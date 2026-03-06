"""
Taurus Vision — Breeding & Genealogy API Endpoints (Sprint 25-26)

PREFIX: /api/v1/breeding

ENDPOINTLAR:
    POST   /breeding/records                          — Yangi nasl yozuvi
    GET    /breeding/records                          — Ro'yxat (filter + pagination)
    GET    /breeding/records/{id}                     — Detail
    PATCH  /breeding/records/{id}                     — Yangilash
    DELETE /breeding/records/{id}                     — O'chirish (MANAGER)

    POST   /breeding/records/{id}/confirm-pregnancy   — Homiladorlik tasdiqlash
    POST   /breeding/records/{id}/record-birth        — Tug'ilishni qayd etish
    POST   /breeding/records/{id}/mark-failed         — Muvaffaqiyatsiz belgilash
    POST   /breeding/records/{id}/mark-aborted        — Abort belgilash

    GET    /breeding/active-pregnancies               — Aktiv homiladorliklar
    GET    /breeding/due-soon                         — Yaqin tug'ilishlar
    GET    /breeding/stats                            — Statistika

    GET    /breeding/genealogy/{animal_id}            — Shajara daraxti
    GET    /breeding/animals/{animal_id}/history      — Jonivor nasl tarixi

    POST   /breeding/offspring/{id}/link-animal       — Nashlni jonivorgа bog'lash

    GET    /breeding/recommendations                  — AI juft tavsiyalari
    GET    /breeding/available-females                — Naslga tayyor onalar
    GET    /breeding/available-males                  — Naslga tayyor otalar

AUTH:
    GET   — CurrentUser (barcha autentifikatsiya qilinganlar)
    POST/PATCH/DELETE — CurrentManager (MANAGER + ADMIN)
"""

