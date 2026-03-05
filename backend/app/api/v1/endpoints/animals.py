"""
Taurus Vision — Animals API Endpoints

ENDPOINTLAR:
    POST   /animals/                   — Yangi jonivor yaratish
    GET    /animals/                   — Sahifalangan ro'yxat
    GET    /animals/search             — Ko'p maydonli qidirish
    GET    /animals/search/text        — Oddiy matn qidirish
    GET    /animals/import/template    — CSV namuna faylni yuklab olish       [B6]
    POST   /animals/import/csv         — CSV orqali ommaviy import            [B6]
    GET    /animals/tag/{tag_id}       — Tag ID bo'yicha olish
    GET    /animals/{animal_id}        — ID bo'yicha olish
    PATCH  /animals/{animal_id}        — Yangilash
    DELETE /animals/{animal_id}        — O'chirish
    GET    /animals/{animal_id}/detections — Deteksiya tarixi

AUTENTIFIKATSIYA:
    Barcha endpointlar: VIEWER+ (get_current_active_user)
    Yaratish/yangilash/o'chirish: MANAGER+ (require_manager)
    CSV import: MANAGER+ (require_manager)

ARXITEKTURA:
    HTTP → Endpoint → Service → Repository → DB
    Endpoint faqat HTTP: request/response, status kodlar, xatolarni HTTP ga aylantirish.
    Biznes logika yo'q.
"""

from __future__ import annotations

from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_active_user, require_manager
from app.core.database import get_db
from app.core.exceptions import (
    BusinessRuleViolationError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
)
from app.core.logging_config import get_logger
from app.models.animal import AnimalSpecies, AnimalStatus
from app.schemas.animal import (
    AnimalCreate,
    AnimalListResponse,
    AnimalResponse,
    AnimalUpdate,
    BulkImportResponse,
    generate_csv_template,
)
from app.services.animal import AnimalService

logger = get_logger(__name__)

# CSV fayl uchun ruxsat etilgan MIME turlari
_ALLOWED_CSV_MIME = {
    "text/csv",
    "text/plain",
    "application/csv",
    "application/octet-stream",
    "application/vnd.ms-excel",
}

# CSV import uchun maksimal fayl hajmi: 2 MB
_MAX_CSV_SIZE_BYTES = 2 * 1024 * 1024


router = APIRouter(
    prefix="/animals",
    tags=["Animals"],
    redirect_slashes=False,
    dependencies=[Depends(get_current_active_user)],
)


# =============================================================================
# DEPENDENCY
# =============================================================================

def _get_service(db: AsyncSession = Depends(get_db)) -> AnimalService:
    """
    AnimalService dependency injection.

    Har bir so'rov uchun yangi service instance qaytaradi.
    """
    return AnimalService(db)


# =============================================================================
# YORDAMCHI FUNKSIYALAR
# =============================================================================

def _http_from_service_error(exc: Exception) -> HTTPException:
    """
    Service qatlami xatolarini HTTP istisnolariga aylantiradi.

    Endpoint larda takroriy try/except blokidan qochish uchun.
    """
    if isinstance(exc, EntityNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        )
    if isinstance(exc, EntityAlreadyExistsError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        )
    if isinstance(exc, BusinessRuleViolationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        )
    # Kutilmagan xato
    logger.error(f"[endpoint] Kutilmagan xato: {exc}", exc_info=True)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Ichki server xatosi",
    )


# =============================================================================
# CREATE
# =============================================================================

@router.post(
    "/",
    response_model=AnimalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yangi jonivor yaratish",
    description="""
    Yangi jonivor yozuvini yaratadi.

    **Biznes qoidalar:**
    - Tag ID noyob bo'lishi kerak (katta/kichik harfga sezgir emas)
    - Tag ID avtomatik katta harfga o'tkaziladi
    - Tug'ilgan sana kelajakda bo'lishi mumkin emas
    - Sotib olish sanasi kelajakda bo'lishi mumkin emas
    """,
    responses={
        201: {"description": "Muvaffaqiyatli yaratildi"},
        409: {"description": "Bu tag ID allaqachon mavjud"},
        422: {"description": "Validatsiya xatosi"},
    },
    dependencies=[Depends(require_manager)],
)
async def create_animal(
    animal_data: AnimalCreate,
    service: AnimalService = Depends(_get_service),
) -> AnimalResponse:
    """Yangi jonivor yaratadi va 201 bilan qaytaradi."""
    try:
        return await service.create_animal(animal_data)
    except (EntityAlreadyExistsError, BusinessRuleViolationError) as exc:
        raise _http_from_service_error(exc)


