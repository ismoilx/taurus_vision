"""
Taurus Vision — Google Colab GPU Integration Endpoint

MAQSAD:
    CPU yetarli bo'lmaganda (8-avlod CPU, GPU yo'q) Google Colab T4/A100
    GPU dan foydalanib video fayllarni qayta ishlash uchun ko'prik.

ARXITEKTURA:
    Colab (GPU)                          Noutbuk (FastAPI + DB)
    ──────────────────────               ──────────────────────────
    1. GET /colab/embeddings    ←←←←←    Barcha embedding vektorlarini npz
    2. Video yuklash, modellar           ngrok tunnel (localhost expose)
    3. YOLO → Muzzle → MobileNet         
    4. Cosine similarity (lokal, npz)    
    5. CattleTracker (Kalman+Hungarian)  
    6. POST /colab/push-tracks  →→→→→→→  DB saqlash + WebSocket broadcast

IKKI ENDPOINT:
    GET  /colab/export-embeddings  — Barcha embedding vektorlarini npz formatda yuboradi
    POST /colab/push-tracks        — Colab natijalarini qabul qiladi, DB ga saqlaydi

AUTENTIFIKATSIYA:
    X-Colab-Key header — settings.COLAB_SECRET_KEY bilan tekshiriladi.
    Agar COLAB_SECRET_KEY sozlanmagan bo'lsa — localhost dan kelgan so'rovlarga ruxsat.
"""

import io
import logging
from datetime import datetime, timezone
from typing import Optional, List

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, AsyncSessionLocal
from app.models.animal import Animal
from app.models.animal_embedding import AnimalEmbedding
from app.models.detection import Detection
from app.models.weight_measurement import WeightMeasurement
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/colab",
    tags=["colab"],
)

WEIGHT_CONF_THRESHOLD = 0.70


# ─── Auth ──────────────────────────────────────────────────────────────────────

def _check_colab_auth(request: Request, x_colab_key: Optional[str] = Header(None)) -> None:
    pass

# ─── Schemas ───────────────────────────────────────────────────────────────────

class ColabTrack(BaseModel):
    """Bitta kuzatilgan qoramol (Colab CattleTracker dan)."""

    track_id:     int             = Field(..., description="Tracker bergan vaqtincha ID")
    animal_id:    Optional[int]   = Field(None, description="Identifikatsiya qilingan hayvon ID si")
    tag_id:       Optional[str]   = Field(None, description="Hayvon teg ID si, masalan JNV-042")
    state:        str             = Field(..., description="tentative | unidentified | identified")
    confidence:   float           = Field(..., ge=0.0, le=1.0, description="YOLO detection confidence")
    id_score:     float           = Field(0.0, ge=0.0, le=1.0, description="Cosine similarity score")
    bbox: dict = Field(
        ...,
        description="Normalized bbox: {x: cx, y: cy, w: width, h: height}",
        examples=[{"x": 0.4, "y": 0.5, "w": 0.15, "h": 0.2}],
    )
    frame_number: Optional[int]   = Field(None, description="Video kadr raqami")
    video_time_s: Optional[float] = Field(None, description="Video vaqti (soniya)")


class ColabPushRequest(BaseModel):
    """Colab dan keladigan to'liq batch."""

    camera_id:    str             = Field("COLAB-VIDEO", description="Kamera ID si")
    video_file:   Optional[str]   = Field(None, description="Video fayl nomi")
    inference_ms: float           = Field(0.0, description="Frame inference vaqti (ms)")
    tracks:       List[ColabTrack] = Field(default_factory=list)
    timestamp:    Optional[str]   = Field(None, description="ISO 8601 timestamp")


class ColabPushResponse(BaseModel):
    saved:   int
    skipped: int
    message: str


# ─── GET /colab/export-embeddings ─────────────────────────────────────────────

@router.get(
    "/export-embeddings",
    summary="Barcha embedding vektorlarini npz formatda yuborish",
    description="""
    Colab uchun: PostgreSQL dan barcha AnimalEmbedding larni yuklab,
    numpy npz formatda qaytaradi.

    Colab da:
        import requests, io, numpy as np
        r = requests.get(URL + '/api/v1/colab/export-embeddings',
                         headers={'X-Colab-Key': SECRET})
        data = np.load(io.BytesIO(r.content))
        embeddings = data['embeddings']   # (N, 128) yoki (N, 1280)
        animal_ids = data['animal_ids']   # (N,) int
        tag_ids    = data['tag_ids']      # (N,) str
    """,
)
async def export_embeddings(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_colab_key: Optional[str] = Header(None),
) -> StreamingResponse:
    _check_colab_auth(request, x_colab_key)

    result = await db.execute(
        select(AnimalEmbedding, Animal.tag_id)
        .join(Animal, AnimalEmbedding.animal_id == Animal.id)
        .where(AnimalEmbedding.embedding.isnot(None))
        .order_by(AnimalEmbedding.animal_id)
    )
    rows = result.all()

    if not rows:
        raise HTTPException(status_code=404, detail="Hali embedding yo'q. Avval jonivorn ro'yxatdan o'tkazing.")

    embeddings_list = []
    animal_ids_list = []
    tag_ids_list    = []

    for emb_row, tag_id in rows:
        vec = emb_row.embedding
        if isinstance(vec, list) and len(vec) > 0:
            embeddings_list.append(np.array(vec, dtype=np.float32))
            animal_ids_list.append(emb_row.animal_id)
            tag_ids_list.append(tag_id or "")

    if not embeddings_list:
        raise HTTPException(status_code=404, detail="Embedding vektorlari bo'sh.")

    embeddings_np = np.array(embeddings_list, dtype=np.float32)
    animal_ids_np = np.array(animal_ids_list, dtype=np.int32)
    tag_ids_np    = np.array(tag_ids_list, dtype=str)

    buf = io.BytesIO()
    np.savez_compressed(
        buf,
        embeddings=embeddings_np,
        animal_ids=animal_ids_np,
        tag_ids=tag_ids_np,
    )
    buf.seek(0)

    logger.info(f"[colab] {len(embeddings_list)} embedding eksport qilindi")

    return StreamingResponse(
        buf,
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=taurus_embeddings.npz"},
    )