from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.api.v1.deps import CurrentUser, CurrentManager
from app.models.breeding import BreedingStatus
from app.services.breeding_service import BreedingService
from app.schemas.breeding import (
    BreedingRecordCreate,
    BreedingRecordUpdate,
    BreedingRecordResponse,
    BreedingRecordList,
    BreedingConfirmPregnancy,
    BreedingRecordBirth,
    BreedingMarkFailed,
    BreedingMarkAborted,
    OffspringLinkAnimal,
    OffspringResponse,
    GenealogyNode,
    BreedingStats,
    BreedingRecommendationList,
    AnimalBrief,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/breeding", tags=["Breeding & Genealogy"])


# =============================================================================
# HELPERS
# =============================================================================

def _svc(db: AsyncSession) -> BreedingService:
    return BreedingService(db)


# =============================================================================
# CREATE
# =============================================================================

@router.post(
    "/records",
    response_model=BreedingRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yangi nasl yozuvi yaratish",
    description=(
        "Juftlashish hodisasini qayd etish. "
        "Ona jonivor (female, active) va ota (ichki yoki tashqi) ko'rsatilishi shart. "
        "Gestatsiya muddati va kutilgan tug'ilish sanasi avtomatik hisoblanadi. "
        "**MANAGER** yoki **ADMIN** talab qilinadi."
    ),
)
async def create_breeding_record(
    data: BreedingRecordCreate,
    current_user: CurrentManager,
    db: AsyncSession = Depends(get_db),
) -> BreedingRecordResponse:
    svc = _svc(db)
    return await svc.create_record(data, created_by_id=current_user.id)


# =============================================================================
# LIST
# =============================================================================

@router.get(
    "/records",
    response_model=BreedingRecordList,
    summary="Nasl yozuvlari ro'yxati",
    description="Filter va sahifalash bilan barcha nasl yozuvlari.",
)
async def list_breeding_records(
    farm_id:      Optional[int]  = Query(None, description="Ferma bo'yicha filter"),
    status:       Optional[BreedingStatus] = Query(None),
    species:      Optional[str]  = Query(None, description="Tur: cattle, sheep, goat, horse"),
    mother_id:    Optional[int]  = Query(None),
    father_id:    Optional[int]  = Query(None),
    date_from:    Optional[date] = Query(None, description="Juftlashish sanasidan"),
    date_to:      Optional[date] = Query(None, description="Juftlashish sanasigacha"),
    overdue_only: bool           = Query(False, description="Faqat muddati o'tganlar"),
    page:         int            = Query(1, ge=1),
    size:         int            = Query(20, ge=1, le=100),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> BreedingRecordList:
    svc = _svc(db)
    return await svc.get_list(
        farm_id=farm_id,
        status=status,
        species=species,
        mother_id=mother_id,
        father_id=father_id,
        date_from=date_from,
        date_to=date_to,
        overdue_only=overdue_only,
        page=page,
        size=size,
    )


# =============================================================================
# DETAIL
# =============================================================================

@router.get(
    "/records/{record_id}",
    response_model=BreedingRecordResponse,
    summary="Nasl yozuvi detail",
)
async def get_breeding_record(
    record_id: int = Path(..., gt=0),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> BreedingRecordResponse:
    return await _svc(db).get_record(record_id)


# =============================================================================
# UPDATE
# =============================================================================

@router.patch(
    "/records/{record_id}",
    response_model=BreedingRecordResponse,
    summary="Nasl yozuvini yangilash",
)
async def update_breeding_record(
    data: BreedingRecordUpdate,
    record_id: int = Path(..., gt=0),
    current_user: CurrentManager = ...,
    db: AsyncSession = Depends(get_db),
) -> BreedingRecordResponse:
    return await _svc(db).update_record(record_id, data)


# =============================================================================
# DELETE
# =============================================================================

@router.delete(
    "/records/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Nasl yozuvini o'chirish (faqat PLANNED/FAILED)",
)
async def delete_breeding_record(
    record_id: int = Path(..., gt=0),
    current_user: CurrentManager = ...,
    db: AsyncSession = Depends(get_db),
) -> None:
    await _svc(db).delete_record(record_id)


# =============================================================================
# STATE TRANSITIONS
# =============================================================================

@router.post(
    "/records/{record_id}/confirm-pregnancy",
    response_model=BreedingRecordResponse,
    summary="Homiladorlikni tasdiqlash",
    description=(
        "PLANNED → CONFIRMED_PREGNANT. "
        "Ultratovush yoki qon tahlili natijasini qayd etish."
    ),
)
async def confirm_pregnancy(
    data: BreedingConfirmPregnancy,
    record_id: int = Path(..., gt=0),
    current_user: CurrentManager = ...,
    db: AsyncSession = Depends(get_db),
) -> BreedingRecordResponse:
    return await _svc(db).confirm_pregnancy(record_id, data)


@router.post(
    "/records/{record_id}/record-birth",
    response_model=BreedingRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Tug'ilishni qayd etish",
    description=(
        "→ BIRTHED. "
        "Har bir tug'ilgan jonivor uchun alohida OffspringRecord yaratiladi. "
        "Tirik va o'lik tug'ilganlar avtomatik sanaladi."
    ),
)
async def record_birth(
    data: BreedingRecordBirth,
    record_id: int = Path(..., gt=0),
    current_user: CurrentManager = ...,
    db: AsyncSession = Depends(get_db),
) -> BreedingRecordResponse:
    return await _svc(db).record_birth(record_id, data)


@router.post(
    "/records/{record_id}/mark-failed",
    response_model=BreedingRecordResponse,
    summary="Muvaffaqiyatsiz belgilash",
    description="Homiladorlik bo'lmadi — juftlashish natija bermadi.",
)
async def mark_failed(
    data: BreedingMarkFailed,
    record_id: int = Path(..., gt=0),
    current_user: CurrentManager = ...,
    db: AsyncSession = Depends(get_db),
) -> BreedingRecordResponse:
    return await _svc(db).mark_failed(record_id, data)


@router.post(
    "/records/{record_id}/mark-aborted",
    response_model=BreedingRecordResponse,
    summary="Abort belgilash",
)
async def mark_aborted(
    data: BreedingMarkAborted,
    record_id: int = Path(..., gt=0),
    current_user: CurrentManager = ...,
    db: AsyncSession = Depends(get_db),
) -> BreedingRecordResponse:
    return await _svc(db).mark_aborted(record_id, data)


# =============================================================================
# SPECIAL VIEWS
# =============================================================================

@router.get(
    "/active-pregnancies",
    response_model=List[BreedingRecordResponse],
    summary="Aktiv homiladorliklar",
    description="Hozir CONFIRMED_PREGNANT yoki PLANNED holatidagi barcha yozuvlar.",
)
async def get_active_pregnancies(
    farm_id: Optional[int] = Query(None),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> List[BreedingRecordResponse]:
    return await _svc(db).get_active_pregnancies(farm_id)


@router.get(
    "/due-soon",
    response_model=List[BreedingRecordResponse],
    summary="Yaqin tug'ilishlar",
)
async def get_due_soon(
    days:    int            = Query(14, ge=1, le=90, description="Kelgusi necha kun"),
    farm_id: Optional[int]  = Query(None),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> List[BreedingRecordResponse]:
    svc = _svc(db)
    records = await svc.repo.get_due_soon(db, days=days, farm_id=farm_id)
    return [svc._build_response(r) for r in records]


@router.get(
    "/stats",
    response_model=BreedingStats,
    summary="Nasl statistikasi",
    description="Homiladorlik, tug'ilish, muvaffaqiyat ko'rsatkichlari.",
)
async def get_stats(
    farm_id: Optional[int] = Query(None),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> BreedingStats:
    return await _svc(db).get_stats(farm_id)


# =============================================================================
# GENEALOGY
# =============================================================================

@router.get(
    "/genealogy/{animal_id}",
    response_model=GenealogyNode,
    summary="Shajara daraxti",
    description=(
        "Jonivorning ota-ona zanjirini ko'rsatadi. "
        "`max_generations` parametri bilan chuqurlikni belgilang (1-5). "
        "Tashqi otalar ham ko'rsatiladi."
    ),
)
async def get_genealogy(
    animal_id:       int = Path(..., gt=0),
    max_generations: int = Query(3, ge=1, le=5),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> GenealogyNode:
    return await _svc(db).get_genealogy(animal_id, max_generations)


@router.get(
    "/animals/{animal_id}/history",
    response_model=List[BreedingRecordResponse],
    summary="Jonivorning nasl tarixi",
    description="Ushbu jonivor ona yoki ota sifatida ishtirok etgan barcha yozuvlar.",
)
async def get_animal_breeding_history(
    animal_id:    int = Path(..., gt=0),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> List[BreedingRecordResponse]:
    return await _svc(db).get_animal_breeding_history(animal_id)


# =============================================================================
# OFFSPRING
# =============================================================================

@router.post(
    "/offspring/{offspring_id}/link-animal",
    response_model=OffspringResponse,
    summary="Nashlni ro'yxatdagi jonivorgа bog'lash",
    description=(
        "Tug'ilgan naslning animal_id sini belgilash. "
        "Avval animals jadvalida jonivor ro'yxatdan o'tishi kerak."
    ),
)
async def link_offspring_to_animal(
    data: OffspringLinkAnimal,
    offspring_id: int = Path(..., gt=0),
    current_user: CurrentManager = ...,
    db: AsyncSession = Depends(get_db),
) -> OffspringResponse:
    return await _svc(db).link_offspring_to_animal(offspring_id, data.animal_id)


# =============================================================================
# RECOMMENDATIONS
# =============================================================================

@router.get(
    "/recommendations",
    response_model=BreedingRecommendationList,
    summary="AI juft tavsiyalari",
    description=(
        "Mavjud urg'ochi va erkak jonivorlar orasidan optimal juftlarni tavsiya qiladi. "
        "Genetik xilma-xillik, ADI ko'rsatkichlari, vazn nisbati va zot uyg'unligi "
        "asosida 100 ballik tizimda baholanadi."
    ),
)
async def get_recommendations(
    farm_id: Optional[int] = Query(None),
    species: Optional[str] = Query(None, description="cattle | sheep | goat | horse"),
    top_n:   int           = Query(10, ge=1, le=50),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> BreedingRecommendationList:
    return await _svc(db).get_recommendations(farm_id, species, top_n)


@router.get(
    "/available-females",
    response_model=List[AnimalBrief],
    summary="Naslga tayyor urg'ochi jonivorlar",
    description="Aktiv, urg'ochi va hozir homilador bo'lmagan jonivorlar.",
)
async def get_available_females(
    farm_id: Optional[int] = Query(None),
    species: Optional[str] = Query(None),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> List[AnimalBrief]:
    svc = _svc(db)
    animals = await svc.repo.get_available_females(db, farm_id, species)
    return [
        AnimalBrief(
            id=a.id, tag_id=a.tag_id, species=a.species.value,
            breed=a.breed, gender=a.gender.value, status=a.status.value,
        )
        for a in animals
    ]


@router.get(
    "/available-males",
    response_model=List[AnimalBrief],
    summary="Naslga tayyor erkak jonivorlar",
)
async def get_available_males(
    farm_id: Optional[int] = Query(None),
    species: Optional[str] = Query(None),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> List[AnimalBrief]:
    svc = _svc(db)
    animals = await svc.repo.get_available_males(db, farm_id, species)
    return [
        AnimalBrief(
            id=a.id, tag_id=a.tag_id, species=a.species.value,
            breed=a.breed, gender=a.gender.value, status=a.status.value,
        )
        for a in animals
    ]