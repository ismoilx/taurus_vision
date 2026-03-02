"""
Taurus Vision — Dataset Builder (Sprint 15-16)

Diskdagi yig'ilgan framlardan Ultralytics YOLO formatida
dataset yaratadi.

YOLO DATASET TUZILMASI:
    {dataset_dir}/
    ├── images/
    │   ├── train/   ← 80% kadrlar
    │   └── val/     ← 20% kadrlar
    ├── labels/
    │   ├── train/
    │   └── val/
    └── data.yaml    ← Ultralytics konfiguratsiya fayli

data.yaml namunasi:
    path: /app/data/training/datasets/run_42
    train: images/train
    val:   images/val
    nc:    2
    names: {0: cow, 1: sheep}

SINF MAPPING:
    FrameCollector bilan mos:
        COCO class 19 (cow)   → 0
        COCO class 20 (sheep) → 1

MINIMALLIK TALABI:
    Muvaffaqiyatli dataset yasash uchun kamida
    MIN_IMAGES_REQUIRED (default: 30) ta rasm kerak.
    Val uchun kamida 5 ta.
"""

import logging
import random
import shutil
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Training/validation split
TRAIN_RATIO = 0.80       # 80% train, 20% val

# Minimum talablar
MIN_IMAGES_REQUIRED  = 30
MIN_VAL_IMAGES       = 5

# Class konfiguratsiyasi
TRAINING_CLASS_NAMES: dict[int, str] = {0: "cow", 1: "sheep"}
NUM_CLASSES = len(TRAINING_CLASS_NAMES)


class DatasetBuildError(Exception):
    """Dataset yaratishda xato."""


