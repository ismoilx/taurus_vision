"""
Taurus Vision — Animal Service

JAVOBGARLIK: Barcha biznes qoidalar va mantiq shu yerda.
Repository ga to'g'ridan to'g'ri murojaat qilmaydi — faqat Repository orqali.

BIZNES QOIDALAR:
    1. Tag ID noyob bo'lishi kerak (katta/kichik harfga sezgir emas)
    2. Arxivlangan jonivolarni o'zgartirish mumkin emas (SOLD, DECEASED)
    3. To'g'ri status o'tishlarini nazorat qilish
    4. CSV import: satr xatolari butun importni to'xtatmaydi

METODLAR:
    create_animal()     — Bitta jonivor yaratish
    get_animal()        — ID bo'yicha olish
    get_animals()       — Sahifalangan ro'yxat
    update_animal()     — Yangilash
    delete_animal()     — O'chirish
    get_animal_by_tag() — Tag bo'yicha olish
    import_from_csv()   — CSV fayldan ommaviy import (B6)
"""

from __future__ import annotations

import csv
import io
from typing import Optional

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BusinessRuleViolationError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
)
from app.core.logging_config import get_logger
from app.models.animal import Animal, AnimalStatus
from app.repositories.animal import AnimalRepository
from app.schemas.animal import (
    AnimalCreate,
    AnimalImportRow,
    AnimalListResponse,
    AnimalResponse,
    AnimalUpdate,
    BulkImportResponse,
    BulkImportRowResult,
)

logger = get_logger(__name__)

# CSV importda bir vaqtda qabul qilinadigan maksimal satr soni.
# Katta fayllar uchun stream-based import tavsiya etiladi.
_MAX_IMPORT_ROWS = 5_000