# =============================================================================
# CSV OMMAVIY IMPORT (B6)
# =============================================================================

@router.get(
    "/import/template",
    summary="CSV namuna shablon yuklab olish",
    description="""
    Foydalanuvchi to'ldirishi uchun namuna CSV faylni qaytaradi.

    **Ustunlar:**
    | Ustun            | Majburiy | Tavsif                                      |
    |------------------|----------|---------------------------------------------|
    | tag_id           | ✅ Ha    | Noyob identifikator (masalan: JNV-001)      |
    | species          | ✅ Ha    | cattle / sheep / goat / horse / other       |
    | breed            | ❌ Yo'q  | Zot nomi                                    |
    | gender           | ❌ Yo'q  | male / female / unknown (default: unknown)  |
    | birth_date       | ❌ Yo'q  | YYYY-MM-DD formatida                        |
    | acquisition_date | ❌ Yo'q  | YYYY-MM-DD (default: bugungi sana)          |
    | status           | ❌ Yo'q  | active / sick / quarantine (default: active)|
    | notes            | ❌ Yo'q  | Erkin matn izoh                             |
    """,
    responses={
        200: {
            "description": "CSV namuna fayl",
            "content": {"text/csv": {}},
        }
    },
)
async def download_csv_template() -> Response:
    """
    Foydalanuvchi to'ldirishi uchun namuna CSV faylini qaytaradi.

    Frontend da "Shablonni yuklab olish" tugmasi shu endpointni chaqiradi.
    """
    csv_content = generate_csv_template()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=animals_import_template.csv",
            "Content-Length": str(len(csv_content.encode("utf-8"))),
        },
    )


