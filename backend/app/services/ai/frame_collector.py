"""
Taurus Vision — Frame Collector (Sprint 15-16)

Detection pipeline ishlayotganda qimmatli kadrlarni diskka yig'adi.
Bu kadrlar keyinchalik Custom YOLO fine-tuning uchun training dataset
bo'lib xizmat qiladi.

ARXITEKTURA:
    DetectionPipeline → FrameCollector.maybe_save(frame, detections)
                         ↓ (har N framdan bir)
                        disk: frames/{camera_id}_{timestamp}_{uuid}.jpg
                              frames/{camera_id}_{timestamp}_{uuid}.txt  ← YOLO label

YOLO LABEL FORMATI:
    Har bir satrda: class_index cx cy w h  (normalized 0-1)
    Bizning mapping:
        COCO 19 (cow)   → 0
        COCO 20 (sheep) → 1

SAMPLING STRATEGIYASI:
    - Har bir kameradan alohida hisoblagich
    - Har COLLECT_EVERY_N_DETECTIONS (default: 50) detection'dan bir saqlash
    - Minimum COLLECT_MIN_DETECTIONS (default: 2) detection bo'lsa saqlash
    - Bir framda faqat maqsadli klasslar (cow/sheep) bo'lsa saqlash

DISK BOSHQARUVI:
    MAX_FRAMES_PER_CAMERA (default: 500) chegarasi — eski kadrlar o'chadi
    Jami frames/ papkasi MAX_TOTAL_FRAMES (default: 5000) dan oshmaydi
"""

import hashlib
import logging
import os
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# COCO class ID → Custom YOLO training class index
COCO_TO_TRAINING_CLASS: dict[int, int] = {
    19: 0,  # cow   → class 0
    20: 1,  # sheep → class 1
}

# Qo'llab-quvvatlanadigan maqsadli COCO klasslar
TARGET_COCO_CLASSES: set[int] = set(COCO_TO_TRAINING_CLASS.keys())


