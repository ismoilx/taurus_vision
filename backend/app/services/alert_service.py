"""
Alert Service — Ogohlantirish tizimi biznes logikasi (Refactored).

ARXITEKTURA O'ZGARISHI (Sprint 5):
    Oldingi:  AlertService → self.db.execute(select...) to'g'ridan-to'g'ri
    Yangi:    AlertService → AlertRepository → SQLAlchemy → PostgreSQL

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

from sqlalchemy import select
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
from app.repositories.alert_repository import AlertRepository
from app.schemas.alert import AlertCreateManual
from app.core.exceptions import EntityNotFoundError, DatabaseError

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Konstantalar                                                         #
# ------------------------------------------------------------------ #

ADI_SHARP_DROP_THRESHOLD = 15.0     # Bir kunda shu balldan ko'p tushsa
ADI_WARNING_THRESHOLD    = 50.0     # Warning kategoriya chegarasi
ADI_CRITICAL_THRESHOLD   = 25.0     # Critical kategoriya chegarasi

MISSING_WARNING_HOURS    = 24       # 24 soat ko'rinmasa → warning
MISSING_CRITICAL_HOURS   = 48       # 48 soat ko'rinmasa → critical

FEEDING_STOPPED_VISITS   = 1        # Kuniga 1 dan kam tashrif = to'xtagan


class AlertService:
    """
    Alert lifecycle boshqarish servisi.

    Barcha alert yaratish, yangilash va resolve logikasi.
    DB bilan muloqot AlertRepository orqali amalga oshiriladi.

    Usage:
        service = AlertService(db)
        await service.process_adi_result(
            animal_id=1, adi_score=22.0, prev_score=68.0
        )
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize Alert service.

        Args:
            db: Async database session
        """
        self.db = db
        self._repo = AlertRepository(db)  # Repository pattern

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
            category:      Bugungi kategoriya (healthy/average/warning/critical)
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
                    "adi_score":  adi_score,
                    "category":   category,
                    "threshold":  ADI_CRITICAL_THRESHOLD,
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
                        "prev_score":  prev_score,
                        "curr_score":  adi_score,
                        "drop_amount": round(drop, 2),
                        "threshold":   ADI_SHARP_DROP_THRESHOLD,
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
        So'nggi deteksiya vaqtiga qarab ko'rinmayotgan
        jonivorlarni aniqlash.

        Celery scheduled task tomonidan har soatda chaqiriladi.

        Returns:
            Yaratilgan alertlar ro'yxati
        """
        now = datetime.now(timezone.utc)
        created_alerts: list[Alert] = []

        # Aktiv jonivorlarni olish (to'g'ridan-to'g'ri, chunki
        # animal_repository bu service ga inject qilinmagan)
        result = await self.db.execute(
            select(Animal).where(Animal.status == AnimalStatus.ACTIVE)
        )
        animals = list(result.scalars().all())

        for animal in animals:
            if not animal.last_detected_at:
                continue

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
                        f"ko'rinmadi. So'nggi ko'rinish: "
                        f"{last_seen.strftime('%Y-%m-%d %H:%M')} UTC. "
                        f"Darhol tekshirish zarur."
                    ),
                    context={
                        "tag_id":          animal.tag_id,
                        "species":         animal.species.value,
                        "last_seen_at":    last_seen.isoformat(),
                        "hours_missing":   round(hours_missing, 1),
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
                        f"So'nggi ko'rinish: "
                        f"{last_seen.strftime('%Y-%m-%d %H:%M')} UTC."
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

        Returns:
            Yangi alert yoki None
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
                        f"Jonivor tana harorati normal diapazondan chiqdi: "
                        f"{temperature:.1f}°C (normal: 38.0—39.5°C). "
                        f"Isitma yoki gipotermiya belgisi bo'lishi mumkin."
                    ),
                    context={
                        "temperature": temperature,
                        "normal_min":  38.0,
                        "normal_max":  39.5,
                        "deviation":   round(temperature - 38.75, 2),
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

    async def create_manual_alert(self, data: AlertCreateManual) -> Alert:
        """
        Fermer tomonidan qo'lda alert yaratish.

        Args:
            data: AlertCreateManual Pydantic schema

        Returns:
            Yaratilgan Alert

        Raises:
            DatabaseError: DB xatosi
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
            created = await self._repo.create(alert)
            await self.db.commit()
            logger.info(
                f"Manual alert created: {alert.alert_type} "
                f"for animal {alert.animal_id}"
            )
            return created
        except DatabaseError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            raise DatabaseError(f"Alert yaratishda xato: {e}") from e

    # ================================================================ #
    # LIFECYCLE MANAGEMENT                                               #
    # ================================================================ #

    async def mark_seen(self, alert_id: int) -> Alert:
        """
        Alertni ko'rilgan deb belgilash.

        Args:
            alert_id: Alert ID

        Returns:
            Yangilangan Alert

        Raises:
            EntityNotFoundError: Alert topilmasa
        """
        alert = await self._get_alert(alert_id)
        alert.mark_seen()
        await self._repo.save(alert)
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
            note:        Qanday harakat qilindi (ixtiyoriy)

        Returns:
            Yangilangan Alert

        Raises:
            EntityNotFoundError: Alert topilmasa
            ValueError:          Alert allaqachon yopiq bo'lsa
            DatabaseError:       DB xatosi
        """
        alert = await self._get_alert(alert_id)

        if not alert.is_open:
            raise ValueError(
                f"Alert {alert_id} allaqachon {alert.status} holatida"
            )

        alert.resolve(resolved_by=resolved_by, note=note)

        try:
            await self._repo.save(alert)
            await self.db.commit()
            logger.info(f"Alert {alert_id} resolved by {resolved_by}")
            return alert
        except DatabaseError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            raise DatabaseError(f"Alert resolve xatosi: {e}") from e

    async def dismiss_alert(
        self,
        alert_id: int,
        dismissed_by: str,
        reason: Optional[str] = None,
    ) -> Alert:
        """
        Alertni noto'g'ri alarm deb bekor qilish.

        Args:
            alert_id:     Alert ID
            dismissed_by: Bekor qilgan foydalanuvchi
            reason:       Bekor qilish sababi (ixtiyoriy)

        Returns:
            Yangilangan Alert

        Raises:
            EntityNotFoundError: Alert topilmasa
            ValueError:          Alert allaqachon yopiq bo'lsa
            DatabaseError:       DB xatosi
        """
        alert = await self._get_alert(alert_id)

        if not alert.is_open:
            raise ValueError(
                f"Alert {alert_id} allaqachon {alert.status}"
            )

        alert.dismiss(dismissed_by=dismissed_by, reason=reason)

        try:
            await self._repo.save(alert)
            await self.db.commit()
            return alert
        except DatabaseError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            raise DatabaseError(f"Alert dismiss xatosi: {e}") from e

    # ================================================================ #
    # QUERY METHODS (Repository orqali)                                  #
    # ================================================================ #

    async def get_open_alerts(
        self,
        animal_id: Optional[int] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Alert], int]:
        """
        Ochiq alertlarni olish.

        Args:
            animal_id: Jonivor filter (ixtiyoriy)
            severity:  Jiddiylik filter (ixtiyoriy)
            limit:     Sahifa hajmi
            offset:    Sahifa ofseti

        Returns:
            (alerts, total_count)
        """
        return await self._repo.get_open_alerts(
            animal_id=animal_id,
            severity=severity,
            limit=limit,
            offset=offset,
        )

    async def get_alert_stats(self) -> dict[str, Any]:
        """
        Dashboard uchun alert statistikasi.

        Returns:
            {total_open, critical_open, high_open, medium_open, low_open,
             resolved_today, avg_resolution_minutes}
        """
        return await self._repo.get_stats()

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

        Args:
            animal_id:   Jonivor ID (None = system alert)
            alert_type:  AlertType enum
            title:       Alert sarlavhasi
            description: Batafsil tavsif
            context:     Qo'shimcha ma'lumotlar (JSON)
            camera_id:   Kamera ID (faqat camera alertlari uchun)

        Returns:
            Alert yoki None (xato bo'lsa)
        """
        try:
            # Repository orqali ochiq alertni tekshirish
            existing = await self._repo.get_open_by_animal_and_type(
                animal_id=animal_id,
                alert_type=alert_type,
            )

            if existing:
                # Mavjud alertni yangilash
                existing.title        = title
                existing.description  = description
                existing.context      = context
                existing.triggered_at = datetime.now(timezone.utc)
                await self._repo.save(existing)
                await self.db.commit()
                return existing
            else:
                # Yangi alert yaratish
                severity = ALERT_SEVERITY_MAP.get(alert_type, AlertSeverity.MEDIUM)
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
                created = await self._repo.create(alert)
                await self.db.commit()

                logger.info(
                    f"Alert created: {alert_type.value} "
                    f"| animal={animal_id} "
                    f"| severity={severity.value}"
                )
                return created

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
        Jonivor holati yaxshilanganda ADI alertlarini avtomatik yopish.

        Args:
            animal_id:     Jonivor ID
            current_score: Joriy ADI score
        """
        alerts = await self._repo.get_adi_alerts_for_animal(animal_id)

        for alert in alerts:
            alert.resolve(
                resolved_by="system",
                note=(
                    f"ADI yaxshilandi: {current_score:.1f}/100. "
                    f"Avtomatik yopildi."
                ),
            )

        if alerts:
            await self._repo.bulk_save(alerts)
            await self.db.commit()
            logger.info(
                f"Auto-resolved {len(alerts)} ADI alerts for animal {animal_id}"
            )

    async def _auto_resolve_missing_alerts(self, animal_id: int) -> None:
        """
        Jonivor qaytib ko'ringanda missing alertlarni yopish.

        Args:
            animal_id: Jonivor ID
        """
        alerts = await self._repo.get_missing_alerts_for_animal(animal_id)

        for alert in alerts:
            alert.resolve(
                resolved_by="system",
                note="Jonivor kamerada qayta aniqlandi. Avtomatik yopildi.",
            )

        if alerts:
            await self._repo.bulk_save(alerts)
            await self.db.commit()
            logger.info(
                f"Auto-resolved {len(alerts)} missing alerts for animal {animal_id}"
            )

    async def _auto_resolve_camera_alerts(self, camera_id: str) -> None:
        """
        Kamera online bo'lganda uning alertlarini yopish.

        Args:
            camera_id: Kamera identifikatori
        """
        alerts = await self._repo.get_open_by_camera(camera_id)

        for alert in alerts:
            alert.resolve(
                resolved_by="system",
                note=f"Kamera {camera_id} qayta ulandi. Avtomatik yopildi.",
            )

        if alerts:
            await self._repo.bulk_save(alerts)
            await self.db.commit()

    async def _get_alert(self, alert_id: int) -> Alert:
        """
        Alertni olish, topilmasa exception.

        Args:
            alert_id: Alert ID

        Returns:
            Alert ORM instance

        Raises:
            EntityNotFoundError: Alert topilmasa
        """
        alert = await self._repo.get_by_id(alert_id)

        if not alert:
            raise EntityNotFoundError(entity="Alert", identifier=alert_id)
        return alert