"""
Prediction Repository — Health Prediction ma'lumotlar qatlami.

JAVOBGARLIK:
    Faqat DB operatsiyalari.
    PredictionService bu repository orqali DB bilan ishlaydi.

PATTERN:
    PredictionService → PredictionRepository → SQLAlchemy → PostgreSQL

Barcha metodlar:
    - to'liq async
    - type-annotated
    - exception-safe (DatabaseError ga wrap qilingan)
    - log yozadi (DEBUG darajada)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, and_, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.health_prediction import HealthPrediction
from app.models.animal import Animal, AnimalStatus
from app.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class PredictionRepository:
    """
    Repository for HealthPrediction entity.

    Args:
        db: AsyncSession injected via FastAPI Depends()

    Example:
        repo = PredictionRepository(db)
        pred = await repo.get_latest_for_animal(animal_id=42)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # CREATE / UPSERT
    # =========================================================================

    async def create_or_replace(self, prediction: HealthPrediction) -> HealthPrediction:
        """
        Bashorat yozuvini yaratadi yoki mavjudi bo'lsa yangilaydi (upsert).

        Bir jonivor uchun bir kunda faqat bitta yozuv bo'ladi.
        Agar mavjud bo'lsa — o'chirib qaytadan yaratadi.

        Args:
            prediction: To'ldirilgan HealthPrediction ORM instance

        Returns:
            Saqlangan HealthPrediction (generated id bilan)

        Raises:
            DatabaseError: DB xatosi bo'lsa
        """
        try:
            # Mavjud yozuvni o'chirish (upsert pattern)
            await self.db.execute(
                delete(HealthPrediction).where(
                    and_(
                        HealthPrediction.animal_id == prediction.animal_id,
                        HealthPrediction.prediction_date == prediction.prediction_date,
                    )
                )
            )
            await self.db.flush()

            self.db.add(prediction)
            await self.db.flush()
            await self.db.refresh(prediction)

            logger.debug(
                f"[pred_repo] Upserted prediction: "
                f"animal_id={prediction.animal_id} "
                f"date={prediction.prediction_date} "
                f"risk={prediction.risk_level} "
                f"score={prediction.risk_score:.1f}"
            )
            return prediction

        except Exception as exc:
            logger.error(f"[pred_repo] create_or_replace failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="Bashorat yozuvini saqlashda xato",
                details={
                    "animal_id": prediction.animal_id,
                    "date": prediction.prediction_date,
                    "error": str(exc),
                },
            ) from exc

    # =========================================================================
    # READ — Single
    # =========================================================================

    async def get_latest_for_animal(
        self,
        animal_id: int,
    ) -> Optional[HealthPrediction]:
        """
        Jonivorning eng so'nggi bashoratini olish.

        Args:
            animal_id: Jonivor ID

        Returns:
            Eng yangi HealthPrediction yoki None
        """
        try:
            result = await self.db.execute(
                select(HealthPrediction)
                .where(HealthPrediction.animal_id == animal_id)
                .order_by(HealthPrediction.prediction_date.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(f"[pred_repo] get_latest_for_animal({animal_id}) failed: {exc}")
            raise DatabaseError(
                message="Bashorat olishda xato",
                details={"animal_id": animal_id, "error": str(exc)},
            ) from exc

    async def get_by_animal_and_date(
        self,
        animal_id: int,
        date_str: str,
    ) -> Optional[HealthPrediction]:
        """
        Jonivorning muayyan sanasidagi bashoratini olish.

        Args:
            animal_id: Jonivor ID
            date_str:  YYYY-MM-DD

        Returns:
            HealthPrediction yoki None
        """
        try:
            result = await self.db.execute(
                select(HealthPrediction).where(
                    and_(
                        HealthPrediction.animal_id == animal_id,
                        HealthPrediction.prediction_date == date_str,
                    )
                )
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(
                f"[pred_repo] get_by_animal_and_date({animal_id}, {date_str}) failed: {exc}"
            )
            raise DatabaseError(
                message="Bashorat olishda xato",
                details={"animal_id": animal_id, "date": date_str, "error": str(exc)},
            ) from exc

    # =========================================================================
    # READ — History
    # =========================================================================

    async def get_history_for_animal(
        self,
        animal_id: int,
        days: int = 30,
    ) -> list[HealthPrediction]:
        """
        Jonivorning bashorat tarixini olish.

        Args:
            animal_id: Jonivor ID
            days:      Necha kunlik tarix (default: 30)

        Returns:
            HealthPrediction ro'yxati, yangi → eski tartibda
        """
        from_date = (
            datetime.now(timezone.utc) - timedelta(days=days)
        ).strftime("%Y-%m-%d")

        try:
            result = await self.db.execute(
                select(HealthPrediction)
                .where(
                    and_(
                        HealthPrediction.animal_id == animal_id,
                        HealthPrediction.prediction_date >= from_date,
                    )
                )
                .order_by(HealthPrediction.prediction_date.desc())
            )
            return list(result.scalars().all())
        except Exception as exc:
            logger.error(
                f"[pred_repo] get_history_for_animal({animal_id}, {days}d) failed: {exc}"
            )
            raise DatabaseError(
                message="Bashorat tarixi olishda xato",
                details={"animal_id": animal_id, "days": days, "error": str(exc)},
            ) from exc

    # =========================================================================
    # READ — Farm-wide
    # =========================================================================

    async def get_at_risk_animals(
        self,
        date_str: Optional[str] = None,
        min_risk_level: str = "medium",
    ) -> list[HealthPrediction]:
        """
        Muayyan kunda xavf darajasi threshold dan yuqori jonivorlarni olish.

        Farm-wide "At Risk" ro'yxati uchun ishlatiladi.

        Args:
            date_str:       YYYY-MM-DD (None = bugun)
            min_risk_level: minimum daraja: medium | high | critical

        Returns:
            HealthPrediction ro'yxati, risk_score kamayish tartibida
        """
        target_date = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Risk level to minimum score mapping
        min_score_map = {
            "low":      0.0,
            "medium":  30.0,
            "high":    60.0,
            "critical": 80.0,
        }
        min_score = min_score_map.get(min_risk_level, 30.0)

        try:
            result = await self.db.execute(
                select(HealthPrediction)
                .where(
                    and_(
                        HealthPrediction.prediction_date == target_date,
                        HealthPrediction.risk_score >= min_score,
                    )
                )
                .order_by(HealthPrediction.risk_score.desc())
            )
            return list(result.scalars().all())
        except Exception as exc:
            logger.error(f"[pred_repo] get_at_risk_animals({target_date}) failed: {exc}")
            raise DatabaseError(
                message="Xavfli jonivorlar ro'yxatini olishda xato",
                details={"date": target_date, "error": str(exc)},
            ) from exc

    async def get_farm_summary(
        self,
        date_str: Optional[str] = None,
    ) -> dict:
        """
        Ferma darajasidagi bashorat statistikasi.

        Args:
            date_str: YYYY-MM-DD (None = bugun)

        Returns:
            {
                "date": str,
                "total_predicted": int,
                "low_count": int,
                "medium_count": int,
                "high_count": int,
                "critical_count": int,
                "avg_risk_score": float,
                "max_risk_score": float,
            }
        """
        target_date = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        try:
            result = await self.db.execute(
                select(
                    func.count(HealthPrediction.id).label("total"),
                    func.avg(HealthPrediction.risk_score).label("avg_score"),
                    func.max(HealthPrediction.risk_score).label("max_score"),
                    func.count(
                        func.nullif(HealthPrediction.risk_level != "low", True)
                    ).label("low_count"),
                    func.count(
                        func.nullif(HealthPrediction.risk_level != "medium", True)
                    ).label("medium_count"),
                    func.count(
                        func.nullif(HealthPrediction.risk_level != "high", True)
                    ).label("high_count"),
                    func.count(
                        func.nullif(HealthPrediction.risk_level != "critical", True)
                    ).label("critical_count"),
                )
                .where(HealthPrediction.prediction_date == target_date)
            )
            row = result.one()

            return {
                "date":            target_date,
                "total_predicted": row.total or 0,
                "avg_risk_score":  round(float(row.avg_score or 0), 1),
                "max_risk_score":  round(float(row.max_score or 0), 1),
                "low_count":       int(row.low_count     or 0),
                "medium_count":    int(row.medium_count  or 0),
                "high_count":      int(row.high_count    or 0),
                "critical_count":  int(row.critical_count or 0),
            }
        except Exception as exc:
            logger.error(f"[pred_repo] get_farm_summary({target_date}) failed: {exc}")
            raise DatabaseError(
                message="Ferma bashorat xulosasini olishda xato",
                details={"date": target_date, "error": str(exc)},
            ) from exc

    # =========================================================================
    # CLEANUP
    # =========================================================================

    async def delete_old_predictions(self, older_than_days: int = 90) -> int:
        """
        Eski bashorat yozuvlarini tozalash.

        Args:
            older_than_days: Bu kundan eski yozuvlarni o'chirish

        Returns:
            O'chirilgan yozuvlar soni
        """
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=older_than_days)
        ).strftime("%Y-%m-%d")

        try:
            result = await self.db.execute(
                delete(HealthPrediction)
                .where(HealthPrediction.prediction_date < cutoff)
            )
            deleted = result.rowcount
            logger.info(f"[pred_repo] Deleted {deleted} predictions older than {cutoff}")
            return deleted
        except Exception as exc:
            logger.error(f"[pred_repo] delete_old_predictions failed: {exc}")
            raise DatabaseError(
                message="Eski bashoratlarni o'chirishda xato",
                details={"cutoff": cutoff, "error": str(exc)},
            ) from exc