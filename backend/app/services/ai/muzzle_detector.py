"""
Taurus Vision — Muzzle Detection Service

ARXITEKTURA:
    YOLO26 (yolo26n.pt) → sigir/qo'y bbox
        ↓
    MuzzleDetector (best.pt) ← BU SERVIS
        Input:  sigir bbox cropidan olingan kichik rasm
        Output: muzzle bbox (sigir cropiga nisbatan koordinatalar)
        ↓
    MobileNetV2 → 1280-dim embedding → cosine similarity → animal_id

MUHIM FARQ (yolo_service.py dan):
    - YoloService → to'liq kadrda ishlaydi → sigir topadi (COCO class 19/20)
    - MuzzleDetector → SIGIR CROPIDA ishlaydi → muzzle topadi (custom class 0)

MODEL (best.pt):
    Custom trained YOLO model (versiya muhim emas — ultralytics universal load qiladi).
    Class 0: muzzle (burun/og'iz sohasi)
    Input:  sigir bbox ni kesib olingan rasm (variable size)
    Output: muzzle bbox (normalized, 0-1 coordinates relative to crop)

WORKFLOW (detection_pipeline.py dan chaqiriladi):
    1. YOLO26 sigir topadi → det.bounding_box (x, y, w, h) normalized
    2. crop_animal_region(frame, det.bounding_box) → animal_crop (BGR numpy)
    3. muzzle_detector.detect_muzzle(animal_crop) → MuzzleDetection yoki None
    4. Muzzle topilsa → muzzle_crop ni IdentificationService ga uzatish
    5. Muzzle topilmasa → identifikatsiyani o'tkazib yuborish

THREAD SAFETY:
    Singleton pattern — bitta model instance.
    Inference: ThreadPoolExecutor orqali (event loop bloklanmaydi).
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

# Muzzle class ID (custom model ichida)
MUZZLE_CLASS_ID = 0

# Minimal muzzle crop o'lchami (pixel) — kichikroq bo'lsa sifatsiz
MIN_MUZZLE_SIZE_PX = 24


@dataclass
class MuzzleDetection:
    """
    Muzzle detection natijasi.

    Koordinatalar SIGIR CROPIGA nisbatan normalized (0.0-1.0).
    To'liq kadrga nisbatan koordinata olish uchun:
        full_x1 = animal_x1 + muzzle.x1 * animal_width
        full_y1 = animal_y1 + muzzle.y1 * animal_height

    Attributes:
        x1, y1:     Muzzle bbox yuqori chap burchak (normalized, crop ga nisbatan)
        x2, y2:     Muzzle bbox quyi o'ng burchak (normalized, crop ga nisbatan)
        confidence: Detection ishonchliligi (0.0-1.0)
    """
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float

    @property
    def width(self) -> float:
        """Muzzle bbox kengligi (normalized)."""
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        """Muzzle bbox balandligi (normalized)."""
        return self.y2 - self.y1

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def center_y(self) -> float:
        return (self.y1 + self.y2) / 2

    def to_dict(self) -> dict[str, float]:
        return {
            "x1": round(self.x1, 4),
            "y1": round(self.y1, 4),
            "x2": round(self.x2, 4),
            "y2": round(self.y2, 4),
            "confidence": round(self.confidence, 4),
        }


class MuzzleDetector:
    """
    Sigir cropidan muzzle ni aniqlash servisi.

    Singleton pattern — model bir marta yuklanadi va qayta ishlatiladi.

    MUHIM:
        Bu servis to'liq kadrda EMAS, SIGIR CROPIDA ishlaydi.
        Buning sababi:
        1. Tezlik — kichik rasm tezroq inferensiya
        2. Aniqlik — background yo'q, faqat sigir bor
        3. Moslik — best.pt ehtimol sigir rasmlarida o'qitilgan

    USAGE:
        detector = MuzzleDetector()
        await detector.load_model()

        # Inference
        animal_crop = frame[y1:y2, x1:x2]  # sigir bbox cropidan
        result = await detector.detect_muzzle(animal_crop)
        if result:
            muzzle_crop = crop_muzzle_from_animal(animal_crop, result)
            # → MobileNetV2 ga uzatish
    """

    _instance: "MuzzleDetector | None" = None
    _model = None
    _executor: ThreadPoolExecutor | None = None

    def __new__(cls) -> "MuzzleDetector":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize service (called once due to singleton)."""
        if not hasattr(self, "_initialized"):
            self._initialized = False
            self._model_path: Path | None = None
            self._device = "cpu"
            self._class_names: dict[int, str] = {}

            # Performance tracking
            self._total_inferences = 0
            self._total_inference_time = 0.0
            self._total_muzzles_found = 0
            self._total_muzzles_missed = 0

    # ================================================================ #
    # LIFECYCLE                                                          #
    # ================================================================ #

    async def load_model(self) -> None:
        """
        Load muzzle detection model (best.pt) from disk.

        Model path: settings.muzzle_model_path → /app/ml/models/best.pt
        Agar fayl topilmasa → RuntimeError (bu model auto-download emas,
        chunki custom trained).

        Args:
            None (path settings dan olinadi)

        Raises:
            RuntimeError: Model fayl topilmasa yoki yuklab bo'lmasa.
        """
        if self._initialized:
            logger.warning("Muzzle detector already loaded")
            return

        try:
            from ultralytics import YOLO

            model_path = Path("/app/ml/models") / settings.MUZZLE_MODEL

            if not model_path.exists():
                # Development muhitda local path ni sinab ko'rish
                local_path = Path(settings.ML_MODEL_PATH) / settings.MUZZLE_MODEL
                if local_path.exists():
                    model_path = local_path
                else:
                    raise RuntimeError(
                        f"Muzzle model topilmadi: {model_path}\n"
                        f"Lokal path ham yo'q: {local_path}\n"
                        f"best.pt faylini backend/ml/models/ papkasiga joylang."
                    )

            logger.info(f"Loading muzzle detector: {model_path}")

            start_time = time.time()
            self._model = YOLO(str(model_path))
            load_time = time.time() - start_time

            self._model_path = model_path
            self._class_names = self._model.names

            import torch
            self._device = "cuda" if torch.cuda.is_available() else "cpu"

            # Warm-up — birinchi inferensiya sekin
            logger.info("Warming up muzzle detector...")
            dummy = np.zeros((224, 224, 3), dtype=np.uint8)
            _ = self._model.predict(dummy, verbose=False)

            self._executor = ThreadPoolExecutor(
                max_workers=2,
                thread_name_prefix="muzzle_inference",
            )

            self._initialized = True

            logger.info(
                f"✓ Muzzle detector loaded in {load_time:.2f}s "
                f"(device: {self._device}, classes: {self._class_names})"
            )

        except RuntimeError:
            raise
        except Exception as exc:
            logger.error(f"Failed to load muzzle model: {exc}", exc_info=True)
            raise RuntimeError(f"Muzzle model loading failed: {exc}")

    async def unload_model(self) -> None:
        """Modelni xotiradan o'chirish."""
        logger.info("Unloading muzzle detector...")

        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None

        self._model = None
        self._initialized = False
        logger.info("✓ Muzzle detector unloaded")

    @property
    def is_loaded(self) -> bool:
        """Model yuklanganligini tekshirish."""
        return self._initialized and self._model is not None

    # ================================================================ #
    # DETECTION                                                          #
    # ================================================================ #

    async def detect_muzzle(
        self,
        animal_crop: np.ndarray,
        confidence_threshold: Optional[float] = None,
    ) -> Optional[MuzzleDetection]:
        """
        Sigir cropidan muzzleni aniqlash.

        Input: sigir bbox ni kesib olingan BGR rasm (variable size).
        Output: eng ishonchli muzzle bbox yoki None.

        Agar bir nechta muzzle topilsa (noodatiy), eng yuqori confidence li
        tanlnadi.

        Args:
            animal_crop:          Sigir bbox cropidan olingan BGR numpy array.
                                  O'lcham muhim emas — YOLO ichki resize qiladi.
            confidence_threshold: Min confidence. None → settings qiymatidan.

        Returns:
            MuzzleDetection (normalized coords, crop ga nisbatan) yoki None.

        Raises:
            RuntimeError: Agar model yuklanmagan bo'lsa.
            ValueError:   Agar animal_crop noto'g'ri bo'lsa.
        """
        if not self._initialized or self._model is None:
            raise RuntimeError(
                "Muzzle detector not loaded. Call load_model() first."
            )

        if animal_crop is None or animal_crop.size == 0:
            raise ValueError("animal_crop is empty or None")

        if len(animal_crop.shape) != 3 or animal_crop.shape[2] != 3:
            raise ValueError(
                f"animal_crop shape {animal_crop.shape} yaroqsiz. "
                f"(height, width, 3) kerak."
            )

        threshold = confidence_threshold or settings.MUZZLE_CONFIDENCE_THRESHOLD

        import asyncio
        loop = asyncio.get_event_loop()

        results, inference_ms = await loop.run_in_executor(
            self._executor,
            self._run_inference,
            animal_crop,
            threshold,
        )

        self._total_inferences += 1
        self._total_inference_time += inference_ms

        best = self._pick_best_muzzle(results[0], animal_crop.shape)

        if best is not None:
            self._total_muzzles_found += 1
            logger.debug(
                f"Muzzle topildi: conf={best.confidence:.3f} "
                f"bbox=({best.x1:.2f},{best.y1:.2f},"
                f"{best.x2:.2f},{best.y2:.2f}) "
                f"({inference_ms:.1f}ms)"
            )
        else:
            self._total_muzzles_missed += 1
            logger.debug(
                f"Muzzle topilmadi (threshold={threshold:.2f}, "
                f"{inference_ms:.1f}ms)"
            )

        return best

    def _run_inference(
        self,
        crop: np.ndarray,
        confidence_threshold: float,
    ) -> tuple[list, float]:
        """
        YOLO inferensiyasini thread pool ichida bajarish.

        Returns:
            (results_list, inference_time_ms)
        """
        start = time.time()

        results = self._model.predict(
            crop,
            conf=confidence_threshold,
            classes=[MUZZLE_CLASS_ID],
            verbose=False,
            imgsz=640,
            half=False,
        )

        elapsed_ms = (time.time() - start) * 1000
        return results, elapsed_ms

    def _pick_best_muzzle(
        self,
        result: Any,
        crop_shape: tuple,
    ) -> Optional[MuzzleDetection]:
        """
        YOLO natijasidan eng yaxshi muzzle detectionni tanlash.

        Ko'p muzzle topilsa (odatda 1 ta bo'ladi) — eng yuqori
        confidence li tanlnadi.

        Args:
            result:     YOLO natija ob'ekti (result.boxes)
            crop_shape: (height, width, channels) — normalizatsiya uchun

        Returns:
            Eng yaxshi MuzzleDetection yoki None.
        """
        if result.boxes is None or len(result.boxes) == 0:
            return None

        crop_h, crop_w = crop_shape[:2]

        boxes       = result.boxes.xyxy.cpu().numpy()   # [x1, y1, x2, y2] absolute
        confidences = result.boxes.conf.cpu().numpy()
        class_ids   = result.boxes.cls.cpu().numpy().astype(int)

        best_det: Optional[MuzzleDetection] = None

        for box, conf, cls_id in zip(boxes, confidences, class_ids):
            if cls_id != MUZZLE_CLASS_ID:
                continue

            abs_x1, abs_y1, abs_x2, abs_y2 = box

            # Minimal o'lcham tekshiruvi
            w_px = abs_x2 - abs_x1
            h_px = abs_y2 - abs_y1
            if w_px < MIN_MUZZLE_SIZE_PX or h_px < MIN_MUZZLE_SIZE_PX:
                logger.debug(
                    f"Muzzle cropdan o'tkazib yuborildi: {w_px:.0f}x{h_px:.0f}px "
                    f"(min {MIN_MUZZLE_SIZE_PX}px)"
                )
                continue

            # Normalize (0.0-1.0, crop ga nisbatan)
            norm_x1 = max(0.0, abs_x1 / crop_w)
            norm_y1 = max(0.0, abs_y1 / crop_h)
            norm_x2 = min(1.0, abs_x2 / crop_w)
            norm_y2 = min(1.0, abs_y2 / crop_h)

            det = MuzzleDetection(
                x1=norm_x1,
                y1=norm_y1,
                x2=norm_x2,
                y2=norm_y2,
                confidence=float(conf),
            )

            if best_det is None or det.confidence > best_det.confidence:
                best_det = det

        return best_det

    # ================================================================ #
    # STATISTICS                                                         #
    # ================================================================ #

    def get_stats(self) -> dict[str, Any]:
        """Muzzle detector statistikasini qaytarish."""
        total = self._total_inferences
        detection_rate = (
            self._total_muzzles_found / total * 100
            if total > 0 else 0.0
        )
        avg_ms = (
            self._total_inference_time / total
            if total > 0 else 0.0
        )
        return {
            "model": settings.MUZZLE_MODEL,
            "loaded": self._initialized,
            "device": self._device,
            "total_inferences": total,
            "muzzles_found": self._total_muzzles_found,
            "muzzles_missed": self._total_muzzles_missed,
            "detection_rate_pct": round(detection_rate, 1),
            "avg_inference_ms": round(avg_ms, 2),
        }


