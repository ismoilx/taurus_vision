"""
Taurus Vision — Animal Pydantic Schemas

Barcha Animal API request/response sxemalari shu yerda.
3 qatlamli arxitekturada bu fayl Endpoint ↔ Service o'rtasidagi
shartnoma hisoblanadi.

SXEMALAR:
    AnimalBase          — Umumiy maydonlar + validatorlar
    AnimalCreate        — POST /animals/ uchun
    AnimalUpdate        — PATCH /animals/{id} uchun (hamma maydon optional)
    AnimalResponse      — Barcha GET javoblari uchun
    AnimalListResponse  — Paginated ro'yxat uchun

    AnimalImportRow     — CSV bir satr uchun (import)
    BulkImportRowResult — Har bir satr natijasi
    BulkImportResponse  — POST /animals/import/csv javobi
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.models.animal import AnimalGender, AnimalSpecies, AnimalStatus


# =============================================================================
# HELPERS
# =============================================================================

def _ensure_naive_utc(v: Any) -> Any:
    """
    Vaqtni timezone-aware dan naive UTC ga o'tkazadi.

    SQLAlchemy naive datetime saqlaydi, Pydantic esa aware qaytarishi
    mumkin — bu funksiya ikki tomonni moslashtiradi.
    """
    if isinstance(v, datetime) and v.tzinfo is not None:
        return v.astimezone(timezone.utc).replace(tzinfo=None)
    return v


# =============================================================================
# BASE
# =============================================================================

class AnimalBase(BaseModel):
    """Barcha hayvon sxemalari uchun asosiy model."""

    tag_id: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Noyob identifikator (masalan: JNV-001)",
        examples=["JNV-001"],
    )
    species: AnimalSpecies = Field(..., description="Tur (cattle / sheep / goat / horse / other)")
    breed: Optional[str] = Field(None, max_length=100, description="Zot nomi")
    gender: AnimalGender = Field(default=AnimalGender.UNKNOWN, description="Jins")
    birth_date: Optional[datetime] = Field(None, description="Tug'ilgan sana (ISO-8601)")
    acquisition_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        description="Xo'jalikka qo'shilgan sana",
    )
    status: AnimalStatus = Field(default=AnimalStatus.ACTIVE, description="Joriy holat")
    notes: Optional[str] = Field(None, max_length=1000, description="Qo'shimcha izoh")
    profile_image: Optional[str] = Field(None, description="Profil rasmi URL")

    # ------------------------------------------------------------------
    # VALIDATORS
    # ------------------------------------------------------------------

    @field_validator("tag_id", mode="before")
    @classmethod
    def validate_tag_id(cls, v: Any) -> Any:
        """Tag IDni trim qiladi, katta harfga o'tkazadi va formatini tekshiradi."""
        if not isinstance(v, str):
            return v
        v = v.strip().upper()
        if not all(c.isalnum() or c == "-" for c in v):
            raise ValueError(
                "Tag ID faqat harf, raqam va chiziqcha (-) dan iborat bo'lishi kerak"
            )
        return v

    @field_validator("birth_date", "acquisition_date", mode="before")
    @classmethod
    def validate_dates(cls, v: Any) -> Optional[datetime]:
        """Kelajakdagi sanani rad etadi va naive UTC ga keltiradi.

        mode="before" — Pydantic parse qilishdan OLDIN chaqiriladi,
        shuning uchun v string yoki datetime bo'lishi mumkin.
        """
        if v is None or v == "":
            return None
        # String kelsa — datetime ga parse qilamiz
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
                try:
                    v = datetime.strptime(v, fmt)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError(f"Sana formati noto'g'ri: '{v}'. To'g'ri format: YYYY-MM-DD")
        if not isinstance(v, datetime):
            raise ValueError(f"Sana datetime yoki string bo'lishi kerak, {type(v).__name__} emas")
        v_naive = _ensure_naive_utc(v)
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        if v_naive > now_naive:
            raise ValueError("Sana kelajakda bo'lishi mumkin emas")
        return v_naive


# =============================================================================
# CREATE / UPDATE
# =============================================================================

class AnimalCreate(AnimalBase):
    """Yangi jonivor yaratish uchun sxema (POST /animals/)."""
    pass