@router.post(
    "/import/csv",
    response_model=BulkImportResponse,
    status_code=status.HTTP_200_OK,
    summary="CSV orqali ko'p jonivorni birdaniga import qilish",
    description="""
    CSV fayl yuklash orqali bir vaqtda ko'p jonivorni qo'shadi.

    **CSV formati:**
    - Sarlavha satri majburiy
    - Majburiy ustunlar: `tag_id`, `species`
    - Qolgan ustunlar ixtiyoriy

    **Import xulqi:**
    - Har bir satr mustaqil tekshiriladi
    - Bitta satr xatosi butun importni to'xtatmaydi
    - `skip_duplicates=true`: mavjud tag_id lar o'tkazib yuboriladi
    - `skip_duplicates=false`: mavjud tag_id lar xato sifatida qaytariladi
    - Maksimal: 1000 satr, 2 MB

    **Javob:**
    Har bir satr uchun natija: `created` | `skipped` | `error`

    **CSV namunasini yuklab olish:**
    `GET /animals/import/template`
    """,
    responses={
        200: {"description": "Import natijasi (xatolar bo'lsa ham 200 qaytariladi)"},
        400: {"description": "Fayl yuborilmagan yoki noto'g'ri format"},
        422: {"description": "CSV tuzilmasi noto'g'ri (sarlavha xato va h.k.)"},
    },
    dependencies=[Depends(require_manager)],
)
async def import_animals_csv(
    file: UploadFile = File(
        ...,
        description="CSV fayl (.csv, max 2MB)",
    ),
    skip_duplicates: bool = Query(
        default=True,
        description=(
            "True — mavjud tag_id larni o'tkazib yuborish (default), "
            "False — xato sifatida belgilash"
        ),
    ),
    service: AnimalService = Depends(_get_service),
) -> BulkImportResponse:
    """
    CSV fayldan jonivornlarni ommaviy import qiladi.

    Args:
        file:             Multipart/form-data orqali yuklangan CSV fayl
        skip_duplicates:  Takroriy tag_id lar uchun xulq
        service:          Injected AnimalService

    Returns:
        BulkImportResponse — batafsil natija (created/skipped/errors/per-row details)
    """
    # ------------------------------------------------------------------
    # Fayl validatsiyasi
    # ------------------------------------------------------------------
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fayl nomi bo'sh. Iltimos, CSV fayl tanlang.",
        )

    # Kengaytmani tekshirish
    filename_lower = file.filename.lower()
    if not filename_lower.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Noto'g'ri fayl kengaytmasi: '{file.filename}'. "
                "Faqat .csv kengaytmali fayllar qabul qilinadi."
            ),
        )

    # MIME turini tekshirish (content_type None bo'lishi mumkin)
    if file.content_type and file.content_type not in _ALLOWED_CSV_MIME:
        logger.warning(
            f"[endpoint] CSV import: noto'g'ri MIME turi: {file.content_type}"
        )
        # Faqat ogohlantirish — ba'zi browserlar boshqa MIME yuborishi mumkin

    # Faylni o'qish
    try:
        raw_bytes = await file.read()
    except Exception as exc:
        logger.error(f"[endpoint] Faylni o'qishda xato: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faylni o'qib bo'lmadi. Iltimos, qayta urinib ko'ring.",
        )

    # Hajmini tekshirish
    if len(raw_bytes) > _MAX_CSV_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Fayl hajmi juda katta: "
                f"{len(raw_bytes) / 1024 / 1024:.1f} MB. "
                f"Maksimal ruxsat etilgan hajm: 2 MB."
            ),
        )

    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yuklangan fayl bo'sh.",
        )

    # Baytlarni matn ga aylantirish
    try:
        csv_content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            csv_content = raw_bytes.decode("utf-8-sig")  # BOM bilan UTF-8 (Excel)
        except UnicodeDecodeError:
            try:
                csv_content = raw_bytes.decode("cp1251")  # Windows Kirill
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Fayl kodlash xatosi. "
                        "Iltimos, faylni UTF-8 kodlashda saqlang."
                    ),
                )

    logger.info(
        f"[endpoint] CSV import so'rovi: fayl='{file.filename}', "
        f"hajm={len(raw_bytes)} bayt, skip_duplicates={skip_duplicates}"
    )

    # ------------------------------------------------------------------
    # Service ga topshirish
    # ------------------------------------------------------------------
    try:
        result = await service.import_from_csv(
            csv_content=csv_content,
            skip_duplicates=skip_duplicates,
        )
    except BusinessRuleViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        )
    except Exception as exc:
        logger.error(f"[endpoint] import_from_csv kutilmagan xato: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Import jarayonida kutilmagan xato yuz berdi.",
        )

    logger.info(
        f"[endpoint] CSV import yakunlandi: "
        f"yaratildi={result.created}, "
        f"o'tkazildi={result.skipped}, "
        f"xato={result.errors}"
    )
    return result


# =============================================================================
# READ — QIDIRUV
# =============================================================================

