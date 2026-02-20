"""
Alert Repository — Ogohlantirish ma'lumotlar qatlami.

JAVOBGARLIK:
    Faqat DB operatsiyalari — biznes logika YO'Q.
    AlertService shu repository orqali DB bilan ishlaydi.

PATTERN:
    Service → Repository → SQLAlchemy → PostgreSQL

MUHIM:
    AlertService ichidagi barcha to'g'ridan-to'g'ri DB querylar
    shu repositoryga ko'chirilgan. AlertService faqat biznes
    qoidalar (deduplikatsiya, lifecycle, severity mapping) bilan
    shug'ullanadi.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

from sqlalchemy import select, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertType, AlertStatus
from app.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class AlertRepository:
    """
    Repository for Alert entity database operations.

    All methods are strictly async and fully type-annotated.
    No business logic — pure DB access layer.

    Args:
        db: AsyncSession injected via FastAPI Depends()

    Example:
        repo = AlertRepository(db)
        alert = await repo.get_open_by_animal_and_type(
            animal_id=1,
            alert_type=AlertType.ADI_CRITICAL
        )
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # CREATE
    # =========================================================================

    async def create(self, alert: Alert) -> Alert:
        """
        Yangi alert yozuvini DB ga qo'shish.

        Args:
            alert: To'ldirilgan Alert ORM instance

        Returns:
            Saqlangan Alert (generated id bilan)

        Raises:
            DatabaseError: DB xatosi bo'lsa
        """
        try:
            self.db.add(alert)
            await self.db.flush()
            await self.db.refresh(alert)
            logger.debug(
                f"[alert_repo] Created alert: type={alert.alert_type} "
                f"animal_id={alert.animal_id} severity={alert.severity}"
            )
            return alert
        except Exception as exc:
            logger.error(f"[alert_repo] create failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="Alert yaratishda xato",
                details={"error": str(exc)},
            ) from exc

    # =========================================================================
    # READ — single
    # =========================================================================

    async def get_by_id(self, alert_id: int) -> Optional[Alert]:
        """
        Primary key orqali alert olish.

        Args:
            alert_id: Alert.id

        Returns:
            Alert yoki None
        """
        try:
            result = await self.db.execute(
                select(Alert).where(Alert.id == alert_id)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(f"[alert_repo] get_by_id({alert_id}) failed: {exc}")
            raise DatabaseError(
                message=f"Alert olishda xato (id={alert_id})",
                details={"error": str(exc)},
            ) from exc

    async def get_open_by_animal_and_type(
        self,
        animal_id: Optional[int],
        alert_type: AlertType,
    ) -> Optional[Alert]:
        """
        Jonivor uchun berilgan turdagi OCHIQ alertni olish.

        Deduplikatsiya tekshiruvi uchun asosiy metod.
        Faqat OPEN va SEEN statuslari "ochiq" hisoblanadi.

        Args:
            animal_id:  Jonivor ID (None = system alert, masalan kamera)
            alert_type: AlertType enum qiymati

        Returns:
            Ochiq Alert yoki None
        """
        try:
            conditions = [
                Alert.alert_type == alert_type.value,
                Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN]),
            ]

            if animal_id is not None:
                conditions.append(Alert.animal_id == animal_id)
            else:
                conditions.append(Alert.animal_id.is_(None))

            result = await self.db.execute(
                select(Alert).where(and_(*conditions)).limit(1)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(
                f"[alert_repo] get_open_by_animal_and_type failed: {exc}"
            )
            raise DatabaseError(
                message="Ochiq alertni olishda xato",
                details={
                    "animal_id": animal_id,
                    "alert_type": alert_type.value,
                    "error": str(exc),
                },
            ) from exc

    async def get_open_by_camera(self, camera_id: str) -> list[Alert]:
        """
        Kamera uchun ochiq alertlarni olish.

        Kamera online bo'lganda ularni yopish uchun.

        Args:
            camera_id: Kamera identifikatori

        Returns:
            Ochiq Alert ro'yxati
        """
        try:
            result = await self.db.execute(
                select(Alert).where(
                    and_(
                        Alert.camera_id == camera_id,
                        Alert.alert_type == AlertType.CAMERA_OFFLINE.value,
                        Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN]),
                    )
                )
            )
            return list(result.scalars().all())
        except Exception as exc:
            logger.error(
                f"[alert_repo] get_open_by_camera({camera_id}) failed: {exc}"
            )
            raise DatabaseError(
                message="Kamera alertlarini olishda xato",
                details={"camera_id": camera_id, "error": str(exc)},
            ) from exc

    # =========================================================================
    # READ — collections
    # =========================================================================

    async def get_open_alerts(
        self,
        animal_id: Optional[int] = None,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Alert], int]:
        """
        Ochiq alertlarni paginated holda olish.

        Args:
            animal_id:  Jonivor bo'yicha filter (ixtiyoriy)
            severity:   Jiddiylik bo'yicha filter: low|medium|high|critical
            alert_type: Alert turi bo'yicha filter (ixtiyoriy)
            limit:      Sahifa hajmi
            offset:     Sahifa ofseti

        Returns:
            (alerts, total_count) — tuple
        """
        try:
            conditions = [
                Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN])
            ]

            if animal_id is not None:
                conditions.append(Alert.animal_id == animal_id)
            if severity:
                conditions.append(Alert.severity == severity)
            if alert_type:
                conditions.append(Alert.alert_type == alert_type)

            where = and_(*conditions)

            # Total count
            count_result = await self.db.execute(
                select(func.count(Alert.id)).where(where)
            )
            total = count_result.scalar_one() or 0

            # Data — severity desc, triggered_at desc
            data_result = await self.db.execute(
                select(Alert)
                .where(where)
                .order_by(
                    Alert.severity.desc(),
                    Alert.triggered_at.desc(),
                )
                .limit(limit)
                .offset(offset)
            )
            alerts = list(data_result.scalars().all())

            return alerts, total

        except Exception as exc:
            logger.error(f"[alert_repo] get_open_alerts failed: {exc}")
            raise DatabaseError(
                message="Ochiq alertlarni olishda xato",
                details={"error": str(exc)},
            ) from exc

    async def get_all_alerts(
        self,
        animal_id: Optional[int] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Alert], int]:
        """
        Barcha alertlarni filtrlash va paginate qilish.

        Tarix ko'rish va export uchun ishlatiladi.

        Args:
            animal_id:  Jonivor filter
            status:     Status filter: open|seen|resolved
            severity:   Jiddiylik filter
            alert_type: Tur filter
            from_date:  Boshlanish sanasi filter
            to_date:    Tugash sanasi filter
            limit:      Sahifa hajmi
            offset:     Sahifa ofseti

        Returns:
            (alerts, total_count)
        """
        try:
            conditions: list = []

            if animal_id is not None:
                conditions.append(Alert.animal_id == animal_id)
            if status:
                conditions.append(Alert.status == status)
            if severity:
                conditions.append(Alert.severity == severity)
            if alert_type:
                conditions.append(Alert.alert_type == alert_type)
            if from_date:
                conditions.append(Alert.triggered_at >= from_date)
            if to_date:
                conditions.append(Alert.triggered_at <= to_date)

            where = and_(*conditions) if conditions else True

            count_result = await self.db.execute(
                select(func.count(Alert.id)).where(where)
            )
            total = count_result.scalar_one() or 0

            data_result = await self.db.execute(
                select(Alert)
                .where(where)
                .order_by(Alert.triggered_at.desc())
                .limit(limit)
                .offset(offset)
            )
            alerts = list(data_result.scalars().all())

            return alerts, total

        except Exception as exc:
            logger.error(f"[alert_repo] get_all_alerts failed: {exc}")
            raise DatabaseError(
                message="Alertlarni olishda xato",
                details={"error": str(exc)},
            ) from exc

    async def get_adi_alerts_for_animal(self, animal_id: int) -> list[Alert]:
        """
        Jonivor uchun ochiq ADI alertlarni olish.

        ADI yaxshilanganda ularni avtomatik yopish uchun.

        Args:
            animal_id: Jonivor ID

        Returns:
            Ochiq ADI Alert ro'yxati
        """
        adi_types = [
            AlertType.ADI_CRITICAL.value,
            AlertType.ADI_WARNING.value,
        ]
        try:
            result = await self.db.execute(
                select(Alert).where(
                    and_(
                        Alert.animal_id == animal_id,
                        Alert.alert_type.in_(adi_types),
                        Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN]),
                    )
                )
            )
            return list(result.scalars().all())
        except Exception as exc:
            logger.error(
                f"[alert_repo] get_adi_alerts_for_animal({animal_id}) failed: {exc}"
            )
            raise DatabaseError(
                message="ADI alertlarni olishda xato",
                details={"animal_id": animal_id, "error": str(exc)},
            ) from exc

    async def get_missing_alerts_for_animal(self, animal_id: int) -> list[Alert]:
        """
        Jonivor uchun ochiq missing alertlarni olish.

        Jonivor qayta ko'ringanda ularni yopish uchun.

        Args:
            animal_id: Jonivor ID

        Returns:
            Ochiq missing Alert ro'yxati
        """
        missing_types = [
            AlertType.ANIMAL_MISSING.value,
            AlertType.ANIMAL_MISSING_LONG.value,
        ]
        try:
            result = await self.db.execute(
                select(Alert).where(
                    and_(
                        Alert.animal_id == animal_id,
                        Alert.alert_type.in_(missing_types),
                        Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN]),
                    )
                )
            )
            return list(result.scalars().all())
        except Exception as exc:
            logger.error(
                f"[alert_repo] get_missing_alerts_for_animal({animal_id}) failed: {exc}"
            )
            raise DatabaseError(
                message="Missing alertlarni olishda xato",
                details={"animal_id": animal_id, "error": str(exc)},
            ) from exc

    # =========================================================================
    # AGGREGATIONS / STATS
    # =========================================================================

    async def get_stats(self) -> dict[str, Any]:
        """
        Dashboard uchun alert statistikasini olish.

        Returns:
            {
                total_open, critical_open, high_open, medium_open, low_open,
                resolved_today, avg_resolution_minutes
            }
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        try:
            # Ochiq alertlar severity bo'yicha
            open_result = await self.db.execute(
                select(Alert.severity, func.count(Alert.id))
                .where(Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN]))
                .group_by(Alert.severity)
            )
            open_by_severity: dict[str, int] = {}
            for severity, count in open_result.fetchall():
                open_by_severity[severity] = count

            # Bugun hal etilganlar
            resolved_today = await self.db.scalar(
                select(func.count(Alert.id)).where(
                    and_(
                        Alert.status == AlertStatus.RESOLVED,
                        Alert.resolved_at >= today_start,
                    )
                )
            ) or 0

            # O'rtacha hal etish vaqti (so'nggi 7 kun, daqiqada)
            avg_resolution = await self.db.scalar(
                select(
                    func.avg(
                        func.extract(
                            "epoch",
                            Alert.resolved_at - Alert.triggered_at,
                        ) / 60
                    )
                ).where(
                    and_(
                        Alert.status == AlertStatus.RESOLVED,
                        Alert.resolved_at >= now - timedelta(days=7),
                    )
                )
            )

            return {
                "total_open":     sum(open_by_severity.values()),
                "critical_open":  open_by_severity.get("critical", 0),
                "high_open":      open_by_severity.get("high",     0),
                "medium_open":    open_by_severity.get("medium",   0),
                "low_open":       open_by_severity.get("low",      0),
                "resolved_today": resolved_today,
                "avg_resolution_minutes": (
                    round(float(avg_resolution), 1)
                    if avg_resolution else None
                ),
            }

        except Exception as exc:
            logger.error(f"[alert_repo] get_stats failed: {exc}")
            raise DatabaseError(
                message="Alert statistikasini olishda xato",
                details={"error": str(exc)},
            ) from exc

    async def count_open_for_animal(self, animal_id: int) -> int:
        """
        Jonivor uchun ochiq alertlar sonini hisoblash.

        Args:
            animal_id: Jonivor ID

        Returns:
            Ochiq alertlar soni
        """
        try:
            result = await self.db.execute(
                select(func.count(Alert.id)).where(
                    and_(
                        Alert.animal_id == animal_id,
                        Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN]),
                    )
                )
            )
            return result.scalar_one() or 0
        except Exception as exc:
            raise DatabaseError(
                message="Ochiq alertlar sonini olishda xato",
                details={"animal_id": animal_id, "error": str(exc)},
            ) from exc

    # =========================================================================
    # UPDATE (faqat status o'zgarishlari — biznes logika servisda)
    # =========================================================================

    async def save(self, alert: Alert) -> Alert:
        """
        Mavjud alertni saqlash (flush + refresh).

        AlertService tomonidan status o'zgartirilgandan keyin
        DB ga yozish uchun ishlatiladi.

        Args:
            alert: O'zgartirilgan Alert ORM instance

        Returns:
            Yangilangan Alert

        Raises:
            DatabaseError: DB xatosi
        """
        try:
            await self.db.flush()
            await self.db.refresh(alert)
            logger.debug(
                f"[alert_repo] Saved alert: id={alert.id} status={alert.status}"
            )
            return alert
        except Exception as exc:
            logger.error(f"[alert_repo] save failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="Alertni saqlashda xato",
                details={"alert_id": alert.id, "error": str(exc)},
            ) from exc

    async def bulk_save(self, alerts: list[Alert]) -> None:
        """
        Bir nechta alertni batch saqlash.

        Auto-resolve operatsiyalari uchun — har birini
        alohida flush qilishdan samaraliroq.

        Args:
            alerts: O'zgartirilgan Alert ro'yxati

        Raises:
            DatabaseError: DB xatosi
        """
        if not alerts:
            return
        try:
            await self.db.flush()
            logger.debug(f"[alert_repo] Bulk saved {len(alerts)} alerts")
        except Exception as exc:
            logger.error(f"[alert_repo] bulk_save failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="Alertlarni batch saqlashda xato",
                details={"count": len(alerts), "error": str(exc)},
            ) from exc