class AnimalUpdate(BaseModel):
    """
    Jonivorni yangilash uchun sxema (PATCH /animals/{id}).

    Hamma maydonlar optional — faqat yuborilgan maydonlar o'zgaradi.
    """

    tag_id: Optional[str] = Field(None, min_length=3, max_length=50)
    species: Optional[AnimalSpecies] = None
    breed: Optional[str] = Field(None, max_length=100)
    gender: Optional[AnimalGender] = None
    birth_date: Optional[datetime] = None
    acquisition_date: Optional[datetime] = None
    status: Optional[AnimalStatus] = None
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("tag_id", mode="before")
    @classmethod
    def _validate_tag(cls, v: Any) -> Any:
        return AnimalBase.validate_tag_id(v)

    @field_validator("birth_date", "acquisition_date", mode="before")
    @classmethod
    def _validate_dates(cls, v: Optional[datetime]) -> Optional[datetime]:
        return AnimalBase.validate_dates(v)


# =============================================================================
# RESPONSE
# =============================================================================

class AnimalPhotoResponse(BaseModel):
    """Rasm galereyasi uchun schema."""
    id:         int
    file_name:  str
    file_size:  Optional[int] = None
    url:        str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("created_at", mode="before")
    @classmethod
    def _norm(cls, v: Any) -> Any:
        return _ensure_naive_utc(v)


class AnimalResponse(AnimalBase):
    """
    API javobi uchun sxema.

    Barcha DB maydonlari kiritilgan: id, deteksiya statistikasi,
    yaratilgan/yangilangan vaqtlar.
    """

    id: int
    profile_image: Optional[str] = None
    muzzle_image: Optional[str] = None
    photos: list[AnimalPhotoResponse] = []
    first_detected_at: Optional[datetime] = None
    last_detected_at: Optional[datetime] = None
    total_detections: int = 0
    created_at: datetime
    updated_at: datetime

    @field_validator(
        "birth_date",
        "acquisition_date",
        "created_at",
        "updated_at",
        "first_detected_at",
        "last_detected_at",
        mode="before",
    )
    @classmethod
    def _normalize_dates(cls, v: Any) -> Any:
        return _ensure_naive_utc(v)

    model_config = ConfigDict(from_attributes=True)


class AnimalListResponse(BaseModel):
    """Sahifalangan ro'yxat uchun javob sxemasi."""

    items: list[AnimalResponse]
    total: int
    skip: int
    limit: int


# =============================================================================
# CSV BULK IMPORT
# =============================================================================

