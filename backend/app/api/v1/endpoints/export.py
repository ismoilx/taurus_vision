"""
Taurus Vision — Export API Endpoints

CSV va Excel formatida ma'lumot eksporti.

ENDPOINTLAR:
    POST GET /export/animals/csv     — Jonivorlar CSV (filtrlangan)
    GET      /export/animals/excel   — Jonivorlar Excel (professional)  ← B7 yangi
    POST     /export/detections/csv  — Deteksiyalar CSV (sana oralig'i)
    POST     /export/weights/excel   — Og'irlik Excel (har jonivor varaq)
    GET      /export/all/excel       — To'liq arxiv Excel (4 varaqli)
    GET      /export/templates       — Mavjud eksport turlari ro'yxati

AUTENTIFIKATSIYA:
    Barcha endpointlar — VIEWER+ (get_current_active_user)

FAYL NOMLANISHI:
    animals_YYYYMMDD_HHMMSS.csv / .xlsx
    detections_FROM_TO.csv
    weights_YYYYMMDD.xlsx
    farm_data_complete_YYYYMMDD_HHMMSS.xlsx
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_active_user
from app.core.database import get_db
from app.core.logging_config import get_logger
from app.schemas.export import AnimalsExportRequest, DetectionsExportRequest, WeightsExportRequest
from app.services.export_service import ExportService

logger = get_logger(__name__)

router = APIRouter(
    prefix="/export",
    tags=["Export"],
    dependencies=[Depends(get_current_active_user)],
)

_svc = ExportService()


# =============================================================================
# HELPERS
# =============================================================================

def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

def _streaming(raw: bytes, media_type: str, filename: str) -> StreamingResponse:
    return StreamingResponse(
        BytesIO(raw),
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Length":      str(len(raw)),
        },
    )


# =============================================================================
# ANIMALS — CSV
# =============================================================================

@router.post(
    "/animals/csv",
    summary="Jonivorlar CSV eksporti",
    description="""
    Jonivorlarni CSV formatida yuklab oladi.

    **Filtrlar:** status, species, gender, tag_id (qisman mos)

    **CSV ustunlari:**
    id, tag_id, species, gender, status, breed, acquisition_date,
    total_detections, last_detected_at, notes

    **Foydalanish holatlari:** Excel tahlili, zaxira, tashqi tizim
    """,
    responses={
        200: {"description": "CSV fayl", "content": {"text/csv": {}}},
        500: {"description": "Server xatosi"},
    },
)
async def export_animals_csv(
    request: AnimalsExportRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Jonivorlarni CSV sifatida yuklab oladi."""
    logger.info(f"[endpoint] POST /export/animals/csv filters={request.model_dump()}")
    try:
        raw = await _svc.export_animals_csv(db, filters=request.model_dump(exclude_none=True))
        return _streaming(raw, "text/csv", f"animals_{_now_str()}.csv")
    except Exception as exc:
        logger.error(f"[endpoint] animals/csv xatosi: {exc}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "CSV eksportda xato")


# =============================================================================
# ANIMALS — EXCEL (B7 — yangi)
# =============================================================================

@router.get(
    "/animals/excel",
    summary="Jonivorlar Excel eksporti (professional)",
    description="""
    Jonivorlarni professional formatlangan **.xlsx** faylda yuklab oladi.

    **Excel tarkibi:**

    | Varaq | Nomi | Mazmun |
    |-------|------|--------|
    | 1 | Ro'yxat | Barcha jonivorlar; holat rangi, muzlatilgan sarlavha |
    | 2 | Statistika | Tur / holat taqsimot; umumiy ko'rsatkichlar |

    **Filtrlar (query params):**
    - `status`  — holat (active / sick / quarantine / sold / deceased)
    - `species` — tur (cattle / sheep / goat / horse / other)
    - `gender`  — jins (male / female / unknown)
    - `tag_id`  — Tag ID (qisman mos, katta/kichik harfga sezgir emas)

    **Professional formatlash:**
    - Qoʻyuq sarlavha qatori (muzlatilgan)
    - Holat katakchalari — har holat o'z rangi bilan
    - Alternativ qator ranglari
    - Avtomatik ustun kengliigi
    - Tashqi tahlil uchun tayyor

    **Namuna:**
    ```
    GET /api/v1/export/animals/excel?status=active&species=cattle
    ```
    """,
    responses={
        200: {
            "description": "Excel .xlsx fayl",
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}
            },
        },
        400: {"description": "Noto'g'ri filtr"},
        500: {"description": "Server xatosi"},
    },
)
async def export_animals_excel(
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Holat filtri: active | sick | quarantine | sold | deceased | transferred",
    ),
    species: Optional[str] = Query(
        None,
        description="Tur filtri: cattle | sheep | goat | horse | other",
    ),
    gender: Optional[str] = Query(
        None,
        description="Jins filtri: male | female | unknown",
    ),
    tag_id: Optional[str] = Query(
        None,
        description="Tag ID bo'yicha qisman qidiruv",
    ),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Jonivorlarni professional Excel (.xlsx) sifatida yuklab oladi.

    Filtrlar query param sifatida beriladi.
    Filtr ko'rsatilmasa — barcha jonivorlar eksport qilinadi.
    """
    filters: dict = {}
    if status_filter: filters["status"]  = status_filter
    if species:        filters["species"] = species
    if gender:         filters["gender"]  = gender
    if tag_id:         filters["tag_id"]  = tag_id

    logger.info(f"[endpoint] GET /export/animals/excel filters={filters}")

    try:
        raw = await _svc.export_animals_excel(db, filters=filters or None)
        filename = f"animals_{_now_str()}.xlsx"
        return _streaming(
            raw,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    except Exception as exc:
        logger.error(f"[endpoint] animals/excel xatosi: {exc}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Excel eksportda xato")


# =============================================================================
# DETECTIONS — CSV
# =============================================================================

@router.post(
    "/detections/csv",
    summary="Deteksiyalar CSV eksporti",
    description="""
    Deteksiya jurnalini CSV formatida yuklab oladi.

    **Majburiy:** `date_from`, `date_to`

    **Ixtiyoriy:** `animal_id` — bitta jonivor bo'yicha filtr

    **Sana oralig'i:** maksimal 365 kun

    **CSV ustunlari:**
    id, animal_id, animal_tag_id, camera_id, timestamp,
    confidence, class_name, bbox_x, bbox_y, bbox_w, bbox_h
    """,
    responses={
        200: {"description": "CSV fayl", "content": {"text/csv": {}}},
        400: {"description": "Noto'g'ri sana oralig'i"},
        500: {"description": "Server xatosi"},
    },
)
async def export_detections_csv(
    request: DetectionsExportRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Deteksiyalarni CSV sifatida yuklab oladi."""
    diff = (request.date_to - request.date_from).days
    if diff > 365:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Sana oralig'i 365 kundan oshishi mumkin emas",
        )

    logger.info(f"[endpoint] POST /export/detections/csv {request.date_from}→{request.date_to}")
    try:
        raw = await _svc.export_detections_csv(
            db,
            date_from=request.date_from,
            date_to=request.date_to,
            animal_id=request.animal_id,
        )
        suffix  = f"_animal{request.animal_id}" if request.animal_id else ""
        fname   = f"detections_{request.date_from}_{request.date_to}{suffix}_{_now_str()}.csv"
        return _streaming(raw, "text/csv", fname)
    except Exception as exc:
        logger.error(f"[endpoint] detections/csv xatosi: {exc}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "CSV eksportda xato")


# =============================================================================
# WEIGHTS — EXCEL
# =============================================================================

@router.post(
    "/weights/excel",
    summary="Og'irlik o'lchovlari Excel eksporti",
    description="""
    Og'irlik o'lchovlarini ko'p varaqli Excel faylida yuklab oladi.

    **Excel tarkibi:**
    - Varaq 1 (Xulosa): Barcha jonivornlar uchun umumiy
    - Varaq 2+ (Jonivor_{tag}): Har bir jonivor uchun alohida

    **Ixtiyoriy:** `animal_ids` — faqat ma'lum jonivornlar (bo'sh = hammasi)
    """,
    responses={
        200: {
            "description": "Excel .xlsx fayl",
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}
            },
        },
        500: {"description": "Server xatosi"},
    },
)
async def export_weights_excel(
    request: WeightsExportRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Og'irlik o'lchovlarini Excel sifatida yuklab oladi."""
    logger.info(f"[endpoint] POST /export/weights/excel animal_ids={request.animal_ids}")
    try:
        raw = await _svc.export_weights_excel(db, animal_ids=request.animal_ids)
        return _streaming(
            raw,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            f"weights_{_now_str()}.xlsx",
        )
    except Exception as exc:
        logger.error(f"[endpoint] weights/excel xatosi: {exc}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Excel eksportda xato")


# =============================================================================
# TO'LIQ ARXIV — EXCEL
# =============================================================================

@router.get(
    "/all/excel",
    summary="To'liq arxiv Excel eksporti",
    description="""
    Barcha ferma ma'lumotlarini 4 varaqli Excel faylida yuklab oladi.

    **Excel tarkibi:**
    - Varaq 1 — Jonivorlar (hammasi)
    - Varaq 2 — Deteksiyalar (so'nggi 30 kun, max 10 000)
    - Varaq 3 — Og'irlik o'lchovlari (max 10 000)
    - Varaq 4 — Statistika

    ⚠ Katta fermalarda fayl hajmi 100MB+ bo'lishi mumkin.
    """,
    responses={
        200: {
            "description": "Excel .xlsx fayl",
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}
            },
        },
        500: {"description": "Server xatosi"},
    },
)
async def export_all_data_excel(
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Barcha ferma ma'lumotlarini to'liq Excel faylida yuklab oladi."""
    logger.info("[endpoint] GET /export/all/excel")
    try:
        raw = await _svc.export_all_data_excel(db)
        return _streaming(
            raw,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            f"farm_data_complete_{_now_str()}.xlsx",
        )
    except Exception as exc:
        logger.error(f"[endpoint] all/excel xatosi: {exc}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Excel eksportda xato")


# =============================================================================
# TEMPLATES — INFO
# =============================================================================

@router.get(
    "/templates",
    summary="Mavjud eksport turlari",
    description="Barcha mavjud eksport endpointlari va ularning parametrlari haqida ma'lumot.",
)
async def get_export_templates() -> dict:
    """Mavjud eksport shablonlari ro'yxatini qaytaradi."""
    return {
        "templates": [
            {
                "name":        "Jonivorlar CSV",
                "endpoint":    "/api/v1/export/animals/csv",
                "method":      "POST",
                "format":      "CSV",
                "description": "Filtrlanган jonivorlar ro'yxati",
                "example":     {"status": "active", "species": "cattle"},
            },
            {
                "name":        "Jonivorlar Excel (B7)",
                "endpoint":    "/api/v1/export/animals/excel",
                "method":      "GET",
                "format":      "Excel (.xlsx)",
                "description": "Professional formatlangan Excel — 2 varaqli",
                "example":     "?status=active&species=cattle",
            },
            {
                "name":        "Deteksiyalar CSV",
                "endpoint":    "/api/v1/export/detections/csv",
                "method":      "POST",
                "format":      "CSV",
                "description": "Sana oralig'idagi deteksiya jurnali",
                "example":     {"date_from": "2026-02-01", "date_to": "2026-03-01"},
            },
            {
                "name":        "Og'irlik Excel",
                "endpoint":    "/api/v1/export/weights/excel",
                "method":      "POST",
                "format":      "Excel (.xlsx)",
                "description": "Ko'p varaqli og'irlik o'lchovlari",
                "example":     {"animal_ids": [1, 2, 3]},
            },
            {
                "name":        "To'liq Arxiv Excel",
                "endpoint":    "/api/v1/export/all/excel",
                "method":      "GET",
                "format":      "Excel (.xlsx)",
                "description": "4 varaqli to'liq ferma ma'lumotlari",
                "example":     {},
            },
        ]
    }