# ================================================================ #
# HELPER: Muzzle cropni full frame koordinatalariga aylantirish    #
# ================================================================ #

def crop_muzzle_from_animal(
    animal_crop: np.ndarray,
    muzzle_det: MuzzleDetection,
    padding: float = 0.05,
) -> Optional[np.ndarray]:
    """
    MuzzleDetection natijasidan muzzle regionini kesib olish.

    animal_crop (sigir region) va muzzle normalized koordinatalaridan
    haqiqiy BGR piksel rasmini qaytaradi.

    Args:
        animal_crop: Sigir bbox cropidan olingan BGR rasm.
        muzzle_det:  MuzzleDetector.detect_muzzle() natijasi.
        padding:     Qo'shimcha chegara (default 5% — keskin chiziq yo'q).

    Returns:
        Muzzle region BGR numpy array (MobileNetV2 ga tayyor), yoki None.

    Example:
        animal_crop = frame[ay1:ay2, ax1:ax2]
        muzzle_det  = await muzzle_detector.detect_muzzle(animal_crop)
        if muzzle_det:
            muzzle_img = crop_muzzle_from_animal(animal_crop, muzzle_det)
            embedding  = feature_extractor.extract(
                preprocess_for_mobilenet(muzzle_img)
            )
    """
    if animal_crop is None or animal_crop.size == 0:
        return None

    h, w = animal_crop.shape[:2]

    # Absolute pixel koordinatalar
    x1 = muzzle_det.x1 * w
    y1 = muzzle_det.y1 * h
    x2 = muzzle_det.x2 * w
    y2 = muzzle_det.y2 * h

    # Padding qo'shish
    pad_x = (x2 - x1) * padding
    pad_y = (y2 - y1) * padding

    x1 = max(0, int(x1 - pad_x))
    y1 = max(0, int(y1 - pad_y))
    x2 = min(w, int(x2 + pad_x))
    y2 = min(h, int(y2 + pad_y))

    crop = animal_crop[y1:y2, x1:x2]

    if crop.size == 0:
        logger.warning("crop_muzzle_from_animal: empty crop after clamp")
        return None

    return crop