@router.get(
    "/search",
    response_model=list[AnimalResponse],
    summary="Ko'p maydonli qidirish",
    description="""
    Bir nechta filtr, saralash va sahifalash bilan kengaytirilgan qidirish.

    **Filtrlar:** tag_id, species, gender, status, breed, min_detections, search_text

    **Saralash:** tag_id | species | status | total_detections | last_detected_at

    **Misol:**
    ```
    GET /api/v1/animals/search?species=cattle&status=active&sort_by=total_detections&sort_order=desc
    ```
    """,
)
async def search_animals(
    tag_id: Optional[str] = Query(None, description="Tag ID bo'yicha (qisman mos)"),
    species: Optional[str] = Query(None, description="Tur: cattle/sheep/goat/horse/other"),
    gender: Optional[str] = Query(None, description="Jins: male/female/unknown"),
    status: Optional[str] = Query(None, description="Holat: active/sick/quarantine/sold/deceased"),
    breed: Optional[str] = Query(None, description="Zot (qisman mos)"),
    min_detections: Optional[int] = Query(None, ge=0, description="Minimal deteksiya soni"),
    search_text: Optional[str] = Query(None, description="Matn qidirish (tag_id, breed, notes)"),
    sort_by: str = Query(
        "tag_id",
        description="Saralash maydoni",
        pattern="^(tag_id|species|status|total_detections|last_detected_at)$",
    ),
    sort_order: str = Query("asc", description="Saralash yo'nalishi", pattern="^(asc|desc)$"),
    skip: int = Query(0, ge=0, description="Sahifalash ofset"),
    limit: int = Query(20, ge=1, le=100, description="Maksimal natijalar soni"),
    db: AsyncSession = Depends(get_db),
) -> list[AnimalResponse]:
    """Ko'p maydonli qidirish."""
    from app.repositories.animal import AnimalRepository

    try:
        species_enum = AnimalSpecies(species.lower()) if species else None
        status_enum = AnimalStatus(status.lower()) if status else None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Noto'g'ri filtr qiymati: {exc}",
        )

    repo = AnimalRepository(db)
    animals, _ = await repo.advanced_search(
        tag_id=tag_id,
        species=species_enum,
        gender=gender,
        status=status_enum,
        breed=breed,
        min_detections=min_detections,
        search_text=search_text,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=skip,
        limit=limit,
    )
    return [AnimalResponse.model_validate(a) for a in animals]


