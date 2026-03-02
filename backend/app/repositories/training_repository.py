"""
Taurus Vision — Training Repository (Sprint 15-16)

TrainingRun uchun barcha DB operatsiyalari.
Repository pattern: biznes mantiq serviceda, DB mantiq shu yerda.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training_run import TrainingRun, TrainingStatus

logger = logging.getLogger(__name__)


class TrainingRepository:
    """
    TrainingRun CRUD operatsiyalari.

    Barcha SQL so'rovlar shu yerda — servisda SQL yo'q.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # CREATE
    # =========================================================================

    async def create(
        self,
        run_name:        str,
        base_model_name: str  = "yolo11n.pt",
        epochs:          int  = 50,
        batch_size:      int  = 8,
        img_size:        int  = 640,
        freeze_layers:   int  = 10,
        notes:           Optional[str] = None,
    ) -> TrainingRun:
        """Yangi TrainingRun yaratish."""
        run = TrainingRun(
            run_name        = run_name,
            status          = TrainingStatus.PENDING,
            base_model_name = base_model_name,
            epochs          = epochs,
            batch_size      = batch_size,
            img_size        = img_size,
            freeze_layers   = freeze_layers,
            notes           = notes,
        )
        self.db.add(run)
        await self.db.flush()   # ID olish uchun
        await self.db.refresh(run)
        logger.info(f"[repo] TrainingRun created: id={run.id}, name={run.run_name}")
        return run

    # =========================================================================
    # READ
    # =========================================================================

    async def get(self, run_id: int) -> Optional[TrainingRun]:
        """ID bo'yicha bitta run olish."""
        return await self.db.get(TrainingRun, run_id)

    async def list_all(
        self,
        limit:  int = 50,
        offset: int = 0,
    ) -> list[TrainingRun]:
        """Barcha runlar (yangi → eski tartibida)."""
        result = await self.db.execute(
            select(TrainingRun)
            .order_by(TrainingRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_deployed(self) -> Optional[TrainingRun]:
        """Hozir deployed bo'lgan run (bitta bo'lishi kerak)."""
        result = await self.db.execute(
            select(TrainingRun).where(TrainingRun.is_deployed == True)  # noqa: E712
        )
        return result.scalar_one_or_none()

    # =========================================================================
    # UPDATE
    # =========================================================================

    async def set_status(
        self,
        run_id:  int,
        status:  TrainingStatus,
        error:   Optional[str] = None,
    ) -> Optional[TrainingRun]:
        """Run statusini yangilash."""
        run = await self.get(run_id)
        if not run:
            return None

        run.status = status

        if status == TrainingStatus.TRAINING:
            run.started_at = datetime.now(timezone.utc)
        elif status in (TrainingStatus.COMPLETED, TrainingStatus.FAILED):
            run.completed_at = datetime.now(timezone.utc)

        if error:
            run.error_message = error

        await self.db.flush()
        return run

    async def set_dataset_info(
        self,
        run_id:       int,
        dataset_info: dict,
    ) -> Optional[TrainingRun]:
        """Dataset statistikasini saqlash."""
        run = await self.get(run_id)
        if not run:
            return None
        run.dataset_info = dataset_info
        await self.db.flush()
        return run

    async def set_metrics(
        self,
        run_id:     int,
        metrics:    dict,
        model_path: str,
    ) -> Optional[TrainingRun]:
        """Training natijalarini saqlash."""
        run = await self.get(run_id)
        if not run:
            return None
        run.metrics    = metrics
        run.model_path = model_path
        await self.db.flush()
        return run

    async def deploy(self, run_id: int) -> Optional[TrainingRun]:
        """
        Runni deployed deb belgilash.
        Avvalgi deployed runni pending ga qaytarish.
        """
        # Avvalgi deploy ni bekor qilish
        await self.db.execute(
            update(TrainingRun)
            .where(TrainingRun.is_deployed == True)  # noqa: E712
            .values(is_deployed=False)
        )

        # Yangi deploy
        run = await self.get(run_id)
        if not run:
            return None

        run.is_deployed = True
        run.status      = TrainingStatus.DEPLOYED
        run.deployed_at = datetime.now(timezone.utc)

        await self.db.flush()
        logger.info(f"[repo] TrainingRun deployed: id={run_id}")
        return run