class AnimalService:
    """
    Service layer for Animal business logic.

    Enforces all business rules:
    1. Tag ID uniqueness
    2. Archived animals cannot be modified
    3. Proper status transitions
    4. CSV import with per-row error handling

    Args:
        db: AsyncSession instance (injected via FastAPI Depends)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = AnimalRepository(db)

    # =========================================================================
    # CREATE — bitta
    # =========================================================================

    async def create_animal(self, animal_data: AnimalCreate) -> AnimalResponse:
        """
        Yangi jonivor yaratadi (biznes qoidalar bilan).

        BIZNES QOIDALARI:
            1. Tag ID noyob bo'lishi kerak (katta/kichik harfga sezgir emas)

        Args:
            animal_data: Validatsiyadan o'tgan yaratish sxemasi

        Returns:
            Yaratilgan jonivor javobi

        Raises:
            EntityAlreadyExistsError: Tag ID allaqachon mavjud bo'lsa
        """
        existing = await self.repository.get_by_tag_id(animal_data.tag_id)
        if existing:
            logger.warning(
                f"[service] Takroriy jonivor yaratishga urinish: {animal_data.tag_id}"
            )
            raise EntityAlreadyExistsError(
                message=f"'{animal_data.tag_id}' tag ID si allaqachon mavjud",
                details={
                    "tag_id": animal_data.tag_id,
                    "existing_id": existing.id,
                },
            )

        animal = await self.repository.create(animal_data)
        logger.info(
            f"[service] Jonivor yaratildi: {animal.tag_id} "
            f"(ID: {animal.id}, tur: {animal.species.value})"
        )
        return AnimalResponse.model_validate(animal)

    # =========================================================================
    # READ
    # =========================================================================

    async def get_animal(self, animal_id: int) -> AnimalResponse:
        """
        ID bo'yicha jonivorni qaytaradi.

        Args:
            animal_id: Asosiy kalit

        Returns:
            Jonivor javobi

        Raises:
            EntityNotFoundError: Jonivor topilmasa
        """
        animal = await self.repository.get_by_id(animal_id)
        if not animal:
            logger.warning(f"[service] Topilmadi: ID {animal_id}")
            raise EntityNotFoundError(
                message=f"ID {animal_id} li jonivor topilmadi",
                details={"animal_id": animal_id},
            )
        return AnimalResponse.model_validate(animal)

    async def get_animals(
        self,
        skip: int = 0,
        limit: int = 100,
        species: Optional[str] = None,
        status: Optional[str] = None,
    ) -> AnimalListResponse:
        """
        Sahifalangan va filtrlangan ro'yxatni qaytaradi.

        Args:
            skip:    Ofset (default: 0)
            limit:   Sahifa hajmi — 100 da cheklanadi
            species: Tur filtri (ixtiyoriy)
            status:  Holat filtri (ixtiyoriy)

        Returns:
            Sahifalangan ro'yxat javobi
        """
        if limit > 100:
            logger.warning(f"[service] Limit 100 ga cheklanmоqda (so'rov: {limit})")
            limit = 100

        status_enum = None
        if status:
            try:
                status_enum = AnimalStatus(status.lower())
            except ValueError:
                logger.warning(f"[service] Noto'g'ri status filtri: {status!r} — e'tiborsiz")

        animals = await self.repository.get_all(
            skip=skip, limit=limit, species=species, status=status_enum
        )
        total = await self.repository.count(species=species, status=status_enum)
        items = [AnimalResponse.model_validate(a) for a in animals]

        return AnimalListResponse(items=items, total=total, skip=skip, limit=limit)

    async def get_animal_by_tag(self, tag_id: str) -> AnimalResponse:
        """
        Tag ID bo'yicha jonivorni qaytaradi (katta/kichik harfga sezgir emas).

        Args:
            tag_id: Noyob tag identifikatori

        Raises:
            EntityNotFoundError: Jonivor topilmasa
        """
        animal = await self.repository.get_by_tag_id(tag_id)
        if not animal:
            logger.warning(f"[service] Tag bo'yicha topilmadi: {tag_id}")
            raise EntityNotFoundError(
                message=f"'{tag_id}' tag IDli jonivor topilmadi",
                details={"tag_id": tag_id},
            )
        return AnimalResponse.model_validate(animal)

    # =========================================================================
    # UPDATE
    # =========================================================================

    async def update_animal(
        self,
        animal_id: int,
        update_data: AnimalUpdate,
    ) -> AnimalResponse:
        """
        Jonivorni yangilaydi (biznes qoidalar bilan).

        BIZNES QOIDALARI:
            1. Jonivor mavjud bo'lishi kerak
            2. Arxivlangan jonivornlarni (SOLD, DECEASED) o'zgartirish mumkin emas
            3. Yangi tag_id noyob bo'lishi kerak

        Args:
            animal_id:   Yangilanadigan jonivor PK si
            update_data: O'zgartiriladigan maydonlar

        Returns:
            Yangilangan jonivor javobi

        Raises:
            EntityNotFoundError:         Jonivor topilmasa
            BusinessRuleViolationError:  Arxivlangan jonivorni o'zgartirishga urinsa
            EntityAlreadyExistsError:    Yangi tag_id allaqachon mavjud bo'lsa
        """
        animal = await self.repository.get_by_id(animal_id)
        if not animal:
            raise EntityNotFoundError(
                message=f"ID {animal_id} li jonivor topilmadi",
                details={"animal_id": animal_id},
            )

        if animal.status in (AnimalStatus.SOLD, AnimalStatus.DECEASED):
            raise BusinessRuleViolationError(
                message=(
                    f"Arxivlangan jonivorni o'zgartirib bo'lmaydi "
                    f"(holat: {animal.status.value})"
                ),
                details={"animal_id": animal_id, "status": animal.status.value},
            )

        if update_data.tag_id and update_data.tag_id != animal.tag_id:
            existing = await self.repository.get_by_tag_id(update_data.tag_id)
            if existing and existing.id != animal_id:
                raise EntityAlreadyExistsError(
                    message=f"'{update_data.tag_id}' tag ID si allaqachon mavjud",
                    details={"tag_id": update_data.tag_id, "existing_id": existing.id},
                )

        updated = await self.repository.update(animal_id, update_data)
        logger.info(f"[service] Yangilandi: ID {animal_id}")
        return AnimalResponse.model_validate(updated)

    # =========================================================================
    # DELETE
    # =========================================================================

    async def delete_animal(self, animal_id: int) -> None:
        """
        Jonivorni o'chiradi (biznes qoidalar bilan).

        BIZNES QOIDASI:
            Arxivlangan jonivornlarni (SOLD, DECEASED) o'chirib bo'lmaydi.
            Ular audit izi uchun saqlanishi kerak.

        Args:
            animal_id: O'chiriladigan jonivor PK si

        Raises:
            EntityNotFoundError:        Jonivor topilmasa
            BusinessRuleViolationError: Arxivlangan jonivorni o'chirishga urinsa
        """
        animal = await self.repository.get_by_id(animal_id)
        if not animal:
            raise EntityNotFoundError(
                message=f"ID {animal_id} li jonivor topilmadi",
                details={"animal_id": animal_id},
            )

        if animal.status in (AnimalStatus.SOLD, AnimalStatus.DECEASED):
            raise BusinessRuleViolationError(
                message=(
                    f"Arxivlangan jonivorni o'chirib bo'lmaydi "
                    f"(holat: {animal.status.value}). "
                    "Audit izi uchun saqlanishi shart."
                ),
                details={"animal_id": animal_id, "status": animal.status.value},
            )

        deleted = await self.repository.delete(animal_id)
        if deleted:
            logger.info(f"[service] O'chirildi: ID {animal_id}")
        else:
            raise EntityNotFoundError(
                message=f"ID {animal_id} li jonivor topilmadi",
                details={"animal_id": animal_id},
            )

    # =========================================================================
    # CSV OMMAVIY IMPORT (B6)
    # =========================================================================

    async def import_from_csv(
        self,
        csv_content: str,
        skip_duplicates: bool = True,
    ) -> BulkImportResponse:
        """
        CSV mazmunidan jonivornlarni ommaviy import qiladi.

        ALGORITM:
            1. CSV mazmunini satirlarga bo'lish
            2. Sarlavhani tekshirish (majburiy ustunlar: tag_id, species)
            3. Har bir satrni AnimalImportRow sxemasi orqali validatsiya qilish
            4. Bazadagi mavjud tag_id larni BITTA so'rovda tekshirish (samarali)
            5. Yaroqli va yangi jonivornlarni BITTA bulk_create bilan saqlash
            6. Har bir satr uchun natija (created | skipped | error) qaytarish

        BIZNES QOIDALARI:
            - Bitta satr xatosi butun importni to'xtatmaydi
            - skip_duplicates=True: takroriy tag_id lar "skipped" deb belgilanadi
            - skip_duplicates=False: takroriy tag_id lar "error" deb belgilanadi
            - 1000 dan ortiq satr qabul qilinmaydi (xavfsizlik)
            - Kamida tag_id va species ustunlari bo'lishi shart

        Args:
            csv_content:      UTF-8 kodlangan CSV mazmuni (sarlavha bilan)
            skip_duplicates:  True — takroriylarni o'tkazib yuborish,
                              False — xato deb belgilash

        Returns:
            BulkImportResponse — batafsil natija (created/skipped/errors/details)

        Raises:
            BusinessRuleViolationError: CSV bo'sh bo'lsa, sarlavha noto'g'ri bo'lsa,
                                        yoki satrlar soni limitdan oshsa

        Example:
            csv_text = "tag_id,species,breed\\nJNV-001,cattle,Holstein"
            result = await service.import_from_csv(csv_text)
            # BulkImportResponse(total_rows=1, created=1, skipped=0, errors=0, ...)
        """
        # ------------------------------------------------------------------
        # 1. CSV ni tahlil qilish
        # ------------------------------------------------------------------
        try:
            reader = csv.DictReader(io.StringIO(csv_content.strip()))
        except Exception as exc:
            raise BusinessRuleViolationError(
                message="CSV faylni o'qib bo'lmadi",
                details={"error": str(exc)},
            ) from exc

        # Sarlavhani tekshirish
        fieldnames = reader.fieldnames or []
        fieldnames_lower = [f.strip().lower() for f in fieldnames]

        missing_required = []
        for required in ("tag_id", "species"):
            if required not in fieldnames_lower:
                missing_required.append(required)

        if missing_required:
            raise BusinessRuleViolationError(
                message=(
                    f"CSV sarlavhasida majburiy ustunlar yo'q: "
                    f"{', '.join(missing_required)}. "
                    "Majburiy ustunlar: tag_id, species"
                ),
                details={"missing_columns": missing_required, "found_columns": fieldnames_lower},
            )

        # Barcha satrlarni ro'yxatga yuklash
        try:
            raw_rows: list[dict] = [
                {k.strip().lower(): v for k, v in row.items() if k}
                for row in reader
            ]
        except Exception as exc:
            raise BusinessRuleViolationError(
                message="CSV satrlarini o'qishda xato",
                details={"error": str(exc)},
            ) from exc

        if not raw_rows:
            raise BusinessRuleViolationError(
                message="CSV fayl bo'sh — hech qanday ma'lumot satri topilmadi",
                details={"hint": "Sarlavhadan keyin kamida bitta ma'lumot satri bo'lishi kerak"},
            )

        if len(raw_rows) > _MAX_IMPORT_ROWS:
            raise BusinessRuleViolationError(
                message=(
                    f"CSV da juda ko'p satr: {len(raw_rows)} ta. "
                    f"Bir vaqtda maksimal {_MAX_IMPORT_ROWS} ta qabul qilinadi."
                ),
                details={"received": len(raw_rows), "max_allowed": _MAX_IMPORT_ROWS},
            )

        logger.info(f"[service] CSV import boshlandi: {len(raw_rows)} ta satr")

        # ------------------------------------------------------------------
        # 2. Har bir satrni validatsiya qilish
        # ------------------------------------------------------------------
        results: list[BulkImportRowResult] = []
        valid_rows: list[tuple[int, AnimalImportRow]] = []  # (satr_raqami, sxema)

        for row_idx, raw in enumerate(raw_rows, start=1):
            try:
                import_row = AnimalImportRow.model_validate(raw)
                valid_rows.append((row_idx, import_row))
            except PydanticValidationError as exc:
                # Satr xatosini yig'ib boramiz — importni to'xtatmaymiz
                error_messages = "; ".join(
                    f"{e['loc'][0] if e['loc'] else '?'}: {e['msg']}"
                    for e in exc.errors()
                )
                results.append(
                    BulkImportRowResult(
                        row=row_idx,
                        tag_id=raw.get("tag_id", "").strip().upper() or None,
                        status="error",
                        message=f"Validatsiya xatosi: {error_messages}",
                    )
                )
                logger.debug(f"[service] Satr {row_idx} — validatsiya xatosi: {error_messages}")

        if not valid_rows:
            # Barcha satrlar xatolik bilan chiqdi — DB ga murojaat qilmaymiz
            logger.warning("[service] CSV importda barcha satrlar xato")
            return BulkImportResponse.build(results)

        # ------------------------------------------------------------------
        # 3. Mavjud tag_id larni BITTA so'rovda tekshirish
        # ------------------------------------------------------------------
        candidate_tags = [row.tag_id for _, row in valid_rows]
        existing_tags: set[str] = await self.repository.get_existing_tags(candidate_tags)

        logger.debug(
            f"[service] Mavjud tag lar: {len(existing_tags)} ta "
            f"({len(candidate_tags)} ta tekshirildi)"
        )

        # ------------------------------------------------------------------
        # 4. Yaratish / o'tkazib yuborish qarorlari
        # ------------------------------------------------------------------
        to_create: list[tuple[int, AnimalCreate]] = []  # (satr_raqami, create_sxema)

        for row_idx, import_row in valid_rows:
            if import_row.tag_id in existing_tags:
                # Takroriy tag
                status_val = "skipped" if skip_duplicates else "error"
                results.append(
                    BulkImportRowResult(
                        row=row_idx,
                        tag_id=import_row.tag_id,
                        status=status_val,
                        message=(
                            f"'{import_row.tag_id}' tag ID si allaqachon bazada mavjud — "
                            f"{'o\'tkazib yuborildi' if skip_duplicates else 'xato'}"
                        ),
                    )
                )
            else:
                to_create.append((row_idx, import_row.to_animal_create()))

        # ------------------------------------------------------------------
        # 5. Ommaviy yaratish (bitta tranzaksiya)
        # ------------------------------------------------------------------
        if to_create:
            create_data = [data for _, data in to_create]
            try:
                created_animals: list[Animal] = await self.repository.bulk_create(create_data)

                # Har bir yaratilgan jonivor uchun natija
                for (row_idx, _), animal in zip(to_create, created_animals):
                    results.append(
                        BulkImportRowResult(
                            row=row_idx,
                            tag_id=animal.tag_id,
                            status="created",
                            animal_id=animal.id,
                            message=f"'{animal.tag_id}' muvaffaqiyatli yaratildi (ID: {animal.id})",
                        )
                    )

                logger.info(
                    f"[service] CSV import: {len(created_animals)} ta yaratildi, "
                    f"{len(existing_tags)} ta o'tkazib yuborildi, "
                    f"{sum(1 for r in results if r.status == 'error')} ta xato"
                )

            except Exception as exc:
                # bulk_create muvaffaqiyatsiz bo'ldi — barcha yaratilishi kerak bo'lganlarni xato deb belgilaymiz
                logger.error(f"[service] bulk_create muvaffaqiyatsiz: {exc}", exc_info=True)
                for row_idx, create_data_item in to_create:
                    results.append(
                        BulkImportRowResult(
                            row=row_idx,
                            tag_id=create_data_item.tag_id,
                            status="error",
                            message=f"Bazaga saqlashda xato: {exc}",
                        )
                    )

        # ------------------------------------------------------------------
        # 6. Natijani satr raqami bo'yicha tartiblash va qaytarish
        # ------------------------------------------------------------------
        results.sort(key=lambda r: r.row)
        response = BulkImportResponse.build(results)

        logger.info(
            f"[service] CSV import tugadi: "
            f"jami={response.total_rows}, "
            f"yaratildi={response.created}, "
            f"o'tkazildi={response.skipped}, "
            f"xato={response.errors}"
        )
        return response