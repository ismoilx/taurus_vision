"""
Taurus Vision — Cattle Multi-Object Tracker

NEGA BU KERAK:
    Oldingi pipeline har kadrda har qoramol uchun mustaqil identifikatsiya
    qilardi. Bu ikki muammo yaratadi:
      1. Sekin — har kadrda YOLO + Muzzle + MobileNetV2 = ~300ms/detection
      2. Beqaror — bir xil qoramol har kadrda boshqacha tanilishi mumkin

    Bu modul qoramolni bir marta aniqlaydi, keyin Kalman filter orqali
    kadrlar bo'yicha kuzatadi. Identifikatsiya faqat bir marta muvaffaqiyatli
    bo'lishi kerak, keyin track shu ID bilan davom etadi.

TRACKING ALGORITMI (SORT + improvements):
    1. Kalman predict — har mavjud track uchun keyingi pozitsiyani bashorat
    2. IoU cost matrix — YOLO detections × mavjud tracklar
    3. Hungarian assignment — optimal juftlash (scipy)
    4. Matched: track yangilanadi
    5. Unmatched detection: yangi track yaratiladi (TENTATIVE holat)
    6. Unmatched track: time_since_update++ → ko'p o'tsa o'chiriladi

TRACK HOLATLARI (State Machine):
    TENTATIVE    → Yangi (≥MIN_HITS_CONFIRM kadrdan oldin tasdiqlanmagan)
    UNIDENTIFIED → Tasdiqlangan, lekin kim ekanligi noma'lum (QIZIL box)
    IDENTIFIED   → Tanildi (YASHIL box, real animal_id va tag_id mavjud)
    LOST         → Uzoq ko'rinmadi, o'chirishga tayyor

IKKI BOSQICHLI IDENTIFIKATSIYA:
    Bosqich 1 — Body Appearance (tez, ~50ms):
        Sigir tanasining crop → MobileNetV2 embedding → cosine similarity
        Har BODY_ID_EVERY_N kadrda urinish
        Threshold ≥ BODY_CONF_THRESHOLD → tanildi

    Bosqich 2 — Muzzle (aniq, ~150ms):
        MuzzleDetector → muzzle crop → MobileNetV2 → cosine similarity
        Har MUZZLE_ID_EVERY_N kadrda urinish (kamroq, chunki sekin)
        Threshold ≥ MUZZLE_CONF_THRESHOLD → tanildi

    Fusion (ikkalasi ham past bo'lsa):
        score = BODY_W * body_score + MUZZLE_W * muzzle_score
        score ≥ FUSION_THRESHOLD → tanildi

WEBSOCKET BROADCAST FORMATI:
    {
      "type": "tracked_detection",
      "track_id": 7,                    # Vaqtincha ID (doim bor)
      "animal_id": 42,                  # Haqiqiy ID (faqat tanilganda)
      "tag_id": "JNV-042",              # Tag (faqat tanilganda)
      "state": "identified",            # "tentative"|"unidentified"|"identified"
      "bbox_color": "green",            # "red"|"green"|"orange"
      "bbox": {"x":0.4,"y":0.5,...},
      "confidence": 0.94,
      "identification_score": 0.87
    }
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
from scipy.optimize import linear_sum_assignment

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# KONFIGURATSIYA — O'zgartirish mumkin, arxitektura o'zgarmaydi
# ─────────────────────────────────────────────────────────────────────

# Tracking
IOU_MIN_MATCH            = 0.25   # Track ↔ Detection juftlash uchun minimal IoU
MAX_AGE_UNIDENTIFIED     = 25     # UNIDENTIFIED track yo'qolsa shu kadrdan keyin o'chir
MAX_AGE_IDENTIFIED       = 60     # IDENTIFIED track uchun sabr uzunroq
MIN_HITS_TO_CONFIRM      = 3      # TENTATIVE → UNIDENTIFIED uchun minimal kadr soni

# Identification thresholds
BODY_CONF_THRESHOLD      = 0.75   # Body yolg'iz → tanildi
MUZZLE_CONF_THRESHOLD    = 0.82   # Muzzle yolg'iz → tanildi
FUSION_CONF_THRESHOLD    = 0.68   # Ikkalasi birlashsa → tanildi
BODY_FUSION_WEIGHT       = 0.35   # Fusionda body og'irligi
MUZZLE_FUSION_WEIGHT     = 0.65   # Fusionda muzzle og'irligi (aniqroq)

# Identification attempt frequency
BODY_ID_EVERY_N          = 5      # Har 5 kadrda body ID urinishi
MUZZLE_ID_EVERY_N        = 12     # Har 12 kadrda muzzle ID urinishi
MAX_ID_ATTEMPTS          = 40     # Shu urinishdan keyin yana bir qoramol deymiz


# ─────────────────────────────────────────────────────────────────────
# TRACK STATE
# ─────────────────────────────────────────────────────────────────────

class TrackState(str, Enum):
    TENTATIVE    = "tentative"     # Yangi, hali tasdiqlanmagan
    UNIDENTIFIED = "unidentified"  # Tasdiqlangan, tanilmagan → QIZIL
    IDENTIFIED   = "identified"    # Tanildi → YASHIL
    LOST         = "lost"          # O'chirishga tayyor


# ─────────────────────────────────────────────────────────────────────
# KALMAN FILTER — Constant Velocity Model
# ─────────────────────────────────────────────────────────────────────

class KalmanBoxTracker:
    """
    SORT-style Kalman filter for bounding box tracking.

    State vector (8-dim): [cx, cy, w, h, vx, vy, vw, vh]
    Observation (4-dim):  [cx, cy, w, h]

    Normalized koordinatalar (0.0–1.0) bilan ishlaydi.
    """

    def __init__(self, bbox: np.ndarray) -> None:
        """
        Args:
            bbox: [cx, cy, w, h] normalized koordinatalar
        """
        # --- Matritsalar ---
        # State transition: constant velocity
        self.F = np.eye(8, dtype=np.float32)
        self.F[0, 4] = 1.0  # cx += vx
        self.F[1, 5] = 1.0  # cy += vy
        self.F[2, 6] = 1.0  # w  += vw
        self.F[3, 7] = 1.0  # h  += vh

        # Observation: faqat pozitsiya kuzatiladi
        self.H = np.eye(4, 8, dtype=np.float32)

        # Process noise: kichik harakatlar kutiladi
        self.Q = np.diag([
            1e-5, 1e-5, 1e-4, 1e-4,   # pozitsiya noise
            1e-5, 1e-5, 1e-4, 1e-4,   # tezlik noise
        ]).astype(np.float32)

        # Observation noise: YOLO bbox aniq emas
        self.R = np.diag([
            1e-3, 1e-3, 5e-3, 5e-3    # cx,cy,w,h measurement noise
        ]).astype(np.float32)

        # Initial covariance: tezlik noaniq (katta)
        self.P = np.diag([
            1e-3, 1e-3, 1e-3, 1e-3,
            1.0,  1.0,  1.0,  1.0,
        ]).astype(np.float32)

        # Initial state
        self.x = np.zeros(8, dtype=np.float32)
        self.x[:4] = bbox.astype(np.float32)

    def predict(self) -> np.ndarray:
        """
        Keyingi kadr uchun pozitsiyani bashorat qilish.

        Returns:
            [cx, cy, w, h] predicted bbox (normalized)
        """
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        # w va h manfiy bo'lmasin
        self.x[2] = max(self.x[2], 1e-4)
        self.x[3] = max(self.x[3], 1e-4)
        return self.x[:4].copy()

    def update(self, bbox: np.ndarray) -> None:
        """
        Yangi YOLO detection bilan yangilash.

        Args:
            bbox: [cx, cy, w, h] measured bbox (normalized)
        """
        z = bbox.astype(np.float32)
        y = z - self.H @ self.x                            # Innovation
        S = self.H @ self.P @ self.H.T + self.R            # Innovation covariance
        K = self.P @ self.H.T @ np.linalg.inv(S)           # Kalman gain
        self.x = self.x + K @ y
        self.P = (np.eye(8, dtype=np.float32) - K @ self.H) @ self.P
        self.x[2] = max(self.x[2], 1e-4)
        self.x[3] = max(self.x[3], 1e-4)

    @property
    def bbox(self) -> np.ndarray:
        """Joriy bashorat qilingan bbox [cx, cy, w, h]."""
        return self.x[:4].copy()


# ─────────────────────────────────────────────────────────────────────
# CATTLE TRACK — Bitta qoramolning to'liq holati
# ─────────────────────────────────────────────────────────────────────

class CattleTrack:
    """
    Bitta qoramolning tracking va identifikatsiya holati.

    Har bir yangi detection → yangi CattleTrack.
    Identificatsiya muvaffaqiyatli bo'lguncha qizil box ko'rsatiladi.
    Tanilgandan keyin yashil box va haqiqiy ID.
    """

    _id_counter: int = 0

    def __init__(self, bbox: np.ndarray, detection_confidence: float) -> None:
        """
        Args:
            bbox:                 [cx, cy, w, h] normalized
            detection_confidence: YOLO detection confidence
        """
        CattleTrack._id_counter += 1
        self.track_id: int = CattleTrack._id_counter

        # Kalman tracker
        self.kalman = KalmanBoxTracker(bbox)

        # State machine
        self.state: TrackState = TrackState.TENTATIVE

        # Real identity (tanilgandan keyin to'ldiriladi)
        self.animal_id:   Optional[int] = None
        self.tag_id:      Optional[str] = None
        self.id_score:    float         = 0.0

        # Lifecycle counters
        self.age:               int = 1    # Total kadrlar
        self.hits:              int = 1    # Detection bilan moslashgan kadrlar
        self.time_since_update: int = 0    # Oxirgi detectiondan beri

        # Identification attempts
        self._body_frame_ctr:   int   = 0
        self._muzzle_frame_ctr: int   = 0
        self.id_attempts:       int   = 0

        # Running best scores (fusion uchun)
        self._best_body_score:     float         = 0.0
        self._best_muzzle_score:   float         = 0.0
        self._best_body_animal_id: Optional[int] = None
        self._best_muzzle_animal_id: Optional[int] = None

        # Joriy YOLO confidence
        self.detection_confidence: float = detection_confidence

        logger.debug(f"[Tracker] New track T#{self.track_id} created")

    # ─── Lifecycle ────────────────────────────────────────────────────

    def predict(self) -> np.ndarray:
        """Kalman predict. Har kadrda, detection bo'lmasa ham chaqiriladi."""
        self.age += 1
        self.time_since_update += 1
        self._body_frame_ctr += 1
        self._muzzle_frame_ctr += 1
        return self.kalman.predict()

    def update(self, bbox: np.ndarray, confidence: float) -> None:
        """YOLO detection bilan track ni yangilash."""
        self.kalman.update(bbox)
        self.hits += 1
        self.time_since_update = 0
        self.detection_confidence = confidence

        # TENTATIVE → UNIDENTIFIED
        if self.state == TrackState.TENTATIVE and self.hits >= MIN_HITS_TO_CONFIRM:
            self.state = TrackState.UNIDENTIFIED
            logger.debug(f"[Tracker] T#{self.track_id} confirmed → UNIDENTIFIED")

    def mark_identified(
        self,
        animal_id: int,
        tag_id: Optional[str],
        score: float,
    ) -> None:
        """Qoramol tanildi — state IDENTIFIED ga o'tkazish."""
        self.animal_id = animal_id
        self.tag_id    = tag_id
        self.id_score  = score
        self.state     = TrackState.IDENTIFIED
        logger.info(
            f"[Tracker] T#{self.track_id} → IDENTIFIED: "
            f"animal_id={animal_id}, tag={tag_id}, score={score:.3f}"
        )

    @property
    def is_lost(self) -> bool:
        """Track o'chirilishi kerakmi?"""
        if self.state == TrackState.IDENTIFIED:
            return self.time_since_update > MAX_AGE_IDENTIFIED
        return self.time_since_update > MAX_AGE_UNIDENTIFIED

    @property
    def should_try_body_id(self) -> bool:
        """Body identification urinish vaqti keldi?"""
        return (
            self.state == TrackState.UNIDENTIFIED
            and self._body_frame_ctr >= BODY_ID_EVERY_N
            and self.id_attempts < MAX_ID_ATTEMPTS
        )

    @property
    def should_try_muzzle_id(self) -> bool:
        """Muzzle identification urinish vaqti keldi?"""
        return (
            self.state == TrackState.UNIDENTIFIED
            and self._muzzle_frame_ctr >= MUZZLE_ID_EVERY_N
            and self.id_attempts < MAX_ID_ATTEMPTS
        )

    def reset_body_counter(self) -> None:
        self._body_frame_ctr = 0
        self.id_attempts += 1

    def reset_muzzle_counter(self) -> None:
        self._muzzle_frame_ctr = 0

    def update_body_score(self, animal_id: Optional[int], score: float) -> None:
        if score > self._best_body_score:
            self._best_body_score     = score
            self._best_body_animal_id = animal_id

    def update_muzzle_score(self, animal_id: Optional[int], score: float) -> None:
        if score > self._best_muzzle_score:
            self._best_muzzle_score     = score
            self._best_muzzle_animal_id = animal_id

    def try_fusion_identify(self) -> Optional[tuple[int, float]]:
        """
        Ikkala score ni birlashtirib identifikatsiya qilishga urinish.

        Returns:
            (animal_id, fused_score) yoki None.
        """
        if not self._best_body_animal_id and not self._best_muzzle_animal_id:
            return None

        # Eng yaxshi animal_id ni tanlash (muzzle ustuvor)
        candidate_id = self._best_muzzle_animal_id or self._best_body_animal_id

        body_s  = self._best_body_score   if self._best_body_animal_id  == candidate_id else 0.0
        muzzle_s = self._best_muzzle_score if self._best_muzzle_animal_id == candidate_id else 0.0

        fused = BODY_FUSION_WEIGHT * body_s + MUZZLE_FUSION_WEIGHT * muzzle_s

        if fused >= FUSION_CONF_THRESHOLD:
            return (candidate_id, fused)
        return None

    # ─── Display ──────────────────────────────────────────────────────

    @property
    def bbox_color_bgr(self) -> tuple[int, int, int]:
        """OpenCV/WebSocket uchun BGR rang."""
        if self.state == TrackState.IDENTIFIED:
            return (0, 220, 0)     # Yashil
        elif self.state == TrackState.UNIDENTIFIED:
            return (0, 50, 255)    # Qizil
        else:
            return (0, 165, 255)   # To'q sariq (tentative)

    @property
    def bbox_color_name(self) -> str:
        if self.state == TrackState.IDENTIFIED:
            return "green"
        elif self.state == TrackState.UNIDENTIFIED:
            return "red"
        return "orange"

    @property
    def display_label(self) -> str:
        if self.state == TrackState.IDENTIFIED:
            return self.tag_id or f"ID-{self.animal_id}"
        return f"T#{self.track_id}"

    def to_websocket_dict(self) -> dict:
        """WebSocket broadcast uchun dict."""
        bbox = self.kalman.bbox
        return {
            "track_id":           self.track_id,
            "animal_id":          self.animal_id,
            "tag_id":             self.tag_id,
            "state":              self.state.value,
            "bbox_color":         self.bbox_color_name,
            "bbox": {
                "x": round(float(bbox[0]), 4),
                "y": round(float(bbox[1]), 4),
                "w": round(float(bbox[2]), 4),
                "h": round(float(bbox[3]), 4),
            },
            "confidence":         round(self.detection_confidence, 3),
            "identification_score": round(self.id_score, 3),
            "id_attempts":        self.id_attempts,
        }