class DatasetBuilder:
    """
    Yig'ilgan framlardan YOLO dataset yaratuvchi.

    FOYDALANISH:
        builder = DatasetBuilder(
            frames_dir="/app/data/training/frames",
            datasets_dir="/app/data/training/datasets",
        )
        result = builder.build(run_id=42)
        # result.dataset_dir — tayyor dataset papkasi
        # result.n_train, result.n_val — rasm sonlari
    """

    def __init__(
        self,
        frames_dir:   str,
        datasets_dir: str,
        train_ratio:  float = TRAIN_RATIO,
        seed:         int   = 42,
    ) -> None:
        self._frames_dir   = Path(frames_dir)
        self._datasets_dir = Path(datasets_dir)
        self._train_ratio  = train_ratio
        self._seed         = seed

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def build(self, run_id: int) -> "DatasetInfo":
        """
        Dataset yaratish.

        Args:
            run_id: TrainingRun ID (papka nomi uchun)

        Returns:
            DatasetInfo — yaratilgan dataset ma'lumotlari

        Raises:
            DatasetBuildError: Agar kadrlar yetarli bo'lmasa
        """
        logger.info(f"[dataset] Building dataset for run_id={run_id}")

        # 1. Frame juftlarini topish
        pairs = self._find_frame_pairs()
        n_total = len(pairs)

        if n_total < MIN_IMAGES_REQUIRED:
            raise DatasetBuildError(
                f"Yetarli kadr yo'q: {n_total} ta mavjud, "
                f"kamida {MIN_IMAGES_REQUIRED} ta kerak. "
                f"Kameralardan ko'proq kadr to'plang."
            )

        logger.info(f"[dataset] Found {n_total} valid frame pairs")

        # 2. Shuffling va split
        random.seed(self._seed)
        random.shuffle(pairs)

        split_idx = max(
            MIN_VAL_IMAGES,
            int(n_total * (1 - self._train_ratio)),
        )
        val_pairs   = pairs[:split_idx]
        train_pairs = pairs[split_idx:]

        if len(val_pairs) < MIN_VAL_IMAGES:
            raise DatasetBuildError(
                f"Val set uchun yetarli kadr yo'q: "
                f"{len(val_pairs)} < {MIN_VAL_IMAGES}"
            )

        # 3. Dataset papkasini yaratish
        dataset_dir = self._datasets_dir / str(run_id)
        self._create_structure(dataset_dir)

        # 4. Fayllarni ko'chirish
        self._copy_split(train_pairs, dataset_dir, "train")
        self._copy_split(val_pairs,   dataset_dir, "val")

        # 5. data.yaml yaratish
        yaml_path = self._write_yaml(dataset_dir)

        result = DatasetInfo(
            run_id      = run_id,
            dataset_dir = str(dataset_dir),
            yaml_path   = str(yaml_path),
            n_train     = len(train_pairs),
            n_val       = len(val_pairs),
            n_total     = n_total,
            classes     = TRAINING_CLASS_NAMES,
        )

        logger.info(
            f"[dataset] Build complete | "
            f"train={result.n_train} | val={result.n_val} | "
            f"dir={dataset_dir}"
        )
        return result

    def get_frame_count(self) -> int:
        """Diskda mavjud to'g'ri kadr juftlari soni."""
        return len(self._find_frame_pairs())

    def cleanup_dataset(self, run_id: int) -> None:
        """Yaratilgan dataset ni o'chirish (diskni bo'shatish uchun)."""
        dataset_dir = self._datasets_dir / str(run_id)
        if dataset_dir.exists():
            shutil.rmtree(dataset_dir, ignore_errors=True)
            logger.info(f"[dataset] Cleaned up dataset for run_id={run_id}")

    # =========================================================================
    # PRIVATE
    # =========================================================================

    def _find_frame_pairs(self) -> list[tuple[Path, Path]]:
        """
        frames/ papkasidagi to'g'ri jpg+txt juftlarini topish.

        Qaytaradi: [(jpg_path, txt_path), ...]
        Faqat ikkalasi ham mavjud va txt bo'sh bo'lmagan juftlar.
        """
        pairs = []

        if not self._frames_dir.exists():
            logger.warning(f"[dataset] Frames dir not found: {self._frames_dir}")
            return pairs

        for jpg in sorted(self._frames_dir.glob("*.jpg")):
            txt = jpg.with_suffix(".txt")
            if not txt.exists():
                continue
            content = txt.read_text(encoding="utf-8").strip()
            if not content:
                continue
            # Labellar to'g'ri formatda ekanligini tekshirish
            if self._is_valid_label(content):
                pairs.append((jpg, txt))

        return pairs

    @staticmethod
    def _is_valid_label(content: str) -> bool:
        """YOLO label fayli to'g'ri formatda ekanligini tekshirish."""
        for line in content.strip().splitlines():
            parts = line.strip().split()
            if len(parts) != 5:
                return False
            try:
                cls_idx = int(parts[0])
                cx, cy, bw, bh = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                if cls_idx not in TRAINING_CLASS_NAMES:
                    return False
                if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0):
                    return False
                if not (0.001 <= bw <= 1.0 and 0.001 <= bh <= 1.0):
                    return False
            except (ValueError, IndexError):
                return False
        return True

    @staticmethod
    def _create_structure(dataset_dir: Path) -> None:
        """Dataset papka tuzilmasini yaratish."""
        for split in ("train", "val"):
            (dataset_dir / "images" / split).mkdir(parents=True, exist_ok=True)
            (dataset_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _copy_split(
        pairs:       list[tuple[Path, Path]],
        dataset_dir: Path,
        split:       str,
    ) -> None:
        """Frame juftlarini train yoki val papkasiga nusxalash."""
        for jpg, txt in pairs:
            shutil.copy2(jpg, dataset_dir / "images" / split / jpg.name)
            shutil.copy2(txt, dataset_dir / "labels" / split / txt.name)

    @staticmethod
    def _write_yaml(dataset_dir: Path) -> Path:
        """
        Ultralytics data.yaml faylini yozish.

        path → to'liq absolyut yo'l (Docker ichida ishonchli).
        """
        yaml_content = {
            "path":  str(dataset_dir.resolve()),
            "train": "images/train",
            "val":   "images/val",
            "nc":    NUM_CLASSES,
            "names": TRAINING_CLASS_NAMES,
        }

        yaml_path = dataset_dir / "data.yaml"
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(yaml_content, f, default_flow_style=False, allow_unicode=True)

        logger.debug(f"[dataset] data.yaml written: {yaml_path}")
        return yaml_path


class DatasetInfo:
    """Dataset yaratish natijasi."""

    def __init__(
        self,
        run_id:      int,
        dataset_dir: str,
        yaml_path:   str,
        n_train:     int,
        n_val:       int,
        n_total:     int,
        classes:     dict[int, str],
    ) -> None:
        self.run_id      = run_id
        self.dataset_dir = dataset_dir
        self.yaml_path   = yaml_path
        self.n_train     = n_train
        self.n_val       = n_val
        self.n_total     = n_total
        self.classes     = classes

    def to_dict(self) -> dict:
        return {
            "run_id":      self.run_id,
            "dataset_dir": self.dataset_dir,
            "yaml_path":   self.yaml_path,
            "n_train":     self.n_train,
            "n_val":       self.n_val,
            "n_total":     self.n_total,
            "classes":     self.classes,
        }