def get_absolute_muzzle_coords(
    animal_abs_x1: int,
    animal_abs_y1: int,
    animal_abs_x2: int,
    animal_abs_y2: int,
    muzzle_det: MuzzleDetection,
) -> tuple[int, int, int, int]:
    """
    Muzzle koordinatalarini to'liq kadrga nisbatan abs. pixel ga aylantirish.

    Debug va WebSocket broadcast uchun foydali — muzzle bbox ni original
    kadr ustiga chizish kerak bo'lganda.

    Args:
        animal_abs_*: Sigir bbox ning to'liq kadrga nisbatan piksel koordinatalari.
        muzzle_det:   MuzzleDetection natijasi (sigir cropiga nisbatan normalized).

    Returns:
        (full_x1, full_y1, full_x2, full_y2) — to'liq kadrga nisbatan piksel.

    Example:
        abs_x1, abs_y1, abs_x2, abs_y2 = get_absolute_muzzle_coords(
            ax1, ay1, ax2, ay2, muzzle_det
        )
        # Endi bu koordinatalar cv2.rectangle() uchun to'g'ridan ishlatiladi
    """
    animal_w = animal_abs_x2 - animal_abs_x1
    animal_h = animal_abs_y2 - animal_abs_y1

    full_x1 = animal_abs_x1 + int(muzzle_det.x1 * animal_w)
    full_y1 = animal_abs_y1 + int(muzzle_det.y1 * animal_h)
    full_x2 = animal_abs_x1 + int(muzzle_det.x2 * animal_w)
    full_y2 = animal_abs_y1 + int(muzzle_det.y2 * animal_h)

    return full_x1, full_y1, full_x2, full_y2


