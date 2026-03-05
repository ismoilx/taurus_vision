"""
Taurus Vision — Animal Repository

JAVOBGARLIK: Faqat ma'lumotlar bazasi operatsiyalari.
Biznes logikasi YO'Q — bu Service qatlamining ishi.

PATTERN: Repository pattern DB qatlamini biznes logikadan ajratadi.
Barcha metodlar async, to'liq type-annotated, SQLAlchemy 2.0.

METODLAR:
    create()                 — Bitta jonivor qo'shish
    bulk_create()            — Ko'p jonivorni bir tranzaksiyada qo'shish
    get_by_id()              — ID bo'yicha qidirish
    get_by_tag_id()          — Tag ID bo'yicha qidirish (case-insensitive)
    get_existing_tags()      — Mavjud tag_id lar to'plami (import uchun)
    get_all()                — Filtrlangan ro'yxat (pagination)
    count()                  — Filtrlangan soni
    update()                 — Qisman yangilash
    delete()                 — O'chirish
    get_first_active()       — Birinchi aktiv jonivor (pipeline uchun)
    increment_detection_count() — Deteksiya hisobini oshirish
    advanced_search()        — Ko'p maydonli qidirish
    search_by_text()         — Matn bo'yicha qidirish
"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import and_, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError
from app.core.logging_config import get_logger
from app.models.animal import Animal, AnimalSpecies, AnimalStatus
from app.schemas.animal import AnimalCreate, AnimalUpdate

logger = get_logger(__name__)


class AnimalRepository:
    """
    Repository for Animal entity database operations.

    Provides full CRUD + filtering using async SQLAlchemy 2.0.
    All methods are strictly async and type-annotated.

    Args:
        db: AsyncSession injected via FastAPI Depends()
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # CREATE
    # =========================================================================

    async def create(self, animal_data: AnimalCreate) -> Animal:
        """
        Bitta yangi jonivor satrini qo'shadi.

        NOTE: Noyoblikni tekshirmaydi — bu Service qatlamining ishi.

        Args:
            animal_data: Validatsiyadan o'tgan Pydantic sxema

        Returns:
            Persistlanган Animal ORM instance (generatsiya qilingan id bilan)

        Raises:
            DatabaseError: Har qanday SQLAlchemy / DB xatosida
        """
        try:
            animal = Animal(**animal_data.model_dump())
            self.db.add(animal)
            await self.db.flush()           # Commit qilmasdan PK oling
            await self.db.refresh(animal)   # DB tomonidan hisoblangan default larni yuklang
            logger.debug(f"[repo] Created animal pk={animal.id} tag={animal.tag_id}")
            return animal
        except Exception as exc:
            logger.error(f"[repo] create failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="Failed to create animal",
                details={"error": str(exc)},
            ) from exc

    async def bulk_create(
        self,
        animals_data: list[AnimalCreate],
    ) -> list[Animal]:
        """
        Bir tranzaksiyada bir nechta jonivorni qo'shadi.

        NOTE:
            - Noyoblikni tekshirmaydi — chaqiruvchi tekshirishi kerak.
            - Barcha yozuvlar bitta flush() da saqlanadi (samarali).
            - Xato bo'lsa butun to'plam rollback qilinadi.

        Args:
            animals_data: AnimalCreate ob'ektlari ro'yxati

        Returns:
            Yaratilgan Animal ORM instance lar ro'yxati (PK lar bilan)

        Raises:
            DatabaseError: Har qanday DB xatosida

        Example:
            animals = await repo.bulk_create([
                AnimalCreate(tag_id="JNV-001", species="cattle", ...),
                AnimalCreate(tag_id="JNV-002", species="sheep", ...),
            ])
        """
        if not animals_data:
            return []

        try:
            orm_objects: list[Animal] = []
            for data in animals_data:
                animal = Animal(**data.model_dump())
                self.db.add(animal)
                orm_objects.append(animal)

            # Barcha ob'ektlarni bitta flush da saqlash (N+1 muammosidan qochish)
            await self.db.flush()

            # DB tomonidan hisoblangan qiymatlarni yuklash (id, created_at, ...)
            for animal in orm_objects:
                await self.db.refresh(animal)

            logger.info(
                f"[repo] bulk_create: {len(orm_objects)} ta jonivor qo'shildi"
            )
            return orm_objects

        except Exception as exc:
            logger.error(f"[repo] bulk_create failed: {exc}", exc_info=True)
            raise DatabaseError(
                message=f"Ommaviy yaratishda xato ({len(animals_data)} ta yozuv)",
                details={"error": str(exc), "count": len(animals_data)},
            ) from exc

    # =========================================================================
    # READ — yagona yozuv
    # =========================================================================

    async def get_by_id(self, animal_id: int) -> Optional[Animal]:
        """
        Jonivorni asosiy kalit (PK) bo'yicha topadi.

        Returns:
            Animal instance yoki None (topilmasa)
        """
        try:
            result = await self.db.execute(
                select(Animal).where(Animal.id == animal_id)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(f"[repo] get_by_id({animal_id}) failed: {exc}")
            raise DatabaseError(
                message=f"Failed to fetch animal id={animal_id}",
                details={"error": str(exc)},
            ) from exc

    async def get_by_tag_id(self, tag_id: str) -> Optional[Animal]:
        """
        Tag identifikatori bo'yicha topadi (katta/kichik harfga sezgir emas).

        Args:
            tag_id: masalan "jnv-001" yoki "JNV-001" — bir xil natija

        Returns:
            Animal instance yoki None
        """
        try:
            result = await self.db.execute(
                select(Animal).where(
                    func.upper(Animal.tag_id) == tag_id.upper()
                )
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(f"[repo] get_by_tag_id({tag_id}) failed: {exc}")
            raise DatabaseError(
                message=f"Failed to fetch animal tag={tag_id}",
                details={"error": str(exc)},
            ) from exc

    async def get_existing_tags(
        self,
        tag_ids: list[str],
    ) -> set[str]:
        """
        Berilgan tag_id lar ichidan bazada mavjud bo'lganlarini qaytaradi.

        Import jarayonida takroriy yozuvlarni aniqlash uchun ishlatiladi.
        Bitta so'rov bilan ishlaydi — samarali.

        Args:
            tag_ids: Tekshiriladigan tag_id lar ro'yxati

        Returns:
            Bazada mavjud tag_id lar to'plami (katta harflarda)

        Example:
            existing = await repo.get_existing_tags(["JNV-001", "JNV-002", "JNV-999"])
            # {"JNV-001"}  — faqat JNV-001 allaqachon bazada bor
        """
        if not tag_ids:
            return set()

        try:
            upper_tags = [t.upper() for t in tag_ids]
            result = await self.db.execute(
                select(func.upper(Animal.tag_id)).where(
                    func.upper(Animal.tag_id).in_(upper_tags)
                )
            )
            return {row[0] for row in result.fetchall()}

        except Exception as exc:
            logger.error(f"[repo] get_existing_tags failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="Mavjud tag larni tekshirishda xato",
                details={"error": str(exc)},
            ) from exc

    # =========================================================================
    # READ — to'plam
    # =========================================================================

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        species: Optional[str] = None,
        status: Optional[AnimalStatus] = None,
    ) -> Sequence[Animal]:
        """
        Filtrlar bilan sahifalangan ro'yxat qaytaradi.

        Args:
            skip:    Sahifalash ofset
            limit:   Sahifa hajmi (chaqiruvchi 100 da cheklashi kerak)
            species: Tur bo'yicha filtr (masalan "cattle")
            status:  AnimalStatus enum bo'yicha filtr

        Returns:
            Animal instance lar ro'yxati (bo'sh bo'lishi mumkin)
        """
        try:
            stmt = select(Animal)
            conditions = []

            if species:
                try:
                    conditions.append(Animal.species == AnimalSpecies(species.lower()))
                except ValueError:
                    logger.warning(f"[repo] Noma'lum species filtri: {species!r} — e'tiborsiz qoldirildi")

            if status:
                conditions.append(Animal.status == status)

            if conditions:
                stmt = stmt.where(and_(*conditions))

            stmt = stmt.offset(skip).limit(limit).order_by(Animal.id)
            result = await self.db.execute(stmt)
            return result.scalars().all()

        except Exception as exc:
            logger.error(f"[repo] get_all failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="Failed to fetch animals",
                details={"error": str(exc)},
            ) from exc

    async def count(
        self,
        species: Optional[str] = None,
        status: Optional[AnimalStatus] = None,
    ) -> int:
        """
        Filtrlarga mos jonivolar sonini hisoblaydi.

        get_all() bilan birga ishlatiladi (sahifalangan javob uchun).

        Returns:
            Integer son
        """
        try:
            stmt = select(func.count()).select_from(Animal)
            conditions = []

            if species:
                try:
                    conditions.append(Animal.species == AnimalSpecies(species.lower()))
                except ValueError:
                    pass

            if status:
                conditions.append(Animal.status == status)

            if conditions:
                stmt = stmt.where(and_(*conditions))

            result = await self.db.execute(stmt)
            return result.scalar_one()

        except Exception as exc:
            logger.error(f"[repo] count failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="Failed to count animals",
                details={"error": str(exc)},
            ) from exc

    # =========================================================================
    # UPDATE
    # =========================================================================

    async def update(
        self,
        animal_id: int,
        update_data: AnimalUpdate,
    ) -> Optional[Animal]:
        """
        Qisman yangilash — faqat None bo'lmagan maydonlar o'zgaradi.

        Args:
            animal_id:   Yangilanadigan jonivor PK si
            update_data: Pydantic sxema; None maydonlar o'tkazib yuboriladi

        Returns:
            Yangilangan Animal instance yoki None (topilmasa)

        Raises:
            DatabaseError: DB xatosida
        """
        try:
            animal = await self.get_by_id(animal_id)
            if not animal:
                return None

            update_fields = update_data.model_dump(exclude_none=True)
            for field, value in update_fields.items():
                setattr(animal, field, value)

            await self.db.flush()
            await self.db.refresh(animal)

            logger.debug(
                f"[repo] Updated animal pk={animal_id} "
                f"fields={list(update_fields.keys())}"
            )
            return animal

        except DatabaseError:
            raise
        except Exception as exc:
            logger.error(f"[repo] update({animal_id}) failed: {exc}", exc_info=True)
            raise DatabaseError(
                message=f"Failed to update animal id={animal_id}",
                details={"error": str(exc)},
            ) from exc

    # =========================================================================
    # DELETE
    # =========================================================================

    async def delete(self, animal_id: int) -> bool:
        """
        Jonivorni to'liq o'chiradi (hard delete).

        Returns:
            True — o'chirildi, False — topilmadi
        """
        try:
            animal = await self.get_by_id(animal_id)
            if not animal:
                return False

            await self.db.delete(animal)
            await self.db.flush()
            logger.debug(f"[repo] Deleted animal pk={animal_id}")
            return True

        except DatabaseError:
            raise
        except Exception as exc:
            logger.error(f"[repo] delete({animal_id}) failed: {exc}", exc_info=True)
            raise DatabaseError(
                message=f"Failed to delete animal id={animal_id}",
                details={"error": str(exc)},
            ) from exc

    # =========================================================================
    # PIPELINE YORDAMCHILARI
    # =========================================================================

    async def get_first_active(self) -> Optional[Animal]:
        """
        Birinchi aktiv jonivorni qaytaradi.

        Deteksiya pipeline si jonivorni moslashtira olmasa,
        MVP fallback sifatida ishlatiladi.
        """
        try:
            result = await self.db.execute(
                select(Animal)
                .where(Animal.status == AnimalStatus.ACTIVE)
                .order_by(Animal.id)
                .limit(1)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            raise DatabaseError(
                message="Failed to fetch first active animal",
                details={"error": str(exc)},
            ) from exc

    async def increment_detection_count(self, animal_id: int) -> None:
        """
        total_detections ni oshiradi va last_detected_at ni yangilaydi.

        Deteksiya pipeline tomonidan har muvaffaqiyatli deteksiyadan keyin chaqiriladi.
        Kritik emas — xato bo'lsa log ga yoziladi, istisno ko'tarilmaydi.

        Args:
            animal_id: Aniqlangan jonivor PK si
        """
        try:
            animal = await self.get_by_id(animal_id)
            if not animal:
                logger.warning(
                    f"[repo] increment_detection_count: animal {animal_id} topilmadi"
                )
                return
            animal.mark_detected()  # Model helper metodi
            await self.db.flush()
        except Exception as exc:
            logger.error(
                f"[repo] increment_detection_count({animal_id}) failed: {exc}"
            )
            # Kritik emas — istisno ko'tarmayiz

    # =========================================================================
    # KENGAYTIRILGAN QIDIRUV
    # =========================================================================

    async def advanced_search(
        self,
        tag_id: Optional[str] = None,
        species: Optional[AnimalSpecies] = None,
        gender: Optional[str] = None,
        status: Optional[AnimalStatus] = None,
        breed: Optional[str] = None,
        min_detections: Optional[int] = None,
        search_text: Optional[str] = None,
        sort_by: str = "tag_id",
        sort_order: str = "asc",
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Animal], int]:
        """
        Ko'p maydonli qidirish: filtrlar, saralash, sahifalash.

        Args:
            tag_id:         Tag ID bo'yicha qisman mos (case-insensitive)
            species:        Tur filtri
            gender:         Jins filtri
            status:         Holat filtri
            breed:          Zot bo'yicha qisman mos
            min_detections: Minimal deteksiya soni
            search_text:    Matn qidirish (tag_id, breed, notes)
            sort_by:        Saralash maydoni
            sort_order:     asc | desc
            skip:           Sahifalash ofset
            limit:          Maksimal natijalar soni

        Returns:
            (jonivorlar ro'yxati, jami son) — ikkilik
        """
        try:
            conditions = []

            if tag_id:
                conditions.append(Animal.tag_id.ilike(f"%{tag_id}%"))

            if species:
                conditions.append(Animal.species == species)

            if gender:
                conditions.append(Animal.gender == gender)

            if status:
                conditions.append(Animal.status == status)

            if breed:
                conditions.append(Animal.breed.ilike(f"%{breed}%"))

            if min_detections is not None:
                conditions.append(Animal.total_detections >= min_detections)

            if search_text:
                pat = f"%{search_text}%"
                conditions.append(
                    or_(
                        Animal.tag_id.ilike(pat),
                        Animal.breed.ilike(pat),
                        Animal.notes.ilike(pat),
                    )
                )

            where_clause = and_(*conditions) if conditions else True

            # Jami son (sahifalashsiz)
            count_result = await self.db.execute(
                select(func.count(Animal.id)).where(where_clause)
            )
            total = count_result.scalar() or 0

            # Ma'lumotlar + saralash
            sort_col = getattr(Animal, sort_by, Animal.tag_id)
            order_fn = desc if sort_order.lower() == "desc" else asc

            data_result = await self.db.execute(
                select(Animal)
                .where(where_clause)
                .order_by(order_fn(sort_col))
                .offset(skip)
                .limit(limit)
            )
            animals = data_result.scalars().all()

            logger.debug(
                f"[repo] advanced_search: {len(animals)} ta topildi (jami: {total})"
            )
            return animals, total

        except Exception as exc:
            logger.error(f"[repo] advanced_search failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="Kengaytirilgan qidiruvda xato",
                details={"error": str(exc)},
            ) from exc

    async def search_by_text(
        self,
        search_text: str,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Animal], int]:
        """
        tag_id, breed, notes bo'yicha oddiy matn qidirish.

        Args:
            search_text: Qidiruv matni (katta/kichik harfga sezgir emas)
            skip:        Sahifalash ofset
            limit:       Maksimal natijalar soni

        Returns:
            (jonivorlar ro'yxati, jami son)
        """
        try:
            pat = f"%{search_text}%"
            where_clause = or_(
                Animal.tag_id.ilike(pat),
                Animal.breed.ilike(pat),
                Animal.notes.ilike(pat),
            )

            count_result = await self.db.execute(
                select(func.count(Animal.id)).where(where_clause)
            )
            total = count_result.scalar() or 0

            data_result = await self.db.execute(
                select(Animal)
                .where(where_clause)
                .order_by(asc(Animal.tag_id))
                .offset(skip)
                .limit(limit)
            )
            animals = data_result.scalars().all()

            return animals, total

        except Exception as exc:
            logger.error(f"[repo] search_by_text failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="Matn qidiruvida xato",
                details={"error": str(exc)},
            ) from exc