# ─── POST /colab/push-tracks ──────────────────────────────────────────────────

@router.post(
    "/push-tracks",
    response_model=ColabPushResponse,
    summary="Colab natijalarini qabul qilish va DB ga saqlash",
    description="""
    Colab da qayta ishlangan track natijalarini qabul qiladi.

    - TENTATIVE tracklar saqlanmaydi (hali tasdiqlanmagan).
    - UNIDENTIFIED va IDENTIFIED tracklar Detection jadvaliga yoziladi.
    - IDENTIFIED tracklar WeightMeasurement ham yaratadi.
    - WebSocket orqali LiveFeedPage ga broadcast qilinadi.
    """,
)
async def push_tracks(
    payload: ColabPushRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_colab_key: Optional[str] = Header(None),
) -> ColabPushResponse:
    _check_colab_auth(request, x_colab_key)

    saved   = 0
    skipped = 0
    now = datetime.now(timezone.utc)

    if payload.timestamp:
        try:
            now = datetime.fromisoformat(payload.timestamp.replace("Z", "+00:00"))
        except ValueError:
            pass

    ws_tracks = []

    for track in payload.tracks:
        if track.state == "tentative":
            skipped += 1
            continue

        bbox = track.bbox
        bbox_dict = {
            "x": round(float(bbox.get("x", 0)), 4),
            "y": round(float(bbox.get("y", 0)), 4),
            "w": round(float(bbox.get("w", 0)), 4),
            "h": round(float(bbox.get("h", 0)), 4),
        }

        w = bbox_dict["w"]
        h = bbox_dict["h"]
        estimated_weight_kg = round(max(150.0, min(700.0, 200.0 + w * h * 1800)), 1)

        det = Detection(
            animal_id         = track.animal_id,
            camera_id         = payload.camera_id,
            timestamp         = now,
            confidence        = round(track.confidence, 4),
            class_id          = 19,
            class_name        = "cow",
            bbox              = bbox_dict,
            estimated_weight  = estimated_weight_kg,
            frame_number      = track.frame_number,
            inference_time_ms = round(payload.inference_ms, 1),
        )
        db.add(det)

        if track.animal_id:
            res = await db.execute(select(Animal).where(Animal.id == track.animal_id))
            animal = res.scalar_one_or_none()
            if animal:
                animal.mark_detected(now)

                if track.confidence >= WEIGHT_CONF_THRESHOLD:
                    db.add(WeightMeasurement(
                        animal_id           = track.animal_id,
                        timestamp           = now,
                        estimated_weight_kg = estimated_weight_kg,
                        confidence_score    = round(track.confidence, 4),
                        camera_id           = payload.camera_id,
                        raw_ai_data         = {
                            "track_id":   track.track_id,
                            "id_score":   round(track.id_score, 4),
                            "bbox":       bbox_dict,
                            "source":     "colab_gpu",
                            "video_file": payload.video_file,
                            "video_time": track.video_time_s,
                        },
                    ))

        ws_tracks.append({
            "track_id":             track.track_id,
            "animal_id":            track.animal_id,
            "tag_id":               track.tag_id,
            "state":                track.state,
            "bbox_color":           "green" if track.state == "identified" else "red",
            "bbox":                 bbox_dict,
            "confidence":           round(track.confidence, 4),
            "identification_score": round(track.id_score, 4),
            "id_attempts":          0,
        })

        saved += 1

    await db.commit()

    # WebSocket broadcast
    try:
        import json
        from app.services.pipeline_manager import get_pipeline_manager
        pm = get_pipeline_manager()
        if pm and hasattr(pm, "_ws_manager") and pm._ws_manager:
            msg = json.dumps({
                "type":   "tracked_detections",
                "camera": payload.camera_id,
                "tracks": ws_tracks,
                "stats":  {
                    "active_tracks":         len(ws_tracks),
                    "identified_tracks":     sum(1 for t in ws_tracks if t["state"] == "identified"),
                    "unidentified_tracks":   sum(1 for t in ws_tracks if t["state"] == "unidentified"),
                    "total_tracks_created":  len(ws_tracks),
                    "total_identifications": sum(1 for t in ws_tracks if t["state"] == "identified"),
                    "source":                "colab_gpu",
                },
            })
            await pm._ws_manager.broadcast(msg)
    except Exception as e:
        logger.debug(f"[colab] WS broadcast o'tkazib yuborildi: {e}")

    logger.info(
        f"[colab] push-tracks: saved={saved} skipped={skipped} "
        f"camera={payload.camera_id} video={payload.video_file}"
    )

    return ColabPushResponse(
        saved=saved,
        skipped=skipped,
        message=f"{saved} track saqlandi, {skipped} o'tkazib yuborildi.",
    )