# ─────────────────────────────────────────────────────────────────────
# IoU UTILITIES
# ─────────────────────────────────────────────────────────────────────

def _bbox_to_xyxy(cx: float, cy: float, w: float, h: float) -> np.ndarray:
    """[cx,cy,w,h] → [x1,y1,x2,y2]"""
    return np.array([cx - w/2, cy - h/2, cx + w/2, cy + h/2], dtype=np.float32)


def compute_iou_matrix(
    tracks_bboxes: np.ndarray,   # (N, 4) — [cx,cy,w,h] per track
    dets_bboxes:   np.ndarray,   # (M, 4) — [cx,cy,w,h] per detection
) -> np.ndarray:
    """
    N tracks × M detections uchun IoU matritsasini hisoblash.

    Returns:
        (N, M) float32 array — har element [0.0, 1.0] oralig'ida
    """
    n, m = len(tracks_bboxes), len(dets_bboxes)
    if n == 0 or m == 0:
        return np.zeros((n, m), dtype=np.float32)

    # [cx,cy,w,h] → [x1,y1,x2,y2]
    t = np.stack([_bbox_to_xyxy(*b) for b in tracks_bboxes])  # (N,4)
    d = np.stack([_bbox_to_xyxy(*b) for b in dets_bboxes])    # (M,4)

    # Broadcast orqali N×M intersection
    inter_x1 = np.maximum(t[:, None, 0], d[None, :, 0])  # (N,M)
    inter_y1 = np.maximum(t[:, None, 1], d[None, :, 1])
    inter_x2 = np.minimum(t[:, None, 2], d[None, :, 2])
    inter_y2 = np.minimum(t[:, None, 3], d[None, :, 3])

    inter_w = np.maximum(0, inter_x2 - inter_x1)
    inter_h = np.maximum(0, inter_y2 - inter_y1)
    inter   = inter_w * inter_h

    area_t = (t[:, 2] - t[:, 0]) * (t[:, 3] - t[:, 1])  # (N,)
    area_d = (d[:, 2] - d[:, 0]) * (d[:, 3] - d[:, 1])  # (M,)

    union = area_t[:, None] + area_d[None, :] - inter + 1e-9

    return (inter / union).astype(np.float32)


