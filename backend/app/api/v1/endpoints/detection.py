"""
Taurus Vision — AI Detection API

Endpoints:
  POST /detection/upload      — rasm fayl yuklash va detection
  POST /detection/base64      — base64 rasm detection
  GET  /detection/model-info  — YOLO model haqida ma'lumot
  GET  /detection/health      — servis holati (DOIM 200)

Muhim arxitektura qarorlari:
  1. get_yolo_service() Depends sifatida ISHLATILMAYDI.
     Sabab: test muhitida model yuklanmagan (yolo26n.pt yo'q).
     RuntimeError → pytest ga o'tadi, HTTP response ham emas.
     Yechim: har endpoint ichida try/except → HTTPException(503).

  2. Fayl turi validatsiyasi YOLO tekshiruvidan OLDIN.
     Noto'g'ri fayl turi → 400 (YOLO yuklanmasa ham).

  3. /health endpoint YOLO holatidan MUSTAQIL — har doim 200.

  4. /base64 Pydantic JSON body qabul qiladi (query param emas).
     test: json={"image_base64": "...", "camera_id": "..."}
"""

import base64
import binascii
import io
import logging
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from PIL import Image
from pydantic import BaseModel as PydanticModel, Field

from app.api.v1.deps import get_current_active_user
from app.schemas.detection import (
    BoundingBoxResponse,
    DetectionResponse,
    InferenceResultResponse,
    ModelInfoResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/detection",
    tags=["Detection"],
    dependencies=[Depends(get_current_active_user)],
)

# ── Ruxsat etilgan rasm MIME turlari ─────────────────────────────────────────
_ALLOWED_MIME = {"image/jpeg", "image/jpg", "image/png", "image/bmp", "image/webp"}
_ALLOWED_EXT  = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class Base64DetectRequest(PydanticModel):
    """
    Base64 rasm orqali detection so'rovi.

    image_base64 majburiy maydon — bo'sh qoldirish mumkin emas.
    test: json={"image_base64": "...", "camera_id": "CAM-001"}
    """
    image_base64:         str                  = Field(..., min_length=1)
    camera_id:            Optional[str]        = None
    confidence_threshold: float                = Field(0.5, ge=0.0, le=1.0)
    target_classes:       Optional[list[int]]  = None


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _pil_to_bgr(image: Image.Image) -> np.ndarray:
    """PIL Image → numpy BGR array (YOLO formati)."""
    if image.mode != "RGB":
        image = image.convert("RGB")
    arr = np.array(image)
    return arr[:, :, ::-1].copy()


def _get_yolo_or_503():
    """
    YoloService instance qaytaradi yoki HTTPException(503) ko'taradi.

    Sabab: get_yolo_service() RuntimeError ko'taradi, bu pytest ga o'tib
    HTTP response o'rniga exception sifatida ko'rinadi.
    HTTPException esa FastAPI tomonidan to'g'ri HTTP javobi sifatida
    qayta ishlaydi.

    Returns:
        YoloService — yuklanagan model

    Raises:
        HTTPException 503: Model yuklanmagan
    """
    from app.services.ai.yolo_service import get_yolo_service
    try:
        return get_yolo_service()
    except RuntimeError as exc:
        logger.warning(f"YOLO service mavjud emas: {exc}")
        raise HTTPException(
            status_code=503,
            detail=f"YOLO service not available: {exc}",
        )