# ================================================================ #
# SINGLETON MANAGEMENT                                               #
# ================================================================ #

_muzzle_detector: MuzzleDetector | None = None


def get_muzzle_detector() -> MuzzleDetector:
    """
    Global MuzzleDetector instanceni qaytarish.

    Raises:
        RuntimeError: Agar servis initialize qilinmagan bo'lsa.
    """
    global _muzzle_detector

    if _muzzle_detector is None:
        _muzzle_detector = MuzzleDetector()

    if not _muzzle_detector.is_loaded:
        raise RuntimeError(
            "Muzzle detector not loaded. "
            "Ensure initialize_muzzle_detector() is called in startup event."
        )

    return _muzzle_detector


async def initialize_muzzle_detector() -> MuzzleDetector:
    """
    Muzzle detector ni ishga tushirish (startup event da chaqiriladi).

    Returns:
        Initialized MuzzleDetector singleton.

    Raises:
        RuntimeError: Model yuklab bo'lmasa.
    """
    global _muzzle_detector

    if _muzzle_detector is None:
        _muzzle_detector = MuzzleDetector()

    await _muzzle_detector.load_model()
    return _muzzle_detector


async def shutdown_muzzle_detector() -> None:
    """Muzzle detector ni to'xtatish (shutdown event da chaqiriladi)."""
    global _muzzle_detector

    if _muzzle_detector is not None:
        await _muzzle_detector.unload_model()