def _det_to_bbox(det) -> np.ndarray:
    """YOLODetection → [cx, cy, w, h] normalized array."""
    bb = det.bounding_box
    return np.array([bb.x, bb.y, bb.width, bb.height], dtype=np.float32)


# ─────────────────────────────────────────────────────────────────────
# MAIN TRACKER
# ─────────────────────────────────────────────────────────────────────

class CattleTracker:
    """
    Qoramollarni multi-object tracking bilan kuzatuvchi va tanuvchi tizim.

    USAGE (detection_pipeline.py dan):

        # Startup da bir marta yaratish
        self._tracker = CattleTracker()

        # Har kadrda
        tracks = await self._tracker.update(
            detections=yolo_detections,
            frame=frame.frame,
            db=db,
        )

        # Natijani WebSocket ga yuborish
        for track in tracks:
            await ws_manager.broadcast(json.dumps({
                "type": "tracked_detection",
                **track.to_websocket_dict()
            }))

    THREAD SAFETY:
        Bu klass bitta pipeline instancedan ishlashga mo'ljallangan.
        Ko'p kamerali setup uchun har kamera uchun alohida CattleTracker.
    """

    def __init__(self) -> None:
        self._tracks: list[CattleTrack] = []
        self._frame_count: int = 0

        # Stats
        self._total_tracks_created:    int = 0
        self._total_identifications:   int = 0
        self._total_body_attempts:     int = 0
        self._total_muzzle_attempts:   int = 0

        logger.info("[Tracker] CattleTracker initialized")

    # ─── Main Update Loop ────────────────────────────────────────────

    async def update(
        self,
        detections: list,          # List[YOLODetection]
        frame: np.ndarray,         # BGR numpy array
        db,                        # AsyncSession
    ) -> list[CattleTrack]:
        """
        Bitta kadr uchun tracking + identification ni bajarish.

        QADAMLAR:
            1. Barcha tracklarni Kalman predict
            2. IoU matrix → Hungarian assignment
            3. Matched tracklar: Kalman update
            4. Yangi detections: yangi track yaratish
            5. Yo'qolgan tracklar: time_since_update++ → o'chirilish
            6. UNIDENTIFIED tracklar: identification urinish
            7. Aktiv tracklar ro'yxatini qaytarish

        Args:
            detections: YOLO dan kelgan YOLODetection ro'yxati
            frame:      Joriy kadr (BGR numpy)
            db:         Async database sessiyasi

        Returns:
            Joriy aktiv CattleTrack ro'yxati (TENTATIVE ham kiradi,
            lekin odatda UNIDENTIFIED va IDENTIFIED ko'rsatiladi)
        """
        self._frame_count += 1

        # ── 1. Barcha tracklar uchun Kalman predict ─────────────────
        for track in self._tracks:
            track.predict()

        # ── 2. Hungarian assignment ─────────────────────────────────
        matched, unmatched_dets, unmatched_tracks = self._associate(detections)

        # ── 3. Matched tracklar: Kalman update ──────────────────────
        for track_idx, det_idx in matched:
            bbox = _det_to_bbox(detections[det_idx])
            conf = detections[det_idx].confidence
            self._tracks[track_idx].update(bbox, conf)

        # ── 4. Yangi detections → yangi tracklar ────────────────────
        for det_idx in unmatched_dets:
            det  = detections[det_idx]
            bbox = _det_to_bbox(det)
            new_track = CattleTrack(bbox, det.confidence)
            self._tracks.append(new_track)
            self._total_tracks_created += 1

        # ── 5. Yo'qolgan tracklar ni o'chirish ─────────────────────
        self._tracks = [t for t in self._tracks if not t.is_lost]

        # ── 6. Identification urinishlari ────────────────────────────
        await self._run_identification(frame=frame, db=db)

        # ── 7. Aktiv tracklar (LOST emas) ───────────────────────────
        active = [
            t for t in self._tracks
            if t.state != TrackState.LOST
        ]

        if active:
            logger.debug(
                f"[Tracker] Frame#{self._frame_count}: "
                f"{len(active)} active tracks "
                f"({sum(1 for t in active if t.state == TrackState.IDENTIFIED)} identified)"
            )

        return active

    # ─── Association ─────────────────────────────────────────────────

    def _associate(
        self,
        detections: list,
    ) -> tuple[list[tuple[int, int]], list[int], list[int]]:
        """
        Detections va mavjud tracklarni IoU + Hungarian orqali juftlash.

        Returns:
            matched:          [(track_idx, det_idx), ...]
            unmatched_dets:   [det_idx, ...] — yangi track kerak
            unmatched_tracks: [track_idx, ...] — detection yo'q
        """
        if not self._tracks or not detections:
            return [], list(range(len(detections))), list(range(len(self._tracks)))

        # Barcha track predicted bbox lari
        track_bboxes = np.array([t.kalman.bbox for t in self._tracks])
        det_bboxes   = np.array([_det_to_bbox(d) for d in detections])

        # IoU matritsasi
        iou_mat = compute_iou_matrix(track_bboxes, det_bboxes)  # (N_tracks, N_dets)

        # Hungarian: cost = 1 - IoU (minimize cost = maximize IoU)
        row_ind, col_ind = linear_sum_assignment(1.0 - iou_mat)

        matched          = []
        unmatched_dets   = set(range(len(detections)))
        unmatched_tracks = set(range(len(self._tracks)))

        for r, c in zip(row_ind, col_ind):
            if iou_mat[r, c] >= IOU_MIN_MATCH:
                matched.append((r, c))
                unmatched_dets.discard(c)
                unmatched_tracks.discard(r)

        return matched, list(unmatched_dets), list(unmatched_tracks)

    # ─── Identification ───────────────────────────────────────────────

    async def _run_identification(
        self,
        frame:  np.ndarray,
        db,
    ) -> None:
        """
        UNIDENTIFIED tracklar uchun identification urinishlari.

        Har kadrda emas — counterlar asosida (BODY_ID_EVERY_N, MUZZLE_ID_EVERY_N).
        Parallel emas — sequential (CPU inferensiya, race condition yo'q).
        """
        for track in self._tracks:
            if track.state != TrackState.UNIDENTIFIED:
                continue

            # Body identification (tez, ko'p urinish)
            if track.should_try_body_id:
                await self._try_body_identification(track, frame, db)
                track.reset_body_counter()

                # Body yolg'iz yetarli bo'lsa — muzzle kutmaymiz
                if track.state == TrackState.IDENTIFIED:
                    continue

            # Muzzle identification (sekin, kam urinish, aniq)
            if track.should_try_muzzle_id:
                await self._try_muzzle_identification(track, frame, db)
                track.reset_muzzle_counter()

                if track.state == TrackState.IDENTIFIED:
                    continue

            # Fusion — ikkalasi ham bor bo'lsa
            if (
                track._best_body_score > 0
                and track._best_muzzle_score > 0
                and track.state == TrackState.UNIDENTIFIED
            ):
                result = track.try_fusion_identify()
                if result:
                    animal_id, fused_score = result
                    tag_id = await self._get_tag_id(db, animal_id)
                    track.mark_identified(animal_id, tag_id, fused_score)
                    self._total_identifications += 1

    async def _try_body_identification(
        self,
        track: CattleTrack,
        frame: np.ndarray,
        db,
    ) -> None:
        """
        Sigirning tana cropidan embedding chiqarib, bazadagi embeddinglar
        bilan cosine similarity hisoblash (tez usul).

        Args:
            track: UNIDENTIFIED holat da bo'lgan track
            frame: Joriy kadr (BGR)
            db:    Async DB sessiya
        """
        self._total_body_attempts += 1

        try:
            # Sigir cropini kesish (katta crop — tana)
            body_crop = self._crop_from_frame(frame, track.kalman.bbox, padding=0.05)
            if body_crop is None:
                return

            # Embedding chiqarish va solishtirish
            from app.services.identification_service import IdentificationService
            from app.utils.image_utils import preprocess_for_mobilenet
            from app.services.ai.feature_extractor import get_feature_extractor

            extractor    = get_feature_extractor()
            preprocessed = preprocess_for_mobilenet(body_crop)
            embedding    = extractor.extract(preprocessed)

            # identify_from_embedding: bazadagi barcha embeddinglar bilan solishtiradi
            id_service = IdentificationService(db)
            result     = await id_service.identify_from_embedding(embedding)

            track.update_body_score(result.animal_id, result.similarity_score)

            logger.debug(
                f"[Tracker] T#{track.track_id} body score={result.similarity_score:.3f} "
                f"(animal={result.animal_id})"
            )

            # Body yolg'iz yetarli
            if result.animal_id and result.similarity_score >= BODY_CONF_THRESHOLD:
                tag_id = await self._get_tag_id(db, result.animal_id)
                track.mark_identified(result.animal_id, tag_id, result.similarity_score)
                self._total_identifications += 1

        except Exception as exc:
            logger.debug(f"[Tracker] Body ID failed T#{track.track_id}: {exc}")

    async def _try_muzzle_identification(
        self,
        track: CattleTrack,
        frame: np.ndarray,
        db,
    ) -> None:
        """
        MuzzleDetector + MobileNetV2 orqali aniq identifikatsiya.

        Body ID dan aniqroq — muzzle sigirning 'barmoq izi'.

        Args:
            track: UNIDENTIFIED holat da bo'lgan track
            frame: Joriy kadr (BGR)
            db:    Async DB sessiya
        """
        self._total_muzzle_attempts += 1

        try:
            # Sigir cropini kesish
            animal_crop = self._crop_from_frame(frame, track.kalman.bbox, padding=0.02)
            if animal_crop is None:
                return

            # Muzzle topish
            from app.services.ai.muzzle_detector import (
                get_muzzle_detector,
                crop_muzzle_from_animal,
            )
            muzzle_detector = get_muzzle_detector()
            muzzle_det = await muzzle_detector.detect_muzzle(animal_crop)

            if muzzle_det is None:
                logger.debug(
                    f"[Tracker] T#{track.track_id} muzzle not found in crop"
                )
                return

            muzzle_crop = crop_muzzle_from_animal(animal_crop, muzzle_det)
            if muzzle_crop is None:
                return

            # Muzzle embedding → identification
            from app.services.identification_service import IdentificationService
            id_service = IdentificationService(db)
            result     = await id_service.identify_from_crop(muzzle_crop)

            track.update_muzzle_score(result.animal_id, result.similarity_score)

            logger.debug(
                f"[Tracker] T#{track.track_id} muzzle score={result.similarity_score:.3f} "
                f"(animal={result.animal_id})"
            )

            # Muzzle yolg'iz yetarli
            if result.is_identified and result.similarity_score >= MUZZLE_CONF_THRESHOLD:
                track.mark_identified(
                    result.animal_id,
                    result.tag_id,
                    result.similarity_score,
                )
                self._total_identifications += 1

        except Exception as exc:
            logger.debug(f"[Tracker] Muzzle ID failed T#{track.track_id}: {exc}")

    # ─── Helpers ─────────────────────────────────────────────────────

    def _crop_from_frame(
        self,
        frame:   np.ndarray,
        bbox:    np.ndarray,   # [cx, cy, w, h] normalized
        padding: float = 0.0,
    ) -> Optional[np.ndarray]:
        """
        Normalized bbox dan piksel crop kesish.

        Args:
            frame:   BGR numpy array
            bbox:    [cx, cy, w, h] 0.0–1.0 oraliq
            padding: Qo'shimcha chegara (0.05 = 5%)

        Returns:
            BGR crop array yoki None (juda kichik bo'lsa)
        """
        h, w = frame.shape[:2]
        cx, cy, bw, bh = bbox

        # Padding qo'shish
        bw = min(bw * (1 + 2 * padding), 1.0)
        bh = min(bh * (1 + 2 * padding), 1.0)

        x1 = max(0, int((cx - bw / 2) * w))
        y1 = max(0, int((cy - bh / 2) * h))
        x2 = min(w, int((cx + bw / 2) * w))
        y2 = min(h, int((cy + bh / 2) * h))

        if (x2 - x1) < 32 or (y2 - y1) < 32:
            return None

        crop = frame[y1:y2, x1:x2]
        return crop if crop.size > 0 else None

    async def _get_tag_id(self, db, animal_id: int) -> Optional[str]:
        """Animal ID dan tag_id ni bazadan olish."""
        try:
            from sqlalchemy import select
            from app.models.animal import Animal
            result = await db.execute(select(Animal.tag_id).where(Animal.id == animal_id))
            return result.scalar_one_or_none()
        except Exception:
            return None

    # ─── Stats ───────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Tracker statistikasini qaytarish (monitoring uchun)."""
        identified_count = sum(
            1 for t in self._tracks if t.state == TrackState.IDENTIFIED
        )
        return {
            "active_tracks":         len(self._tracks),
            "identified_tracks":     identified_count,
            "unidentified_tracks":   len(self._tracks) - identified_count,
            "total_tracks_created":  self._total_tracks_created,
            "total_identifications": self._total_identifications,
            "total_body_attempts":   self._total_body_attempts,
            "total_muzzle_attempts": self._total_muzzle_attempts,
            "frame_count":           self._frame_count,
        }

    def reset(self) -> None:
        """Tracker ni tozalash (pipeline restart da)."""
        self._tracks.clear()
        CattleTrack._id_counter = 0
        logger.info("[Tracker] Reset complete")