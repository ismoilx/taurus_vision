"""
Taurus Vision — YOLO Fine-Tuning Pipeline (Sprint 15-16)

Ferma spetsifik jonivor turlarini aniqroq aniqlash uchun
pre-trained YOLOv11 modelini custom dataset bilan fine-tune qiladi.

ARXITEKTURA:
    TrainingPipeline
        ├── DatasetBuilder.build()         → YOLO format dataset
        ├── ultralytics YOLO.train()        → Fine-tuning
        ├── _evaluate()                     → mAP50 hisoblash
        └── deploy()                        → Yangi modelni ishga olish

TRANSFER LEARNING STRATEGIYASI (CPU 7.5GB uchun):
    Freeze: yolo11n backbone (birinchi 10 qatlam) → faqat head o'qitiladi
    Batch:  8 (RAM-friendly)
    Epochs: 50 (overfitting oldini olish uchun patience=10 early stopping)
    imgsz:  640 (standart YOLO kirish o'lchami)
    LR:     0.001 → 0.0001 (cosine annealing)

MUHIM:
    - Training sinxron (blocking) jarayon — Celery task ichida ishga tushadi
    - Ultralytics o'z ichiga olgan train/val loop bilan ishlatiladi
    - best.pt → ishlatiladi, last.pt → backup

DEPLOY LOGIKASI:
    Yangi model mAP50 > current model mAP50 + MIN_IMPROVEMENT bo'lsa →
    avtomatik deploy (yoki foydalanuvchi qo'lda tasdiqlaydi)
"""

import logging
import os
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Training hyperparametrlar (CPU-optimized)
DEFAULT_EPOCHS      = 50
DEFAULT_BATCH_SIZE  = 8
DEFAULT_IMG_SIZE    = 640
DEFAULT_FREEZE      = 10      # Freeze first N layers (backbone)
DEFAULT_LR0         = 0.001
DEFAULT_LRF         = 0.01    # Final LR = LR0 * LRF
DEFAULT_PATIENCE    = 10      # Early stopping
DEFAULT_WORKERS     = 0       # 0 = main thread (Docker safe)

# Deploy talabi
MIN_IMPROVEMENT_MAP50 = 0.02  # +2% mAP50 kerak deploy uchun


@dataclass
class TrainingMetrics:
    """Ultralytics training natijalaridan olingan metrikalar."""
    map50:       float   # mAP50 (primary metric)
    map50_95:    float   # mAP50-95
    precision:   float
    recall:      float
    box_loss:    float
    cls_loss:    float
    epochs_done: int
    best_epoch:  int
    duration_sec: float


class TrainingPipelineError(Exception):
    """Training jarayonidagi xato."""


