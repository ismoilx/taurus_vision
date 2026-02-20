"""
ADI Repository — Animal Development Index ma'lumotlar qatlami.

JAVOBGARLIK:
    Faqat DB operatsiyalari — biznes logika YO'Q.
    ADIService shu repository orqali DB bilan ishlaydi.

PATTERN:
    Service → Repository → SQLAlchemy → PostgreSQL

MUHIM:
    Bu fayl ADIService ichidagi barcha to'g'ridan-to'g'ri
    DB querylarini to'liq almashtiradi. ADIService faqat
    adi_result hisoblash bilan shug'ullanadi — saqlash va
    o'qish bu repository orqali amalga oshiriladi.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence, Any

from sqlalchemy import select, and_, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.adi_log import ADILog
from app.models.animal import Animal, AnimalStatus
from app.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class ADIRepository:
    """
    Repository for ADI Log entity database operations.

    All methods are strictly async and fully type-annotated.
    No business logic — pure DB access layer.

    Args:
        db: AsyncSession injected via FastAPI Depends()

    Example:
        repo = ADIRepository(db)
        log  = await repo.get_by_animal_and_date(animal_id=1, date_str="2026-02-20")
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # CREATE / UPSERT
    # =========================================================================

    async def create(self, log: ADILog) -> ADILog:
        """
        ADI log yozuvini DB ga qo'shish.

        Args:
            log: To'ldirilgan ADILog ORM instance

        Returns:
            Saqlangan ADILog (generated id bilan)

        Raises:
            DatabaseError: DB xatosi bo'lsa
        """
        try:
            self.db.add(log)
            await self.db.flush()
            await self.db.refresh(log)
            logger.debug(
                f"[adi_repo] Created ADI log: animal_id={log.animal_id} "
                f"date={log.calculation_date} score={log.adi_score:.1f}"
            )
            return log
        except Exception as exc:
            logger.error(f"[adi_repo] create failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="ADI log yaratishda xato",
                details={"error": str(exc)},
            ) from exc

    async def upsert(
        self,
        animal_id: int,
        calculation_date: str,
        log_data: dict[str, Any],
    ) -> ADILog:
        """
        Mavjud bo'lsa yangilash, yo'q bo'lsa yaratish (upsert).

        Args:
            animal_id:        Jonivor ID
            calculation_date: YYYY-MM-DD format
            log_data:         Yangilanadigan field qiymatlari (dict)

        Returns:
            Yangi yoki yangilangan ADILog

        Raises:
            DatabaseError: DB xatosi bo'lsa
        """
        try:
            existing = await self.get_by_animal_and_date(animal_id, calculation_date)

            if existing:
                # Mavjud yozuvni yangilash
                for field, value in log_data.items():
                    if hasattr(existing, field):
                        setattr(existing, field, value)
                await self.db.flush()
                await self.db.refresh(existing)
                logger.debug(
                    f"[adi_repo] Updated ADI log: animal_id={animal_id} "
                    f"date={calculation_date}"
                )
                return existing
            else:
                # Yangi yozuv yaratish
                log = ADILog(
                    animal_id=animal_id,
                    calculation_date=calculation_date,
                    **log_data,
                )
                return await self.create(log)

        except DatabaseError:
            raise
        except Exception as exc:
            logger.error(f"[adi_repo] upsert failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="ADI upsert xatosi",
                details={"error": str(exc)},
            ) from exc

    # =========================================================================
    # READ — single
    # =========================================================================

    async def get_by_id(self, log_id: int) -> Optional[ADILog]:
        """
        Primary key orqali ADI log olish.

        Args:
            log_id: ADILog.id

        Returns:
            ADILog yoki None
        """
        try:
            result = await self.db.execute(
                select(ADILog).where(ADILog.id == log_id)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(f"[adi_repo] get_by_id({log_id}) failed: {exc}")
            raise DatabaseError(
                message=f"ADI log olishda xato (id={log_id})",
                details={"error": str(exc)},
            ) from exc

    async def get_by_animal_and_date(
        self,
        animal_id: int,
        date_str: str,
    ) -> Optional[ADILog]:
        """
        Jonivor va sana kombinatsiyasi orqali ADI log olish.

        Bu kombinatsiya UniqueConstraint bilan himoyalangan,
        shuning uchun natija faqat bitta yoki None bo'lishi mumkin.

        Args:
            animal_id: Jonivor ID
            date_str:  YYYY-MM-DD format

        Returns:
            ADILog yoki None
        """
        try:
            result = await self.db.execute(
                select(ADILog).where(
                    and_(
                        ADILog.animal_id == animal_id,
                        ADILog.calculation_date == date_str,
                    )
                )
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(
                f"[adi_repo] get_by_animal_and_date({animal_id}, {date_str}) "
                f"failed: {exc}"
            )
            raise DatabaseError(
                message="ADI log olishda xato",
                details={"animal_id": animal_id, "date": date_str, "error": str(exc)},
            ) from exc

    async def get_latest_for_animal(self, animal_id: int) -> Optional[ADILog]:
        """
        Jonivorning eng so'nggi ADI logini olish.

        Args:
            animal_id: Jonivor ID

        Returns:
            So'nggi ADILog yoki None
        """
        try:
            result = await self.db.execute(
                select(ADILog)
                .where(ADILog.animal_id == animal_id)
                .order_by(ADILog.calculation_date.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(
                f"[adi_repo] get_latest_for_animal({animal_id}) failed: {exc}"
            )
            raise DatabaseError(
                message="So'nggi ADI log olishda xato",
                details={"animal_id": animal_id, "error": str(exc)},
            ) from exc

    # =========================================================================
    # READ — collections
    # =========================================================================

    async def get_trend_for_animal(
        self,
        animal_id: int,
        days: int = 30,
    ) -> list[ADILog]:
        """
        Jonivorning ADI trend tarixini olish.

        Args:
            animal_id: Jonivor ID
            days:      Necha kunlik tarix (default: 30)

        Returns:
            ADILog ro'yxati, yangi → eski tartibda
        """
        from_date = (
            datetime.now(timezone.utc) - timedelta(days=days)
        ).strftime("%Y-%m-%d")

        try:
            result = await self.db.execute(
                select(ADILog)
                .where(
                    and_(
                        ADILog.animal_id == animal_id,
                        ADILog.calculation_date >= from_date,
                    )
                )
                .order_by(ADILog.calculation_date.desc())
            )
            return list(result.scalars().all())
        except Exception as exc:
            logger.error(
                f"[adi_repo] get_trend_for_animal({animal_id}, {days}d) failed: {exc}"
            )
            raise DatabaseError(
                message="ADI trend olishda xato",
                details={"animal_id": animal_id, "days": days, "error": str(exc)},
            ) from exc

    async def get_by_date(
        self,
        date_str: str,
        category: Optional[str] = None,
    ) -> list[ADILog]:
        """
        Berilgan sananing barcha ADI loglarini olish.

        Farm summary va daily report uchun ishlatiladi.

        Args:
            date_str: YYYY-MM-DD format
            category: Filter: healthy | average | warning | critical (ixtiyoriy)

        Returns:
            ADILog ro'yxati
        """
        try:
            conditions = [ADILog.calculation_date == date_str]

            if category:
                conditions.append(ADILog.category == category)

            result = await self.db.execute(
                select(ADILog)
                .where(and_(*conditions))
                .order_by(ADILog.adi_score.desc())
            )
            return list(result.scalars().all())
        except Exception as exc:
            logger.error(f"[adi_repo] get_by_date({date_str}) failed: {exc}")
            raise DatabaseError(
                message="ADI log olishda xato",
                details={"date": date_str, "error": str(exc)},
            ) from exc

    async def get_concerning_animals(
        self,
        date_str: Optional[str] = None,
    ) -> list[ADILog]:
        """
        Warning va critical kategoriyasidagi jonivorlar ADI loglarini olish.

        Dashboard "Needs Attention" widget uchun.

        Args:
            date_str: YYYY-MM-DD (None = bugun)

        Returns:
            Warning/critical ADILog ro'yxati, score o'sish tartibida
        """
        target_date = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        try:
            result = await self.db.execute(
                select(ADILog)
                .where(
                    and_(
                        ADILog.calculation_date == target_date,
                        ADILog.category.in_(["warning", "critical"]),
                    )
                )
                .order_by(ADILog.adi_score.asc())  # Eng pastdan boshlab
            )
            return list(result.scalars().all())
        except Exception as exc:
            logger.error(f"[adi_repo] get_concerning_animals failed: {exc}")
            raise DatabaseError(
                message="Warning/critical ADI loglar olishda xato",
                details={"error": str(exc)},
            ) from exc

    async def get_previous_score(
        self,
        animal_id: int,
        before_date: str,
    ) -> Optional[float]:
        """
        Berilgan sanadan oldingi eng so'nggi ADI scoreni olish.

        Alert sharp-drop detection uchun ishlatiladi.

        Args:
            animal_id:   Jonivor ID
            before_date: YYYY-MM-DD — bu sanadan oldingi

        Returns:
            ADI score (float) yoki None
        """
        try:
            result = await self.db.execute(
                select(ADILog.adi_score)
                .where(
                    and_(
                        ADILog.animal_id == animal_id,
                        ADILog.calculation_date < before_date,
                    )
                )
                .order_by(ADILog.calculation_date.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            return float(row) if row is not None else None
        except Exception as exc:
            logger.error(
                f"[adi_repo] get_previous_score({animal_id}) failed: {exc}"
            )
            raise DatabaseError(
                message="Oldingi ADI score olishda xato",
                details={"animal_id": animal_id, "error": str(exc)},
            ) from exc

    # =========================================================================
    # FARM-WIDE AGGREGATIONS
    # =========================================================================

    async def get_farm_category_counts(self, date_str: str) -> dict[str, int]:
        """
        Berilgan sana uchun kategoriya bo'yicha jonivorlar soni.

        Args:
            date_str: YYYY-MM-DD

        Returns:
            {"healthy": N, "average": N, "warning": N, "critical": N}
        """
        try:
            result = await self.db.execute(
                select(ADILog.category, func.count(ADILog.id))
                .where(ADILog.calculation_date == date_str)
                .group_by(ADILog.category)
            )
            counts: dict[str, int] = {
                "healthy": 0,
                "average": 0,
                "warning": 0,
                "critical": 0,
            }
            for category, count in result.fetchall():
                counts[category] = count
            return counts
        except Exception as exc:
            logger.error(f"[adi_repo] get_farm_category_counts failed: {exc}")
            raise DatabaseError(
                message="Kategoriya sanoq olishda xato",
                details={"date": date_str, "error": str(exc)},
            ) from exc

    async def get_farm_avg_score(self, date_str: str) -> Optional[float]:
        """
        Berilgan sana uchun ferma o'rtacha ADI scorini olish.

        Args:
            date_str: YYYY-MM-DD

        Returns:
            O'rtacha score yoki None (ma'lumot yo'q)
        """
        try:
            result = await self.db.execute(
                select(func.avg(ADILog.adi_score))
                .where(ADILog.calculation_date == date_str)
            )
            avg = result.scalar_one_or_none()
            return round(float(avg), 2) if avg is not None else None
        except Exception as exc:
            logger.error(f"[adi_repo] get_farm_avg_score failed: {exc}")
            raise DatabaseError(
                message="O'rtacha score olishda xato",
                details={"date": date_str, "error": str(exc)},
            ) from exc

    async def get_animals_without_adi_today(self) -> list[int]:
        """
        Bugun ADI hisoblanmagan aktiv jonivorlar ID larini olish.

        Celery task uchun — qaysi jonivorlar hisob-kitob qilinishi kerak.

        Returns:
            animal_id lar ro'yxati
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        try:
            # Bugun ADI hisoblangan jonivorlar
            calculated_stmt = select(ADILog.animal_id).where(
                ADILog.calculation_date == today
            )
            calculated_result = await self.db.execute(calculated_stmt)
            calculated_ids = {row[0] for row in calculated_result.fetchall()}

            # Barcha aktiv jonivorlar
            active_stmt = select(Animal.id).where(
                Animal.status == AnimalStatus.ACTIVE
            )
            active_result = await self.db.execute(active_stmt)
            active_ids = [row[0] for row in active_result.fetchall()]

            # Farq
            missing = [aid for aid in active_ids if aid not in calculated_ids]
            return missing

        except Exception as exc:
            logger.error(f"[adi_repo] get_animals_without_adi_today failed: {exc}")
            raise DatabaseError(
                message="ADI hisob-kitob qilinmagan jonivorlarni olishda xato",
                details={"error": str(exc)},
            ) from exc

    # =========================================================================
    # DELETE
    # =========================================================================

    async def delete_by_animal_and_date(
        self,
        animal_id: int,
        date_str: str,
    ) -> bool:
        """
        Jonivor va sana bo'yicha ADI logni o'chirish.

        Force-recalculate rejimida ishlatiladi.

        Args:
            animal_id: Jonivor ID
            date_str:  YYYY-MM-DD

        Returns:
            True — o'chirildi, False — topilmadi
        """
        try:
            existing = await self.get_by_animal_and_date(animal_id, date_str)
            if not existing:
                return False

            await self.db.delete(existing)
            await self.db.flush()

            logger.debug(
                f"[adi_repo] Deleted ADI log: animal_id={animal_id} date={date_str}"
            )
            return True

        except DatabaseError:
            raise
        except Exception as exc:
            logger.error(f"[adi_repo] delete failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="ADI log o'chirishda xato",
                details={
                    "animal_id": animal_id,
                    "date": date_str,
                    "error": str(exc),
                },
            ) from exc

    async def delete_older_than(self, days: int) -> int:
        """
        Berilgan kundan eski ADI loglarni o'chirish.

        DB tozalash uchun (scheduled task).

        Args:
            days: Shu kundan eski loglar o'chiriladi

        Returns:
            O'chirilgan yozuvlar soni
        """
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=days)
        ).strftime("%Y-%m-%d")

        try:
            result = await self.db.execute(
                delete(ADILog).where(ADILog.calculation_date < cutoff)
            )
            await self.db.flush()
            deleted_count = result.rowcount
            logger.info(
                f"[adi_repo] Deleted {deleted_count} ADI logs older than {days} days"
            )
            return deleted_count
        except Exception as exc:
            logger.error(f"[adi_repo] delete_older_than failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="Eski ADI loglarni o'chirishda xato",
                details={"days": days, "error": str(exc)},
            ) from exc

    # =========================================================================
    # COUNT / EXISTS
    # =========================================================================

    async def count_by_animal(self, animal_id: int) -> int:
        """
        Jonivorning umumiy ADI log sonini olish.

        Args:
            animal_id: Jonivor ID

        Returns:
            ADI log soni
        """
        try:
            result = await self.db.execute(
                select(func.count(ADILog.id)).where(
                    ADILog.animal_id == animal_id
                )
            )
            return result.scalar_one() or 0
        except Exception as exc:
            raise DatabaseError(
                message="ADI log sanoq olishda xato",
                details={"animal_id": animal_id, "error": str(exc)},
            ) from exc

    async def exists(self, animal_id: int, date_str: str) -> bool:
        """
        Jonivor uchun berilgan sanada ADI log mavjudligini tekshirish.

        Args:
            animal_id: Jonivor ID
            date_str:  YYYY-MM-DD

        Returns:
            True — mavjud, False — yo'q
        """
        existing = await self.get_by_animal_and_date(animal_id, date_str)
        return existing is not None