class AnimalImportRow(BaseModel):
    """
    CSV bir satrini ifodalaydi.

    CSV ustunlari (tartib muhim emas, sarlavhaga qarab o'qiladi):
        tag_id           — Majburiy. Noyob identifikator (JNV-001)
        species          — Majburiy. cattle | sheep | goat | horse | other
        breed            — Ixtiyoriy. Zot nomi
        gender           — Ixtiyoriy. male | female | unknown (default: unknown)
        birth_date       — Ixtiyoriy. YYYY-MM-DD yoki YYYY-MM-DDTHH:MM:SS
        acquisition_date — Ixtiyoriy. YYYY-MM-DD (default: bugun)
        status           — Ixtiyoriy. active | sick | quarantine | ... (default: active)
        notes            — Ixtiyoriy. Erkin matn

    NAMUNA CSV:
        tag_id,species,breed,gender,birth_date,acquisition_date,status,notes
        JNV-001,cattle,Holstein,female,2022-03-15,2023-01-10,active,Yuqori sut beruvchi
        QOY-042,sheep,,male,2023-08-20,,active,
    """

    tag_id: str = Field(..., min_length=3, max_length=50)
    species: AnimalSpecies
    breed: Optional[str] = Field(None, max_length=100)
    gender: AnimalGender = AnimalGender.UNKNOWN
    birth_date: Optional[datetime] = None
    acquisition_date: Optional[datetime] = None
    status: AnimalStatus = AnimalStatus.ACTIVE
    notes: Optional[str] = Field(None, max_length=1000)

    # ------------------------------------------------------------------
    # VALIDATORS (CSV dan keladigan string qiymatlarni normalize qiladi)
    # ------------------------------------------------------------------

    @field_validator("tag_id", mode="before")
    @classmethod
    def _clean_tag(cls, v: Any) -> Any:
        if not isinstance(v, str):
            raise ValueError("tag_id matn bo'lishi kerak")
        v = v.strip().upper()
        if not v:
            raise ValueError("tag_id bo'sh bo'lishi mumkin emas")
        if not all(c.isalnum() or c == "-" for c in v):
            raise ValueError("tag_id faqat harf, raqam va '-' dan iborat bo'lishi kerak")
        return v

    @field_validator("species", mode="before")
    @classmethod
    def _clean_species(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip().lower()
            if not v:
                raise ValueError("species bo'sh bo'lishi mumkin emas")
        return v

    @field_validator("gender", mode="before")
    @classmethod
    def _clean_gender(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip().lower()
            return v if v else AnimalGender.UNKNOWN
        return v

    @field_validator("status", mode="before")
    @classmethod
    def _clean_status(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip().lower()
            return v if v else AnimalStatus.ACTIVE
        return v

    @field_validator("birth_date", "acquisition_date", mode="before")
    @classmethod
    def _parse_date(cls, v: Any) -> Optional[datetime]:
        """
        CSV dan kelgan sana qatorini datetime ga o'tkazadi.

        Qabul qilinadigan formatlar:
            YYYY-MM-DD
            YYYY-MM-DDTHH:MM:SS
            YYYY-MM-DD HH:MM:SS
        """
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if isinstance(v, datetime):
            return _ensure_naive_utc(v)
        if isinstance(v, str):
            v = v.strip()
            for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
            raise ValueError(
                f"Sana formati noto'g'ri: '{v}'. "
                "To'g'ri format: YYYY-MM-DD (masalan: 2023-06-15)"
            )
        raise ValueError(f"Kutilmagan sana qiymati: {v!r}")

    @field_validator("notes", "breed", mode="before")
    @classmethod
    def _clean_optional_str(cls, v: Any) -> Optional[str]:
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v

    def to_animal_create(self) -> AnimalCreate:
        """
        AnimalImportRow ni AnimalCreate ga o'tkazadi.

        acquisition_date bo'sh bo'lsa bugungi sana qo'yiladi.
        """
        from datetime import timezone

        acq = self.acquisition_date or datetime.now(timezone.utc).replace(tzinfo=None)

        return AnimalCreate(
            tag_id=self.tag_id,
            species=self.species,
            breed=self.breed,
            gender=self.gender,
            birth_date=self.birth_date,
            acquisition_date=acq,
            status=self.status,
            notes=self.notes,
        )


class BulkImportRowResult(BaseModel):
    """Bitta CSV satr import natijasi."""

    row: int = Field(..., description="CSV da satr raqami (1 dan boshlanadi, sarlavha hisoblanmaydi)")
    tag_id: Optional[str] = Field(None, description="Satrdan olingan tag_id (agar o'qilgan bo'lsa)")
    status: str = Field(
        ...,
        description="created | skipped | error",
        pattern="^(created|skipped|error)$",
    )
    animal_id: Optional[int] = Field(None, description="Yaratilgan jonivor ID si (faqat status=created)")
    message: str = Field(..., description="Natija tavsifi yoki xato matni")


class BulkImportResponse(BaseModel):
    """
    POST /animals/import/csv — to'liq javob.

    Ferma egasi nechta yaratildi, nechta o'tkazib yuborildi
    va qayerlarda xato borligini bir ko'rishda biladi.
    """

    total_rows: int = Field(..., description="CSV dagi jami ma'lumot satrlari (sarlavhasiz)")
    created: int = Field(..., description="Muvaffaqiyatli yaratilganlar soni")
    skipped: int = Field(..., description="O'tkazib yuborilganlar (takroriy tag_id)")
    errors: int = Field(..., description="Xatolar soni")
    results: list[BulkImportRowResult] = Field(..., description="Har bir satr uchun natija")

    @classmethod
    def build(
        cls,
        results: list[BulkImportRowResult],
    ) -> "BulkImportResponse":
        """results ro'yxatidan to'liq javob ob'ektini quradi."""
        return cls(
            total_rows=len(results),
            created=sum(1 for r in results if r.status == "created"),
            skipped=sum(1 for r in results if r.status == "skipped"),
            errors=sum(1 for r in results if r.status == "error"),
            results=results,
        )


# =============================================================================
# CSV TEMPLATE HELPER
# =============================================================================

IMPORT_CSV_HEADERS = [
    "tag_id",
    "species",
    "breed",
    "gender",
    "birth_date",
    "acquisition_date",
    "status",
    "notes",
]

IMPORT_CSV_EXAMPLE_ROWS = [
    [
        "JNV-001", "cattle", "Holstein", "female",
        "2022-03-15", "2023-01-10", "active", "Yuqori sut beruvchi",
    ],
    [
        "QOY-042", "sheep", "", "male",
        "2023-08-20", "", "active", "",
    ],
    [
        "ECHKI-07", "goat", "Zanen", "female",
        "2021-11-05", "2022-04-18", "active", "",
    ],
]


def generate_csv_template() -> str:
    """
    Foydalanuvchiga yuklab olish uchun namuna CSV matnini qaytaradi.

    Frontend dan: GET /animals/import/template
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(IMPORT_CSV_HEADERS)
    writer.writerows(IMPORT_CSV_EXAMPLE_ROWS)
    return output.getvalue()