class TrainingPipeline:
    """
    YOLO fine-tuning orchestrator.

    Celery task ichida ishga tushiriladi.
    Barcha og'ir I/O va hisoblash shu yerda.

    FOYDALANISH:
        pipeline = TrainingPipeline(
            base_model_path="/app/ml/models/yolo11n.pt",
            output_dir="/app/data/training/models",
        )
        metrics = pipeline.train(
            yaml_path    = "/app/data/training/datasets/42/data.yaml",
            run_id       = 42,
            epochs       = 50,
        )
    """

    def __init__(
        self,
        base_model_path: str,
        output_dir:      str,
    ) -> None:
        self._base_model = Path(base_model_path)
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"[training] Pipeline initialized | "
            f"base_model={self._base_model.name}"
        )

    # =========================================================================
    # MAIN TRAINING
    # =========================================================================

    def train(
        self,
        yaml_path:   str,
        run_id:      int,
        epochs:      int = DEFAULT_EPOCHS,
        batch_size:  int = DEFAULT_BATCH_SIZE,
        img_size:    int = DEFAULT_IMG_SIZE,
        freeze:      int = DEFAULT_FREEZE,
    ) -> TrainingMetrics:
        """
        Fine-tuning ni ishga tushirish.

        Blocking — Celery task dan chaqiriladi.

        Args:
            yaml_path:  data.yaml to'liq yo'li
            run_id:     TrainingRun DB ID (papka nomi uchun)
            epochs:     O'qitish epochlari
            batch_size: Batch o'lchami (RAM ga qarab)
            img_size:   Rasm o'lchami (640 standart)
            freeze:     Muzlatilgan qatlamlar soni

        Returns:
            TrainingMetrics — o'qitish natijalari

        Raises:
            TrainingPipelineError: Agar model fayli topilmasa yoki training xato bersa
        """
        if not self._base_model.exists():
            raise TrainingPipelineError(
                f"Base model topilmadi: {self._base_model}. "
                f"Avval 'yolo11n.pt' ni /app/ml/models/ ga joylashtiring."
            )

        if not Path(yaml_path).exists():
            raise TrainingPipelineError(
                f"data.yaml topilmadi: {yaml_path}. "
                f"DatasetBuilder.build() chaqirilganmi?"
            )

        # Ultralytics run papkasi
        run_dir  = self._output_dir / str(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        # PyTorch cache — Docker safe
        os.environ.setdefault("TORCH_HOME", "/app/ml/models")

        logger.info(
            f"[training] Starting | run_id={run_id} | "
            f"epochs={epochs} | batch={batch_size} | "
            f"freeze={freeze} | base={self._base_model.name}"
        )

        start_time = time.monotonic()

        try:
            from ultralytics import YOLO

            # Base modelni yuklash (transfer learning)
            model = YOLO(str(self._base_model))

            # Fine-tuning
            results = model.train(
                data    = yaml_path,
                epochs  = epochs,
                batch   = batch_size,
                imgsz   = img_size,
                device  = "cpu",
                freeze  = freeze,
                lr0     = DEFAULT_LR0,
                lrf     = DEFAULT_LRF,
                patience = DEFAULT_PATIENCE,
                workers  = DEFAULT_WORKERS,
                project  = str(run_dir),
                name     = "finetune",
                exist_ok = True,
                verbose  = False,
                # Augmentation (CPU-friendly)
                hsv_h    = 0.015,
                hsv_s    = 0.7,
                hsv_v    = 0.4,
                degrees  = 5.0,
                translate = 0.1,
                scale    = 0.5,
                flipud   = 0.0,
                fliplr   = 0.5,
                mosaic   = 0.5,
                # Logging
                save     = True,
                save_period = 10,
                plots    = False,  # CPU da plots off — tezroq
            )

            duration = time.monotonic() - start_time

            # Natijalarni parse qilish
            metrics = self._extract_metrics(results, duration)

            # best.pt ni run papkasiga ko'chirish (qulay yo'l)
            best_src = run_dir / "finetune" / "weights" / "best.pt"
            best_dst = run_dir / "best.pt"
            if best_src.exists():
                shutil.copy2(best_src, best_dst)
                logger.info(f"[training] best.pt copied to {best_dst}")
            else:
                logger.warning(
                    f"[training] best.pt not found at {best_src}. "
                    f"Using last.pt as fallback."
                )
                last_src = run_dir / "finetune" / "weights" / "last.pt"
                if last_src.exists():
                    shutil.copy2(last_src, best_dst)

            logger.info(
                f"[training] Complete | run_id={run_id} | "
                f"mAP50={metrics.map50:.4f} | "
                f"precision={metrics.precision:.4f} | "
                f"recall={metrics.recall:.4f} | "
                f"duration={duration:.0f}s"
            )

            return metrics

        except Exception as exc:
            duration = time.monotonic() - start_time
            logger.error(
                f"[training] FAILED | run_id={run_id} | "
                f"error={exc} | duration={duration:.0f}s",
                exc_info=True,
            )
            raise TrainingPipelineError(
                f"Training muvaffaqiyatsiz: {exc}"
            ) from exc

    # =========================================================================
    # DEPLOY
    # =========================================================================

    def deploy(
        self,
        run_id:           int,
        deploy_model_path: str,
    ) -> str:
        """
        O'qitilgan modelni ishlatishga olish.

        best.pt → deploy_model_path ga nusxalaydi.
        YoloService keyingi ishga tushishda yangi modelni yuklaydi.

        Args:
            run_id:            TrainingRun ID
            deploy_model_path: Maqsad yo'l (/app/ml/models/yolo11n_custom.pt)

        Returns:
            Deployed model to'liq yo'li

        Raises:
            TrainingPipelineError: Agar trained model topilmasa
        """
        src = self._output_dir / str(run_id) / "best.pt"
        if not src.exists():
            raise TrainingPipelineError(
                f"Trained model topilmadi: {src}. "
                f"Training muvaffaqiyatli yakunlandimi?"
            )

        dst = Path(deploy_model_path)
        dst.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(src, dst)
        logger.info(f"[training] Deployed: {src} → {dst}")
        return str(dst)

    def get_model_path(self, run_id: int) -> Optional[str]:
        """O'qitilgan model faylining yo'lini qaytarish."""
        path = self._output_dir / str(run_id) / "best.pt"
        return str(path) if path.exists() else None

    def cleanup_run(self, run_id: int) -> None:
        """O'qitish fayllarini o'chirish (disk tejash uchun)."""
        run_dir = self._output_dir / str(run_id) / "finetune"
        if run_dir.exists():
            shutil.rmtree(run_dir, ignore_errors=True)
            logger.info(f"[training] Cleaned up run dir: {run_dir}")

    # =========================================================================
    # PRIVATE
    # =========================================================================

    @staticmethod
    def _extract_metrics(results, duration_sec: float) -> TrainingMetrics:
        """
        Ultralytics results ob'ektidan metrikalarni olish.

        Ultralytics Results API:
            results.results_dict: {'metrics/mAP50(B)': ..., ...}
            results.best_fitness: best epoch fitness value
        """
        try:
            rd          = results.results_dict
            map50       = float(rd.get("metrics/mAP50(B)",    rd.get("metrics/mAP50",    0.0)))
            map50_95    = float(rd.get("metrics/mAP50-95(B)", rd.get("metrics/mAP50-95", 0.0)))
            precision   = float(rd.get("metrics/precision(B)", rd.get("metrics/precision", 0.0)))
            recall      = float(rd.get("metrics/recall(B)",    rd.get("metrics/recall",   0.0)))
            box_loss    = float(rd.get("train/box_loss",    0.0))
            cls_loss    = float(rd.get("train/cls_loss",    0.0))
            epochs_done = int(getattr(results, "epoch",  DEFAULT_EPOCHS))
            best_epoch  = int(getattr(results, "best_fitness_epoch", epochs_done))

        except Exception as exc:
            logger.warning(
                f"[training] Metrics parse xatosi (defaults): {exc}"
            )
            map50     = 0.0
            map50_95  = 0.0
            precision = 0.0
            recall    = 0.0
            box_loss  = 0.0
            cls_loss  = 0.0
            epochs_done = DEFAULT_EPOCHS
            best_epoch  = DEFAULT_EPOCHS

        return TrainingMetrics(
            map50        = map50,
            map50_95     = map50_95,
            precision    = precision,
            recall       = recall,
            box_loss     = box_loss,
            cls_loss     = cls_loss,
            epochs_done  = epochs_done,
            best_epoch   = best_epoch,
            duration_sec = round(duration_sec, 1),
        )

    def should_deploy(
        self,
        new_metrics:     TrainingMetrics,
        current_map50:   float = 0.0,
    ) -> bool:
        """
        Yangi model avtomatik deploy qilinishi kerakmi?

        Faqat mAP50 yetarlicha yaxshilangan bo'lsa.
        """
        improvement = new_metrics.map50 - current_map50
        should = improvement >= MIN_IMPROVEMENT_MAP50
        logger.info(
            f"[training] Deploy check: "
            f"new_mAP50={new_metrics.map50:.4f} | "
            f"current={current_map50:.4f} | "
            f"improvement={improvement:.4f} | "
            f"threshold={MIN_IMPROVEMENT_MAP50} | "
            f"deploy={should}"
        )
        return should