@router.get(
    "/search/text",
    response_model=list[AnimalResponse],
    summary="Oddiy matn qidirish",
    description="""
    tag_id, breed va notes bo'yicha oddiy matn qidirish.

    Qidiruvlar, autocomplete uchun mos.
    Kengaytirilgan qidirish uchun `/search` endpointni ishlating.
    """,
)
async def text_search_animals(
    q: str = Query(..., min_length=1, description="Qidiruv matni"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[AnimalResponse]:
    """Matn bo'yicha qidirish."""
    from app.repositories.animal import AnimalRepository

    repo = AnimalRepository(db)
    animals, _ = await repo.search_by_text(search_text=q, skip=skip, limit=limit)
    return [AnimalResponse.model_validate(a) for a in animals]


# =============================================================================
# READ — yagona
# =============================================================================

@router.get(
    "/tag/{tag_id}",
    response_model=AnimalResponse,
    summary="Tag ID bo'yicha olish",
    description="Tag identifikatori bo'yicha bitta jonivorni qaytaradi (katta/kichik harfga sezgir emas).",
    responses={
        200: {"description": "Jonivor topildi"},
        404: {"description": "Jonivor topilmadi"},
    },
)
async def get_animal_by_tag(
    tag_id: str,
    service: AnimalService = Depends(_get_service),
) -> AnimalResponse:
    """Tag ID bo'yicha jonivor qaytaradi."""
    try:
        return await service.get_animal_by_tag(tag_id)
    except EntityNotFoundError as exc:
        raise _http_from_service_error(exc)


@router.get(
    "/{animal_id}",
    response_model=AnimalResponse,
    summary="ID bo'yicha olish",
    responses={
        200: {"description": "Jonivor topildi"},
        404: {"description": "Jonivor topilmadi"},
    },
)
async def get_animal(
    animal_id: int,
    service: AnimalService = Depends(_get_service),
) -> AnimalResponse:
    """PK bo'yicha bitta jonivorni qaytaradi."""
    try:
        return await service.get_animal(animal_id)
    except EntityNotFoundError as exc:
        raise _http_from_service_error(exc)


@router.get(
    "/",
    response_model=AnimalListResponse,
    summary="Barcha jonivornlar ro'yxati",
    description="""
    Sahifalangan va filtrlangan ro'yxatni qaytaradi.

    **Filtrlar:** species, status
    **Sahifalash:** skip, limit (max 100)
    """,
)
async def list_animals(
    skip: int = Query(0, ge=0, description="Ofset"),
    limit: int = Query(10, ge=1, le=100, description="Sahifa hajmi"),
    species: Optional[str] = Query(None, description="Tur filtri"),
    status: Optional[str] = Query(None, description="Holat filtri"),
    service: AnimalService = Depends(_get_service),
) -> AnimalListResponse:
    """Sahifalangan jonivorlar ro'yxatini qaytaradi."""
    return await service.get_animals(
        skip=skip,
        limit=limit,
        species=species,
        status=status,
    )


# =============================================================================
# UPDATE
# =============================================================================

@router.patch(
    "/{animal_id}",
    response_model=AnimalResponse,
    summary="Jonivorni yangilash",
    description="""
    Jonivorni qisman yangilaydi (PATCH semantikasi).

    **Biznes qoidalar:**
    - Faqat yuborilgan maydonlar o'zgaradi
    - Arxivlangan jonivornlarni (SOLD, DECEASED) o'zgartirish mumkin emas
    - Yangi tag_id noyob bo'lishi kerak
    """,
    responses={
        200: {"description": "Muvaffaqiyatli yangilandi"},
        404: {"description": "Topilmadi"},
        409: {"description": "Tag ID konflikti"},
        422: {"description": "Biznes qoidasi buzildi"},
    },
    dependencies=[Depends(require_manager)],
)
async def update_animal(
    animal_id: int,
    update_data: AnimalUpdate,
    service: AnimalService = Depends(_get_service),
) -> AnimalResponse:
    """Mavjud jonivorni yangilaydi."""
    try:
        return await service.update_animal(animal_id, update_data)
    except (EntityNotFoundError, EntityAlreadyExistsError, BusinessRuleViolationError) as exc:
        raise _http_from_service_error(exc)


# =============================================================================
# DELETE
# =============================================================================

@router.delete(
    "/{animal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Jonivorni o'chirish",
    description="""
    Jonivorni to'liq o'chiradi.

    **Biznes qoidasi:**
    Arxivlangan jonivornlarni (SOLD, DECEASED) o'chirib bo'lmaydi —
    audit izi uchun saqlanishi shart.
    """,
    responses={
        204: {"description": "O'chirildi"},
        404: {"description": "Topilmadi"},
        422: {"description": "Arxivlangan jonivorni o'chirish mumkin emas"},
    },
    dependencies=[Depends(require_manager)],
)
async def delete_animal(
    animal_id: int,
    service: AnimalService = Depends(_get_service),
) -> None:
    """Jonivorni o'chiradi. Muvaffaqiyatli bo'lsa 204 qaytaradi."""
    try:
        await service.delete_animal(animal_id)
    except (EntityNotFoundError, BusinessRuleViolationError) as exc:
        raise _http_from_service_error(exc)


# =============================================================================
# DETEKSIYA TARIXI
# =============================================================================

@router.get(
    "/{animal_id}/detections",
    summary="Jonivorning deteksiya tarixi",
    description="Belgilangan jonivor uchun so'nggi YOLO deteksiyalarini qaytaradi.",
)
async def get_animal_detections(
    animal_id: int,
    limit: int = Query(default=20, ge=1, le=200, description="Maksimal yozuvlar soni"),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    Bitta jonivor uchun deteksiya yozuvlarini qaytaradi (yangi → eski).

    Args:
        animal_id: Jonivor PK si
        limit:     Maksimal yozuvlar soni (default: 20, max: 200)
        db:        DB sessiya

    Returns:
        Deteksiya dict lari ro'yxati:
        id, camera_id, timestamp, confidence, class_name, bbox
    """
    from sqlalchemy import desc, select

    from app.models.animal import Animal
    from app.models.detection import Detection

    animal = await db.scalar(select(Animal).where(Animal.id == animal_id))
    if not animal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ID {animal_id} li jonivor topilmadi",
        )

    result = await db.execute(
        select(Detection)
        .where(Detection.animal_id == animal_id)
        .order_by(desc(Detection.timestamp))
        .limit(limit)
    )
    rows = result.scalars().all()

    return [
        {
            "id": d.id,
            "camera_id": d.camera_id,
            "timestamp": d.timestamp.isoformat(),
            "confidence": round(d.confidence, 3),
            "class_name": d.class_name,
            "bbox": d.bbox,
        }
        for d in rows
    ]