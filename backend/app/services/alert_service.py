"""
Alert Service — Ogohlantirish tizimi biznes logikasi.

VAZIFALAR:
    1. ADI natijalariga asosida avtomatik alert yaratish
    2. Jonivor ko'rinmaslik alertlari
    3. Sensor anomaliya alertlari
    4. Deduplikatsiya — bir xil ochiq alert ikki marta yaratilmaydi
    5. Alert lifecycle boshqarish (open → seen → resolved)

DEDUPLIKATSIYA QOIDASI:
    Bir jonivor uchun bir xil alert_type dan faqat
    bitta OPEN yoki SEEN alert bo'lishi mumkin.
    Yangi trigger kelganda mavjud alert yangilanadi,
    yangi yaratilmaydi.

INTEGRATSIYA:
    - ADIService: ADI hisoblangandan keyin chaqiriladi
    - DetectionPipeline: Ko'rinmaslik aniqlanganda
    - Celery tasks: Scheduled tekshiruvlar
    - WebSocket: Yangi alert → real vaqt xabar
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.animal import Animal, AnimalStatus
from app.models.alert import (
    Alert,
    AlertType,
    AlertSeverity,
    AlertStatus,
    ALERT_SEVERITY_MAP,
)
from app.models.adi_log import ADILog
from app.models.detection import Detection
from app.schemas.alert import AlertCreateManual
from app.core.exceptions import EntityNotFoundError, DatabaseError

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Konstantalar                                                         #
# ------------------------------------------------------------------ #

# ADI keskin tushish threshold
ADI_SHARP_DROP_THRESHOLD = 15.0     # Bir kunda shu balldan ko'p tushsa
ADI_WARNING_THRESHOLD    = 50.0     # Warning kategoriya chegarasi
ADI_CRITICAL_THRESHOLD   = 25.0     # Critical kategoriya chegarasi

# Ko'rinmaslik thresholdlari
MISSING_WARNING_HOURS    = 24       # 24 soat ko'rinmasa → warning
MISSING_CRITICAL_HOURS   = 48       # 48 soat ko'rinmasa → critical

# Oziqlanish to'xtash threshold
FEEDING_STOPPED_VISITS   = 1        # Kuniga 1 dan kam tashrif = to'xtagan


class AlertService:
    """
    Alert lifecycle boshqarish servisi.

    Barcha alert yaratish, yangilash va resolve logikasi.

    Usage:
        service = AlertService(db)
        await service.process_adi_result(animal_id=1, adi_score=22.0, prev_score=68.0)
        await service.check_missing_animals()
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ================================================================ #
    # ADI BASED ALERTS                                                   #
    # ================================================================ #

    async def process_adi_result(
        self,
        animal_id: int,
        adi_score: float,
        category: str,
        prev_score: Optional[float] = None,
        feeding_score: Optional[float] = None,
    ) -> list[Alert]:
        """
        ADI hisoblash natijasiga asosida alertlarni tekshirish
        va kerak bo'lsa yaratish.

        Args:
            animal_id:     Jonivor ID
            adi_score:     Bugungi ADI score
            category:      Bugungi kategoriya
            prev_score:    Kechagi ADI score (trend uchun)
            feeding_score: Oziqlanish komponenti score

        Returns:
            Yaratilgan yoki yangilangan alertlar ro'yxati
        """
        created_alerts: list[Alert] = []

        # 1. Critical kategoriya
        if category == "critical":
            alert = await self._ensure_alert(
                animal_id=animal_id,
                alert_type=AlertType.ADI_CRITICAL,
                title=f"Kritik holat: ADI {adi_score:.1f}",
                description=(
                    f"Jonivorning ADI ko'rsatkichi kritik darajaga tushdi "
                    f"({adi_score:.1f}/100). "
                    f"Zudlik bilan veterinar tekshiruvi talab etiladi."
                ),
                context={
                    "adi_score":    adi_score,
                    "category":     category,
                    "threshold":    ADI_CRITICAL_THRESHOLD,
                },
            )
            if alert:
                created_alerts.append(alert)

        # 2. Warning kategoriya
        elif category == "warning":
            alert = await self._ensure_alert(
                animal_id=animal_id,
                alert_type=AlertType.ADI_WARNING,
                title=f"Diqqat: ADI {adi_score:.1f}",
                description=(
                    f"Jonivorning ADI ko'rsatkichi past ({adi_score:.1f}/100). "
                    f"Kuzatishni kuchaytirish va veterinar maslahat olish tavsiya etiladi."
                ),
                context={
                    "adi_score":  adi_score,
                    "category":   category,
                    "threshold":  ADI_WARNING_THRESHOLD,
                },
            )
            if alert:
                created_alerts.append(alert)

        else:
            # Holat yaxshilangan — warning/critical alertlarni yopish
            await self._auto_resolve_adi_alerts(animal_id, adi_score)

        # 3. Keskin tushish
        if prev_score is not None:
            drop = prev_score - adi_score
            if drop >= ADI_SHARP_DROP_THRESHOLD:
                alert = await self._ensure_alert(
                    animal_id=animal_id,
                    alert_type=AlertType.ADI_SHARP_DROP,
                    title=f"ADI keskin tushdi: -{drop:.1f} ball",
                    description=(
                        f"Jonivorning ADI ko'rsatkichi bir kunda "
                        f"{drop:.1f} ball pasaydi "
                        f"({prev_score:.1f} → {adi_score:.1f}). "
                        f"Tez tekshirish zarur."
                    ),
                    context={
                        "prev_score":   prev_score,
                        "curr_score":   adi_score,
                        "drop_amount":  round(drop, 2),
                        "threshold":    ADI_SHARP_DROP_THRESHOLD,
                    },
                )
                if alert:
                    created_alerts.append(alert)

        # 4. Oziqlanish to'xtagan
        if feeding_score is not None and feeding_score < 20.0:
            alert = await self._ensure_alert(
                animal_id=animal_id,
                alert_type=AlertType.FEEDING_STOPPED,
                title="Oziqlanish deyarli to'xtagan",
                description=(
                    f"Jonivor bugun oziqlanish zonasiga "
                    f"deyarli bormadi (score: {feeding_score:.1f}/100). "
                    f"Sog'liq muammosi bo'lishi mumkin."
                ),
                context={
                    "feeding_score": feeding_score,
                    "threshold":     20.0,
                },
            )
            if alert:
                created_alerts.append(alert)

        return created_alerts

    # ================================================================ #
    # PRESENCE BASED ALERTS                                              #
    # ================================================================ #

    async def check_missing_animals(self) -> list[Alert]:
        """
        So'nggi deteksiya vaqtiga qarab
        ko'rinmayotgan jonivorlarni aniqlash.

        Celery scheduled task tomonidan har soatda chaqiriladi.

        Returns:
            Yaratilgan alertlar ro'yxati
        """
        now = datetime.now(timezone.utc)
        created_alerts: list[Alert] = []

        # Aktiv jonivorlarni olish
        stmt = select(Animal).where(Animal.status == AnimalStatus.ACTIVE)
        result = await self.db.execute(stmt)
        animals = list(result.scalars().all())

        for animal in animals:
            if not animal.last_detected_at:
                continue

            # last_detected_at timezone-aware bo'lishini ta'minlash
            last_seen = animal.last_detected_at
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)

            hours_missing = (now - last_seen).total_seconds() / 3600

            if hours_missing >= MISSING_CRITICAL_HOURS:
                alert = await self._ensure_alert(
                    animal_id=animal.id,
                    alert_type=AlertType.ANIMAL_MISSING_LONG,
                    title=f"Jonivor {animal.tag_id} — {int(hours_missing)} soat ko'rinmadi",
                    description=(
                        f"Jonivor {animal.tag_id} ({animal.species.value}) "
                        f"{int(hours_missing)} soatdan beri hech bir kamerada "
                        f"ko'rinmadi. So'nggi ko'rinish: {last_seen.strftime('%Y-%m-%d %H:%M')} UTC. "
                        f"Darhol tekshirish zarur."
                    ),
                    context={
                        "tag_id":         animal.tag_id,
                        "species":        animal.species.value,
                        "last_seen_at":   last_seen.isoformat(),
                        "hours_missing":  round(hours_missing, 1),
                        "threshold_hours": MISSING_CRITICAL_HOURS,
                    },
                )
                if alert:
                    created_alerts.append(alert)

            elif hours_missing >= MISSING_WARNING_HOURS:
                alert = await self._ensure_alert(
                    animal_id=animal.id,
                    alert_type=AlertType.ANIMAL_MISSING,
                    title=f"Jonivor {animal.tag_id} — {int(hours_missing)} soat ko'rinmadi",
                    description=(
                        f"Jonivor {animal.tag_id} ({animal.species.value}) "
                        f"{int(hours_missing)} soatdan beri ko'rinmadi. "
                        f"So'nggi ko'rinish: {last_seen.strftime('%Y-%m-%d %H:%M')} UTC."
                    ),
                    context={
                        "tag_id":          animal.tag_id,
                        "species":         animal.species.value,
                        "last_seen_at":    last_seen.isoformat(),
                        "hours_missing":   round(hours_missing, 1),
                        "threshold_hours": MISSING_WARNING_HOURS,
                    },
                )
                if alert:
                    created_alerts.append(alert)
            else:
                # Jonivor qaytib ko'rindi — missing alertlarni yopish
                await self._auto_resolve_missing_alerts(animal.id)

        logger.info(
            f"Missing animal check complete: "
            f"{len(animals)} animals checked, "
            f"{len(created_alerts)} alerts created"
        )

        return created_alerts

    async def check_camera_status(
        self,
        camera_id: str,
        is_online: bool,
    ) -> Optional[Alert]:
        """
        Kamera holati o'zgarganda alert yaratish yoki yopish.

        Args:
            camera_id: Kamera identifikatori
            is_online: True = online, False = offline
        """
        if not is_online:
            return await self._ensure_alert(
                animal_id=None,
                alert_type=AlertType.CAMERA_OFFLINE,
                title=f"Kamera offline: {camera_id}",
                description=(
                    f"Kamera {camera_id} bilan aloqa uzildi. "
                    f"Monitoring to'liq ishlamayapti."
                ),
                context={"camera_id": camera_id},
                camera_id=camera_id,
            )
        else:
            # Kamera qaytib online bo'ldi
            await self._auto_resolve_camera_alerts(camera_id)
            return None

    # ================================================================ #
    # SENSOR BASED ALERTS                                                #
    # ================================================================ #

    async def process_sensor_data(
        self,
        animal_id: int,
        temperature: Optional[float] = None,
        heart_rate: Optional[float] = None,
    ) -> list[Alert]:
        """
        Sensor ma'lumotlariga asosida alertlar yaratish.

        Normal diapazonlar (qoramol):
            Harorat:      38.0 — 39.5 °C
            Yurak urishi: 40   — 80 bpm

        Args:
            animal_id:   Jonivor ID
            temperature: Harorat (°C)
            heart_rate:  Yurak urishi (bpm)

        Returns:
            Yaratilgan alertlar
        """
        created: list[Alert] = []

        if temperature is not None:
            if temperature > 40.0 or temperature < 37.0:
                alert = await self._ensure_alert(
                    animal_id=animal_id,
                    alert_type=AlertType.HIGH_TEMPERATURE,
                    title=f"Harorat anomaliyasi: {temperature:.1f}°C",
                    description=(
                        f"Jonivor tana harorati normal diapazondan "
                        f"chiqdi: {temperature:.1f}°C "
                        f"(normal: 38.0—39.5°C). "
                        f"Isitma yoki gipotermiya belgisi bo'lishi mumkin."
                    ),
                    context={
                        "temperature":     temperature,
                        "normal_min":      38.0,
                        "normal_max":      39.5,
                        "deviation":       round(
                            temperature - 38.75, 2
                        ),
                    },
                )
                if alert:
                    created.append(alert)

        if heart_rate is not None:
            if heart_rate < 30:
                alert = await self._ensure_alert(
                    animal_id=animal_id,
                    alert_type=AlertType.LOW_HEART_RATE,
                    title=f"Yurak urishi juda past: {heart_rate} bpm",
                    description=(
                        f"Jonivor yurak urishi kritik past: {heart_rate} bpm "
                        f"(normal: 40—80 bpm). Zudlik bilan tekshirish zarur."
                    ),
                    context={
                        "heart_rate": heart_rate,
                        "normal_min": 40,
                        "normal_max": 80,
                    },
                )
                if alert:
                    created.append(alert)

            elif heart_rate > 100:
                alert = await self._ensure_alert(
                    animal_id=animal_id,
                    alert_type=AlertType.HIGH_HEART_RATE,
                    title=f"Yurak urishi juda yuqori: {heart_rate} bpm",
                    description=(
                        f"Jonivor yurak urishi yuqori: {heart_rate} bpm "
                        f"(normal: 40—80 bpm). Stress yoki infeksiya belgisi."
                    ),
                    context={
                        "heart_rate": heart_rate,
                        "normal_min": 40,
                        "normal_max": 80,
                    },
                )
                if alert:
                    created.append(alert)

        return created

    # ================================================================ #
    # MANUAL ALERT                                                        #
    # ================================================================ #

    async def create_manual_alert(
        self,
        data: AlertCreateManual,
    ) -> Alert:
        """
        Fermer tomonidan qo'lda alert yaratish.

        Args:
            data: AlertCreateManual schema

        Returns:
            Yaratilgan Alert
        """
        alert = Alert(
            animal_id=     data.animal_id,
            alert_type=    data.alert_type.value,
            severity=      data.severity.value,
            status=        AlertStatus.OPEN,
            title=         data.title,
            description=   data.description,
            auto_generated=False,
            triggered_at=  datetime.now(timezone.utc),
            context=       data.context,
        )

        try:
            self.db.add(alert)
            await self.db.commit()
            await self.db.refresh(alert)
            logger.info(
                f"Manual alert created: {alert.alert_type} "
                f"for animal {alert.animal_id}"
            )
            return alert
        except Exception as e:
            await self.db.rollback()
            raise DatabaseError(f"Alert yaratishda xato: {e}") from e

    # ================================================================ #
    # LIFECYCLE MANAGEMENT                                               #
    # ================================================================ #

    async def mark_seen(
        self,
        alert_id: int,
    ) -> Alert:
        """Alertni ko'rilgan deb belgilash."""
        alert = await self._get_alert(alert_id)
        alert.mark_seen()
        await self.db.commit()
        return alert

    async def resolve_alert(
        self,
        alert_id: int,
        resolved_by: str,
        note: Optional[str] = None,
    ) -> Alert:
        """
        Alertni hal etilgan deb belgilash.

        Args:
            alert_id:    Alert ID
            resolved_by: Hal etgan foydalanuvchi
            note:        Qanday harakat qilindi
        """
        alert = await self._get_alert(alert_id)

        if not alert.is_open:
            raise ValueError(
                f"Alert {alert_id} allaqachon "
                f"{alert.status} holatida"
            )

        alert.resolve(resolved_by=resolved_by, note=note)

        try:
            await self.db.commit()
            await self.db.refresh(alert)
            logger.info(
                f"Alert {alert_id} resolved by {resolved_by}"
            )
            return alert
        except Exception as e:
            await self.db.rollback()
            raise DatabaseError(f"Alert resolve xatosi: {e}") from e

    async def dismiss_alert(
        self,
        alert_id: int,
        dismissed_by: str,
        reason: Optional[str] = None,
    ) -> Alert:
        """Alertni noto'g'ri alarm deb bekor qilish."""
        alert = await self._get_alert(alert_id)

        if not alert.is_open:
            raise ValueError(
                f"Alert {alert_id} allaqachon {alert.status}"
            )

        alert.dismiss(dismissed_by=dismissed_by, reason=reason)

        try:
            await self.db.commit()
            await self.db.refresh(alert)
            return alert
        except Exception as e:
            await self.db.rollback()
            raise DatabaseError(f"Alert dismiss xatosi: {e}") from e

    # ================================================================ #
    # QUERY METHODS                                                       #
    # ================================================================ #

    async def get_open_alerts(
        self,
        animal_id: Optional[int] = None,
        severity:  Optional[str] = None,
        limit:     int = 50,
        offset:    int = 0,
    ) -> tuple[list[Alert], int]:
        """
        Ochiq alertlarni olish.

        Returns:
            (alerts, total_count)
        """
        conditions = [
            Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN])
        ]

        if animal_id is not None:
            conditions.append(Alert.animal_id == animal_id)

        if severity:
            conditions.append(Alert.severity == severity)

        # Total count
        count_stmt = select(func.count(Alert.id)).where(and_(*conditions))
        total = await self.db.scalar(count_stmt) or 0

        # Data
        stmt = (
            select(Alert)
            .where(and_(*conditions))
            .order_by(
                # Avval severity bo'yicha: critical → low
                Alert.severity.desc(),
                Alert.triggered_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        alerts = list(result.scalars().all())

        return alerts, total

    async def get_alert_stats(self) -> dict[str, Any]:
        """Dashboard uchun alert statistikasi."""
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Ochiq alertlar severity bo'yicha
        open_stmt = (
            select(Alert.severity, func.count(Alert.id))
            .where(Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN]))
            .group_by(Alert.severity)
        )
        open_result = await self.db.execute(open_stmt)
        open_by_severity: dict[str, int] = {}
        for severity, count in open_result.fetchall():
            open_by_severity[severity] = count

        # Bugun hal etilganlar
        resolved_today_stmt = select(func.count(Alert.id)).where(
            and_(
                Alert.status == AlertStatus.RESOLVED,
                Alert.resolved_at >= today_start,
            )
        )
        resolved_today = await self.db.scalar(resolved_today_stmt) or 0

        # O'rtacha hal etish vaqti (daqiqada)
        avg_resolution_stmt = select(
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
        avg_resolution = await self.db.scalar(avg_resolution_stmt)

        return {
            "total_open":     sum(open_by_severity.values()),
            "critical_open":  open_by_severity.get("critical", 0),
            "high_open":      open_by_severity.get("high",     0),
            "medium_open":    open_by_severity.get("medium",   0),
            "low_open":       open_by_severity.get("low",      0),
            "resolved_today": resolved_today,
            "avg_resolution_minutes": (
                round(avg_resolution, 1) if avg_resolution else None
            ),
        }

    # ================================================================ #
    # PRIVATE HELPERS                                                     #
    # ================================================================ #

    async def _ensure_alert(
        self,
        animal_id: Optional[int],
        alert_type: AlertType,
        title: str,
        description: str,
        context: Optional[dict[str, Any]] = None,
        camera_id: Optional[str] = None,
    ) -> Optional[Alert]:
        """
        Deduplikatsiya bilan alert yaratish yoki yangilash.

        Agar bu jonivor uchun bu turdagi ochiq alert
        allaqachon mavjud bo'lsa — yangilanadi, yangi yaratilmaydi.

        Returns:
            Yangi yoki yangilangan Alert, yoki None (o'zgarish yo'q)
        """
        # Mavjud ochiq alertni tekshirish
        conditions = [
            Alert.alert_type == alert_type.value,
            Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN]),
        ]

        if animal_id is not None:
            conditions.append(Alert.animal_id == animal_id)
        else:
            conditions.append(Alert.animal_id.is_(None))

        stmt = select(Alert).where(and_(*conditions)).limit(1)
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        try:
            if existing:
                # Mavjud alertni yangilash
                existing.title       = title
                existing.description = description
                existing.context     = context
                existing.triggered_at = datetime.now(timezone.utc)
                await self.db.commit()
                await self.db.refresh(existing)
                return existing
            else:
                # Yangi alert yaratish
                severity = ALERT_SEVERITY_MAP.get(
                    alert_type, AlertSeverity.MEDIUM
                )
                alert = Alert(
                    animal_id=     animal_id,
                    camera_id=     camera_id,
                    alert_type=    alert_type.value,
                    severity=      severity.value,
                    status=        AlertStatus.OPEN,
                    title=         title,
                    description=   description,
                    auto_generated=True,
                    triggered_at=  datetime.now(timezone.utc),
                    context=       context,
                )
                self.db.add(alert)
                await self.db.commit()
                await self.db.refresh(alert)

                logger.info(
                    f"Alert created: {alert_type.value} "
                    f"| animal={animal_id} "
                    f"| severity={severity.value}"
                )
                return alert

        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"Failed to ensure alert {alert_type.value}: {e}",
                exc_info=True,
            )
            return None

    async def _auto_resolve_adi_alerts(
        self,
        animal_id: int,
        current_score: float,
    ) -> None:
        """
        Jonivor holati yaxshilanganda
        ADI alertlarini avtomatik yopish.
        """
        adi_alert_types = [
            AlertType.ADI_CRITICAL.value,
            AlertType.ADI_WARNING.value,
        ]

        stmt = select(Alert).where(
            and_(
                Alert.animal_id == animal_id,
                Alert.alert_type.in_(adi_alert_types),
                Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN]),
            )
        )
        result = await self.db.execute(stmt)
        alerts = list(result.scalars().all())

        for alert in alerts:
            alert.resolve(
                resolved_by="system",
                note=(
                    f"ADI yaxshilandi: {current_score:.1f}/100. "
                    f"Avtomatik yopildi."
                ),
            )

        if alerts:
            await self.db.commit()
            logger.info(
                f"Auto-resolved {len(alerts)} ADI alerts "
                f"for animal {animal_id}"
            )

    async def _auto_resolve_missing_alerts(
        self,
        animal_id: int,
    ) -> None:
        """Jonivor qaytib ko'ringanda missing alertlarni yopish."""
        missing_types = [
            AlertType.ANIMAL_MISSING.value,
            AlertType.ANIMAL_MISSING_LONG.value,
        ]

        stmt = select(Alert).where(
            and_(
                Alert.animal_id == animal_id,
                Alert.alert_type.in_(missing_types),
                Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN]),
            )
        )
        result = await self.db.execute(stmt)
        alerts = list(result.scalars().all())

        for alert in alerts:
            alert.resolve(
                resolved_by="system",
                note="Jonivor kamerada qayta aniqlandi. Avtomatik yopildi.",
            )

        if alerts:
            await self.db.commit()
            logger.info(
                f"Auto-resolved {len(alerts)} missing alerts "
                f"for animal {animal_id}"
            )

    async def _auto_resolve_camera_alerts(
        self,
        camera_id: str,
    ) -> None:
        """Kamera online bo'lganda uning alertlarini yopish."""
        stmt = select(Alert).where(
            and_(
                Alert.camera_id == camera_id,
                Alert.alert_type == AlertType.CAMERA_OFFLINE.value,
                Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN]),
            )
        )
        result = await self.db.execute(stmt)
        alerts = list(result.scalars().all())

        for alert in alerts:
            alert.resolve(
                resolved_by="system",
                note=f"Kamera {camera_id} qayta ulandi. Avtomatik yopildi.",
            )

        if alerts:
            await self.db.commit()

    async def _get_alert(self, alert_id: int) -> Alert:
        """Alert olish, topilmasa exception."""
        stmt = select(Alert).where(Alert.id == alert_id)
        result = await self.db.execute(stmt)
        alert = result.scalar_one_or_none()

        if not alert:
            raise EntityNotFoundError(
                entity="Alert",
                identifier=alert_id,
            )
        return alert