class FrameCollector:
    """
    Detection pipeline dan training framlarini yig'uvchi.

    Thread-safe: lock orqali himoyalangan yig'ma hisoblagichlar.

    FOYDALANISH (DetectionPipeline ichida):
        collector = FrameCollector(save_dir="/app/data/training/frames")
        # Har bir muvaffaqiyatli YOLO detection dan keyin:
        await asyncio.get_event_loop().run_in_executor(
            None,
            collector.maybe_save,
            frame, camera_id, detections
        )
    """

    def __init__(
        self,
        save_dir: str,
        collect_every_n: int = 50,      # Har N detectiondan bir saqlash
        min_detections: int  = 2,       # Bir framda kamida N detection bo'lishi
        max_per_camera: int  = 500,     # Bir kamera uchun max saqlangan frame
        max_total: int       = 5000,    # Jami max frame soni
        jpeg_quality: int    = 90,      # Saqlash sifati
    ) -> None:
        self._save_dir    = Path(save_dir)
        self._every_n     = collect_every_n
        self._min_det     = min_detections
        self._max_cam     = max_per_camera
        self._max_total   = max_total
        self._quality     = jpeg_quality

        # Kamera bo'yicha hisoblagichlar (thread-safe)
        self._counters:     dict[str, int] = defaultdict(int)
        self._cam_counts:   dict[str, int] = defaultdict(int)
        self._total_saved:  int = 0
        self._lock          = threading.Lock()

        # Papkani yaratish
        self._save_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"FrameCollector initialized | dir={self._save_dir}")

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def maybe_save(
        self,
        frame:      np.ndarray,
        camera_id:  str,
        detections: list,   # list[Detection] from ai/base.py
    ) -> bool:
        """
        Shart to'g'ri bo'lsa framni saqlaydi.

        Blocking I/O — ThreadPoolExecutor orqali chaqirilishi kerak.

        Args:
            frame:      BGR numpy array
            camera_id:  Kamera identifikatori
            detections: YOLO Detection ob'ektlari ro'yxati

        Returns:
            True → saqlandi, False → o'tkazib yuborildi
        """
        # Faqat maqsadli klasslarni filtrlash
        valid = [
            d for d in detections
            if d.class_id in TARGET_COCO_CLASSES
        ]
        if len(valid) < self._min_det:
            return False

        with self._lock:
            self._counters[camera_id] += 1
            counter = self._counters[camera_id]

            # Har N detectiondan birini saqlash
            if counter % self._every_n != 0:
                return False

            # Limit tekshiruvi
            if self._total_saved >= self._max_total:
                logger.debug(
                    f"[collector] Total limit reached ({self._max_total}), skipping"
                )
                return False

            cam_count = self._cam_counts.get(camera_id, 0)
            if cam_count >= self._max_cam:
                # Kamera uchun eng eski framni o'chirish
                self._evict_oldest_for_camera(camera_id)

        # Disk yozish — lock tashqarida (I/O ni bloklamaslik uchun)
        saved = self._write_frame(frame, camera_id, valid)

        if saved:
            with self._lock:
                self._cam_counts[camera_id] = self._cam_counts.get(camera_id, 0) + 1
                self._total_saved += 1

        return saved

    def get_stats(self) -> dict:
        """Yig'ilgan framlar statistikasi."""
        with self._lock:
            return {
                "total_saved":      self._total_saved,
                "cameras":          dict(self._cam_counts),
                "counters":         dict(self._counters),
                "save_dir":         str(self._save_dir),
                "max_total":        self._max_total,
                "max_per_camera":   self._max_cam,
            }

    def count_collected_frames(self) -> int:
        """Diskda mavjud frame fayllar soni."""
        return len(list(self._save_dir.glob("*.jpg")))

    def reset_stats(self) -> None:
        """Hisoblagichlarni nolga qaytarish (test uchun)."""
        with self._lock:
            self._counters.clear()
            self._cam_counts.clear()
            self._total_saved = 0

    # =========================================================================
    # PRIVATE: DISK OPERATIONS
    # =========================================================================

    def _write_frame(
        self,
        frame:     np.ndarray,
        camera_id: str,
        detections: list,
    ) -> bool:
        """
        Frame va YOLO labellarini diskka yozish.

        Fayl nomlari: {camera_id}_{timestamp}_{uuid8}.jpg / .txt
        Moslik: label .txt fayli rasm .jpg bilan bir xil nom.
        """
        try:
            ts      = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            uid     = uuid.uuid4().hex[:8]
            # camera_id da xavfli belgilar bo'lmasligi uchun sanitize
            cam_safe = camera_id.replace("/", "_").replace(":", "_")[:20]
            stem    = f"{cam_safe}_{ts}_{uid}"

            img_path   = self._save_dir / f"{stem}.jpg"
            label_path = self._save_dir / f"{stem}.txt"

            # JPEG saqlash
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, self._quality]
            ok, buffer = cv2.imencode(".jpg", frame, encode_params)
            if not ok or buffer is None:
                logger.warning(f"[collector] imencode failed for {camera_id}")
                return False

            img_path.write_bytes(buffer.tobytes())

            # YOLO label saqlash
            h, w = frame.shape[:2]
            lines = []
            for det in detections:
                cls_idx = COCO_TO_TRAINING_CLASS.get(det.class_id)
                if cls_idx is None:
                    continue
                bb  = det.bounding_box
                cx  = round(bb.x,     6)
                cy  = round(bb.y,     6)
                bw  = round(bb.width, 6)
                bh  = round(bb.height, 6)
                # Normalized koordinatalar [0, 1] ga clamp
                cx  = max(0.0, min(1.0, cx))
                cy  = max(0.0, min(1.0, cy))
                bw  = max(0.001, min(1.0, bw))
                bh  = max(0.001, min(1.0, bh))
                lines.append(f"{cls_idx} {cx} {cy} {bw} {bh}")

            if not lines:
                # Saqlangan rasm foydasiz — o'chirish
                img_path.unlink(missing_ok=True)
                return False

            label_path.write_text("\n".join(lines), encoding="utf-8")

            logger.debug(
                f"[collector] Saved: {stem}.jpg | "
                f"{len(lines)} labels | camera={camera_id}"
            )
            return True

        except Exception as exc:
            logger.error(
                f"[collector] Write failed for camera {camera_id}: {exc}",
                exc_info=True,
            )
            return False

    def _evict_oldest_for_camera(self, camera_id: str) -> None:
        """
        Kamera uchun eng eski frame juftini o'chirish (jpg + txt).
        Lock ichida chaqiriladi.
        """
        cam_safe = camera_id.replace("/", "_").replace(":", "_")[:20]
        pattern  = f"{cam_safe}_*.jpg"
        files    = sorted(self._save_dir.glob(pattern))

        if not files:
            return

        oldest = files[0]
        label  = oldest.with_suffix(".txt")

        try:
            oldest.unlink(missing_ok=True)
            label.unlink(missing_ok=True)
            self._cam_counts[camera_id] = max(
                0, self._cam_counts.get(camera_id, 0) - 1
            )
            self._total_saved = max(0, self._total_saved - 1)
            logger.debug(f"[collector] Evicted oldest: {oldest.name}")
        except Exception as exc:
            logger.warning(f"[collector] Evict failed: {exc}")


# =============================================================================
# Global singleton
# =============================================================================

_collector: Optional[FrameCollector] = None


def get_frame_collector() -> Optional[FrameCollector]:
    """
    Global FrameCollector instance ni qaytaradi.

    Agar training konfiguratsiyasi o'chirilgan bo'lsa — None qaytaradi
    va detection pipeline hech narsa qilmaydi.
    """
    return _collector


def initialize_frame_collector(save_dir: str, **kwargs) -> FrameCollector:
    """
    Global FrameCollector ni yaratish va qaytarish.

    app/main.py startup event da chaqiriladi.
    """
    global _collector
    _collector = FrameCollector(save_dir=save_dir, **kwargs)
    logger.info(
        f"[collector] Initialized | dir={save_dir} | kwargs={kwargs}"
    )
    return _collector