def _build_inference_response(result) -> InferenceResultResponse:
    """YoloService InferenceResult → InferenceResultResponse."""
    detections = [
        DetectionResponse(
            class_id=     d.class_id,
            class_name=   d.class_name,
            confidence=   d.confidence,
            bounding_box= BoundingBoxResponse(**d.bounding_box.to_dict()),
            timestamp=    d.timestamp,
            has_mask=     d.mask is not None,
            extra_data=   d.extra_data or {},
        )
        for d in result.detections
    ]
    return InferenceResultResponse(
        detections=        detections,
        detection_count=   result.detection_count,
        inference_time_ms= result.inference_time_ms,
        model_name=        result.model_name,
        frame_shape=       result.frame_shape,
        timestamp=         result.timestamp,
    )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post(
    "/upload",
    response_model=InferenceResultResponse,
    summary="Rasm fayl yuklash va detection",
)
async def detect_from_upload(
    file:                 UploadFile       = File(...),
    confidence_threshold: float            = Query(default=0.5, ge=0.0, le=1.0),
    target_classes:       Optional[str]    = Query(
        default=None,
        description="Vergul bilan ajratilgan class IDlar: '19,20'",
    ),
) -> InferenceResultResponse:
    """
    Yuklangan rasm fayldan ob'ektlarni aniqlaydi.

    Validatsiya tartibi (YOLO dan OLDIN):
      1. Fayl turi → 400
      2. Rasm dekodlash → 400
      3. YOLO holati → 503
      4. Detection → 200

    Raises:
        400: Noto'g'ri fayl turi yoki buzilgan rasm
        503: YOLO model yuklanmagan
    """
    # ── 1. Fayl turi validatsiyasi ────────────────────────────────────────
    filename     = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()
    ext          = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""

    if content_type not in _ALLOWED_MIME and ext not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Noto'g'ri fayl turi: '{file.content_type}'. "
                "Qo'llab-quvvatlanadigan: JPEG, PNG, BMP, WebP."
            ),
        )

    # ── 2. Rasm o'qish ────────────────────────────────────────────────────
    contents = await file.read()
    try:
        image = Image.open(io.BytesIO(contents))
        image.verify()
        image = Image.open(io.BytesIO(contents))  # verify() dan keyin qayta ochamiz
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Buzilgan yoki noto'g'ri rasm: {exc}",
        )

    # ── 3. YOLO service ───────────────────────────────────────────────────
    yolo = _get_yolo_or_503()

    # ── 4. Target classes parse ───────────────────────────────────────────
    classes: Optional[list[int]] = None
    if target_classes:
        try:
            classes = [int(c.strip()) for c in target_classes.split(",") if c.strip()]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="target_classes noto'g'ri format. Misol: '19,20'",
            )

    # ── 5. Detection ──────────────────────────────────────────────────────
    try:
        frame  = _pil_to_bgr(image)
        result = await yolo.detect(
            frame=                frame,
            confidence_threshold= confidence_threshold,
            target_classes=       classes,
        )
        logger.info(
            f"Upload detection: {result.detection_count} ob'ekt, "
            f"{result.inference_time_ms:.1f}ms"
        )
        return _build_inference_response(result)
    except Exception as exc:
        logger.error(f"Upload detection xatosi: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Detection: {exc}")


@router.post(
    "/base64",
    response_model=InferenceResultResponse,
    summary="Base64 rasm orqali detection",
)
async def detect_from_base64(
    body: Base64DetectRequest,
) -> InferenceResultResponse:
    """
    Base64 kodlangan rasmdan ob'ektlarni aniqlaydi.

    Kamera oqimlari, mobil ilovalar va IoT qurilmalar uchun mos.

    Validatsiya tartibi:
      1. Pydantic — image_base64 majburiy → 422
      2. Base64 dekodlash → 400
      3. Rasm ochish → 400
      4. YOLO holati → 503
      5. Detection → 200

    Raises:
        422: image_base64 maydoni yo'q yoki bo'sh
        400: Noto'g'ri base64 yoki rasm
        503: YOLO yuklanmagan
    """
    # ── 1. Base64 dekodlash ───────────────────────────────────────────────
    try:
        image_data = base64.b64decode(body.image_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Noto'g'ri base64 ma'lumot: {exc}",
        )

    # ── 2. Rasm ochish ────────────────────────────────────────────────────
    try:
        image = Image.open(io.BytesIO(image_data))
        image.verify()
        image = Image.open(io.BytesIO(image_data))
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Noto'g'ri rasm ma'lumoti: {exc}",
        )

    # ── 3. YOLO service ───────────────────────────────────────────────────
    yolo = _get_yolo_or_503()

    # ── 4. Detection ──────────────────────────────────────────────────────
    try:
        frame  = _pil_to_bgr(image)
        result = await yolo.detect(
            frame=                frame,
            confidence_threshold= body.confidence_threshold,
            target_classes=       body.target_classes,
        )
        logger.info(
            f"Base64 detection: {result.detection_count} ob'ekt "
            f"(cam={body.camera_id}), {result.inference_time_ms:.1f}ms"
        )
        return _build_inference_response(result)
    except Exception as exc:
        logger.error(f"Base64 detection xatosi: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Detection: {exc}")


@router.get(
    "/model-info",
    response_model=ModelInfoResponse,
    summary="YOLO model haqida ma'lumot",
)
async def get_model_info() -> ModelInfoResponse:
    """
    Yuklangan AI model metadatasi.

    Raises:
        503: Model yuklanmagan
    """
    yolo = _get_yolo_or_503()
    info = yolo.get_model_info()
    return ModelInfoResponse(**info)


@router.get(
    "/health",
    summary="AI servis holati tekshiruvi (DOIM 200)",
)
async def ai_health_check() -> dict:
    """
    AI detection servisining holati.

    BU ENDPOINT DOIM HTTP 200 QAYTARADI.
    YOLO yuklanmagan bo'lsa ham 200 — status field orqali ko'rsatiladi.

    Returns:
        {
            "status":       "healthy" | "not_loaded",
            "model_loaded": bool,
            "model_name":   str | None
        }
    """
    from app.services.ai.yolo_service import _yolo_service as _ys
    loaded     = (_ys is not None) and _ys.is_loaded
    model_name = (_ys.model_name if hasattr(_ys, "model_name") else None) if loaded else None
    return {
        "status":       "healthy" if loaded else "not_loaded",
        "model_loaded": loaded,
        "model_name":   model_name,
    }