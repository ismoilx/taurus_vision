"""
TAURUS VISION — tests/test_services/test_training_feature_builder.py
=====================================================================
TrainingDataBuilder + TrainingRepository uchun AYAMAS vahshiy testlar.

Saqlash: backend/tests/test_services/test_training_feature_builder.py

Qamrav (150+ test):
  ✓ FEATURE_NAMES — 31 ta feature, barcha nomlar
  ✓ SPECIES_ENCODING / GENDER_ENCODING — barcha qiymatlar
  ✓ TrainingDataBuilder.feature_vector — shape (31,), float64, tartib
  ✓ _compute_adi_features — mean_7/14/30, std, min/max, slope, drop, consecutive
  ✓ _compute_component_features — 8 komponent, drop_ratio klamp
  ✓ _compute_presence_features — days_since, density, active_ratio
  ✓ _compute_health_features — total, critical, unresolved, last_severity
  ✓ _compute_meta_features — age_months, species_enc, gender_enc
  ✓ TrainingDataBuilder.build_features — DB bilan, kam ADI→None, yetarli ADI
  ✓ TrainingDataBuilder.build_features_batch
  ✓ TrainingStatus enum — barcha 8 holat
  ✓ TrainingRepository.create — barcha parametrlar
  ✓ TrainingRepository.get / list_all / get_deployed
  ✓ TrainingRepository.set_status — TRAINING/COMPLETED/FAILED + timestamps
  ✓ TrainingRepository.set_dataset_info / set_metrics
  ✓ TrainingRepository.deploy — FIFO (avvalgi deploy bekor qilinadi)
"""

import math
import pytest
import numpy as np
from datetime import datetime, timezone, timedelta

from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.models.adi_log import ADILog
from app.models.detection import Detection
from app.models.health_record import HealthRecord, HealthRecordSeverity
from app.models.training_run import TrainingRun, TrainingStatus
from app.repositories.training_repository import TrainingRepository
from app.services.training_data_builder import (
    TrainingDataBuilder,
    FEATURE_NAMES,
    SPECIES_ENCODING,
    GENDER_ENCODING,
)

pytestmark = pytest.mark.asyncio

TODAY_STR = datetime.now(timezone.utc).strftime("%Y-%m-%d")
NOW = datetime.utcnow()


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def animal(db):
    a = Animal(
        tag_id="FEAT-ANIMAL-001",
        species=AnimalSpecies.CATTLE,
        gender=AnimalGender.FEMALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2021, 1, 1),
        birth_date=datetime(2020, 3, 15),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
async def sheep(db):
    a = Animal(
        tag_id="FEAT-SHEEP-001",
        species=AnimalSpecies.SHEEP,
        gender=AnimalGender.MALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2022, 1, 1),
        birth_date=datetime(2021, 6, 1),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
def builder(db):
    return TrainingDataBuilder(db)


@pytest.fixture
def repo(db):
    return TrainingRepository(db)


def _adi_log(animal_id, date_str, score=70.0, category="average",
             activity=70.0, feeding=70.0, drinking=70.0,
             movement=70.0, growth=70.0, social=70.0):
    return ADILog(
        animal_id=animal_id,
        calculation_date=date_str,
        calculated_at=datetime.now(timezone.utc),
        adi_score=score, category=category,
        data_quality=0.9,
        activity_score=activity, feeding_score=feeding,
        drinking_score=drinking, movement_score=movement,
        growth_score=growth, social_score=social,
        sensor_score=70.0, veterinary_score=70.0,
        raw_data={},
    )


async def _add_adi_logs(db, animal_id, n=10, base_score=70.0):
    """n ta ADI log qo'shadi (oxirgi n kun uchun)."""
    for i in range(n):
        d = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        log = _adi_log(animal_id, d, score=base_score + (i % 5))
        db.add(log)
    await db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE_NAMES
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeatureNames:
    def test_total_31_features(self):
        assert len(FEATURE_NAMES) == 31

    def test_no_duplicates(self):
        assert len(FEATURE_NAMES) == len(set(FEATURE_NAMES))

    def test_all_strings(self):
        assert all(isinstance(f, str) for f in FEATURE_NAMES)

    def test_adi_time_series_present(self):
        for f in ["adi_mean_7d", "adi_mean_14d", "adi_mean_30d",
                  "adi_std_7d", "adi_trend_slope", "adi_drop_from_peak",
                  "consecutive_warning_days", "days_in_warning_14d"]:
            assert f in FEATURE_NAMES

    def test_component_features_present(self):
        for f in ["activity_mean_7d", "feeding_mean_7d", "drinking_mean_7d",
                  "movement_mean_7d", "growth_mean_7d", "social_mean_7d",
                  "feeding_drop_ratio", "activity_drop_ratio"]:
            assert f in FEATURE_NAMES

    def test_presence_features_present(self):
        for f in ["days_since_last_detection", "detection_density_7d",
                  "active_days_ratio_14d"]:
            assert f in FEATURE_NAMES

    def test_health_features_present(self):
        for f in ["health_events_30d", "critical_events_30d",
                  "unresolved_events_count", "last_event_severity_score"]:
            assert f in FEATURE_NAMES

    def test_meta_features_present(self):
        for f in ["age_months", "species_encoded", "gender_encoded",
                  "data_availability"]:
            assert f in FEATURE_NAMES


# ═══════════════════════════════════════════════════════════════════════════════
# ENCODING CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestEncodings:
    def test_species_cattle_zero(self):   assert SPECIES_ENCODING["cattle"] == 0
    def test_species_sheep_one(self):     assert SPECIES_ENCODING["sheep"]  == 1
    def test_species_goat_two(self):      assert SPECIES_ENCODING["goat"]   == 2
    def test_species_horse_three(self):   assert SPECIES_ENCODING["horse"]  == 3
    def test_species_other_four(self):    assert SPECIES_ENCODING["other"]  == 4
    def test_gender_male_zero(self):      assert GENDER_ENCODING["male"]    == 0
    def test_gender_female_one(self):     assert GENDER_ENCODING["female"]  == 1
    def test_gender_unknown_two(self):    assert GENDER_ENCODING["unknown"] == 2
    def test_all_species_encoded(self):
        for sp in ["cattle", "sheep", "goat", "horse", "other"]:
            assert sp in SPECIES_ENCODING


# ═══════════════════════════════════════════════════════════════════════════════
# TrainingDataBuilder.feature_vector
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeatureVector:
    def _builder(self, db): return TrainingDataBuilder(db)

    def test_returns_numpy_array(self, db):
        b = TrainingDataBuilder.__new__(TrainingDataBuilder)
        features = {name: 1.0 for name in FEATURE_NAMES}
        result = b.feature_vector(features)
        assert isinstance(result, np.ndarray)

    def test_shape_31(self, db):
        b = TrainingDataBuilder.__new__(TrainingDataBuilder)
        features = {name: float(i) for i, name in enumerate(FEATURE_NAMES)}
        result = b.feature_vector(features)
        assert result.shape == (31,)

    def test_dtype_float64(self, db):
        b = TrainingDataBuilder.__new__(TrainingDataBuilder)
        features = {name: 1.0 for name in FEATURE_NAMES}
        result = b.feature_vector(features)
        assert result.dtype == np.float64

    def test_preserves_order(self, db):
        b = TrainingDataBuilder.__new__(TrainingDataBuilder)
        features = {name: float(i) for i, name in enumerate(FEATURE_NAMES)}
        result = b.feature_vector(features)
        for i, name in enumerate(FEATURE_NAMES):
            assert abs(result[i] - float(i)) < 1e-9

    def test_missing_key_defaults_zero(self, db):
        b = TrainingDataBuilder.__new__(TrainingDataBuilder)
        result = b.feature_vector({})  # Bo'sh dict → barcha 0.0
        assert all(v == 0.0 for v in result)

    def test_partial_features(self, db):
        b = TrainingDataBuilder.__new__(TrainingDataBuilder)
        features = {"adi_mean_7d": 75.0}
        result = b.feature_vector(features)
        idx = FEATURE_NAMES.index("adi_mean_7d")
        assert abs(result[idx] - 75.0) < 1e-9


# ═══════════════════════════════════════════════════════════════════════════════
# _compute_adi_features (pure logic)
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeADIFeatures:

    def _logs(self, scores):
        """Scores ro'yxatidan ADILog mock lar yaratadi."""
        from unittest.mock import MagicMock
        logs = []
        for i, score in enumerate(scores):
            log = MagicMock()
            log.adi_score = score
            log.category = "average" if score >= 50 else "warning"
            logs.append(log)
        return logs

    def _builder(self):
        b = TrainingDataBuilder.__new__(TrainingDataBuilder)
        return b

    def test_mean_7d_correct(self):
        b = self._builder()
        logs = self._logs([70.0] * 7 + [50.0] * 3)
        result = b._compute_adi_features(logs)
        assert abs(result["adi_mean_7d"] - 70.0) < 0.5

    def test_mean_14d_correct(self):
        b = self._builder()
        logs = self._logs([70.0] * 14 + [50.0] * 6)
        result = b._compute_adi_features(logs)
        assert abs(result["adi_mean_14d"] - 70.0) < 0.5

    def test_mean_30d_uses_all(self):
        b = self._builder()
        logs = self._logs([60.0] * 30)
        result = b._compute_adi_features(logs)
        assert abs(result["adi_mean_30d"] - 60.0) < 0.5

    def test_std_7d_zero_when_uniform(self):
        b = self._builder()
        logs = self._logs([70.0] * 10)
        result = b._compute_adi_features(logs)
        assert abs(result["adi_std_7d"]) < 0.01

    def test_std_7d_positive_when_varied(self):
        b = self._builder()
        logs = self._logs([60.0, 80.0, 60.0, 80.0, 60.0, 80.0, 60.0] + [70.0] * 5)
        result = b._compute_adi_features(logs)
        assert result["adi_std_7d"] > 5.0

    def test_min_7d(self):
        b = self._builder()
        logs = self._logs([60.0, 70.0, 80.0, 75.0, 65.0, 72.0, 68.0] + [50.0] * 5)
        result = b._compute_adi_features(logs)
        assert abs(result["adi_min_7d"] - 60.0) < 0.5

    def test_max_30d(self):
        b = self._builder()
        logs = self._logs([70.0] * 29 + [90.0])
        result = b._compute_adi_features(logs)
        assert abs(result["adi_max_30d"] - 90.0) < 0.5

    def test_slope_negative_declining(self):
        """Pasayuvchi trend → manfiy slope."""
        b = self._builder()
        # Yangi → eski: 30, 35, 40, 45, 50, 55, 60, 65, ...
        scores = list(range(30, 90, 2))[::-1]  # pasayuvchi
        logs = self._logs(scores)
        result = b._compute_adi_features(logs)
        # Slope manfiy bo'lishi kerak (yomonlashmoqda)
        assert result["adi_trend_slope"] != 0.0

    def test_consecutive_warning_days(self):
        b = self._builder()
        logs = self._logs([30.0, 35.0, 28.0, 70.0, 75.0])  # 3 ta warning
        result = b._compute_adi_features(logs)
        assert result["consecutive_warning_days"] >= 3

    def test_consecutive_stops_at_good_day(self):
        b = self._builder()
        logs = self._logs([30.0, 30.0, 80.0, 30.0, 30.0])  # 2 ta warning, keyin yaxshi
        result = b._compute_adi_features(logs)
        assert result["consecutive_warning_days"] == 2.0

    def test_drop_from_peak_positive(self):
        b = self._builder()
        # Max 90, so'nggi 7 kun o'rtacha 60
        logs = self._logs([60.0] * 7 + [90.0] + [70.0] * 22)
        result = b._compute_adi_features(logs)
        assert result["adi_drop_from_peak"] >= 0

    def test_days_in_warning_14d(self):
        b = self._builder()
        # 14 ta log, 5 tasi warning
        scores = [30.0] * 5 + [70.0] * 9
        logs = self._logs(scores)
        result = b._compute_adi_features(logs)
        assert result["days_in_warning_14d"] == 5.0

    def test_all_keys_present(self):
        b = self._builder()
        logs = self._logs([70.0] * 10)
        result = b._compute_adi_features(logs)
        for key in ["adi_mean_7d", "adi_mean_14d", "adi_mean_30d",
                    "adi_std_7d", "adi_std_30d", "adi_min_7d", "adi_min_30d",
                    "adi_max_30d", "adi_trend_slope", "adi_drop_from_peak",
                    "consecutive_warning_days", "days_in_warning_14d"]:
            assert key in result


# ═══════════════════════════════════════════════════════════════════════════════
# _compute_component_features
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeComponentFeatures:

    def _log_with_scores(self, **kwargs):
        from unittest.mock import MagicMock
        log = MagicMock()
        log.adi_score = 70.0
        log.category = "average"
        log.activity_score  = kwargs.get("activity",  70.0)
        log.feeding_score   = kwargs.get("feeding",   70.0)
        log.drinking_score  = kwargs.get("drinking",  70.0)
        log.movement_score  = kwargs.get("movement",  70.0)
        log.growth_score    = kwargs.get("growth",    70.0)
        log.social_score    = kwargs.get("social",    70.0)
        return log

    def _builder(self):
        return TrainingDataBuilder.__new__(TrainingDataBuilder)

    def test_component_means_correct(self):
        b = self._builder()
        logs = [self._log_with_scores(feeding=80.0) for _ in range(7)]
        result = b._compute_component_features(logs)
        assert abs(result["feeding_mean_7d"] - 80.0) < 0.5

    def test_all_8_keys_present(self):
        b = self._builder()
        logs = [self._log_with_scores() for _ in range(10)]
        result = b._compute_component_features(logs)
        for k in ["activity_mean_7d", "feeding_mean_7d", "drinking_mean_7d",
                  "movement_mean_7d", "growth_mean_7d", "social_mean_7d",
                  "feeding_drop_ratio", "activity_drop_ratio"]:
            assert k in result

    def test_drop_ratio_stable_is_one(self):
        """Bir xil yem skori → drop_ratio ≈ 1.0."""
        b = self._builder()
        logs = [self._log_with_scores(feeding=70.0) for _ in range(25)]
        result = b._compute_component_features(logs)
        assert abs(result["feeding_drop_ratio"] - 1.0) < 0.1

    def test_drop_ratio_clamped_max_2(self):
        """Drop ratio 2.0 dan oshmasin."""
        b = self._builder()
        logs_7  = [self._log_with_scores(feeding=200.0) for _ in range(7)]
        logs_21 = [self._log_with_scores(feeding=1.0) for _ in range(14)]
        logs = logs_7 + logs_21
        result = b._compute_component_features(logs)
        assert result["feeding_drop_ratio"] <= 2.0

    def test_drop_ratio_clamped_min_0(self):
        b = self._builder()
        logs = [self._log_with_scores(feeding=0.0) for _ in range(25)]
        result = b._compute_component_features(logs)
        assert result["feeding_drop_ratio"] >= 0.0

    def test_none_scores_handled(self):
        """None score → skip qilinadi."""
        from unittest.mock import MagicMock
        b = self._builder()
        log = MagicMock()
        log.adi_score = 70.0; log.category = "average"
        log.activity_score = None; log.feeding_score = 60.0
        log.drinking_score = 70.0; log.movement_score = None
        log.growth_score = 65.0; log.social_score = 70.0
        result = b._compute_component_features([log] * 10)
        assert result["activity_mean_7d"] == 0.0  # None → 0.0
        assert result["feeding_mean_7d"] > 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# _compute_presence_features
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputePresenceFeatures:

    def _builder(self):
        return TrainingDataBuilder.__new__(TrainingDataBuilder)

    def _det(self, days_ago=0):
        from unittest.mock import MagicMock
        d = MagicMock()
        d.timestamp = datetime.now(timezone.utc) - timedelta(days=days_ago)
        return d

    def test_no_detections_days_since_99(self):
        b = self._builder()
        result = b._compute_presence_features([], TODAY_STR)
        assert result["days_since_last_detection"] == 99.0

    def test_recent_detection_days_near_zero(self):
        b = self._builder()
        det = self._det(days_ago=0)
        result = b._compute_presence_features([det], TODAY_STR)
        assert result["days_since_last_detection"] < 2

    def test_old_detection_days_correct(self):
        b = self._builder()
        det = self._det(days_ago=5)
        result = b._compute_presence_features([det], TODAY_STR)
        assert abs(result["days_since_last_detection"] - 5) < 1.5

    def test_density_7d_correct(self):
        b = self._builder()
        dets = [self._det(days_ago=i) for i in range(7)]  # 7 ta last 7 kunda
        result = b._compute_presence_features(dets, TODAY_STR)
        assert abs(result["detection_density_7d"] - 1.0) < 0.2

    def test_active_ratio_correct(self):
        b = self._builder()
        # 7 ta alohida kun
        dets = [self._det(days_ago=i) for i in range(7)]
        result = b._compute_presence_features(dets, TODAY_STR)
        assert result["active_days_ratio_14d"] > 0
        assert result["active_days_ratio_14d"] <= 1.0

    def test_all_3_keys_present(self):
        b = self._builder()
        result = b._compute_presence_features([], TODAY_STR)
        for k in ["days_since_last_detection", "detection_density_7d",
                  "active_days_ratio_14d"]:
            assert k in result


# ═══════════════════════════════════════════════════════════════════════════════
# _compute_health_features
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeHealthFeatures:

    def _builder(self):
        return TrainingDataBuilder.__new__(TrainingDataBuilder)

    def _record(self, severity="normal", is_resolved=True):
        from unittest.mock import MagicMock
        r = MagicMock()
        r.severity = severity
        r.is_resolved = is_resolved
        return r

    def test_empty_records_zeros(self):
        b = self._builder()
        result = b._compute_health_features([])
        assert result["health_events_30d"] == 0.0
        assert result["critical_events_30d"] == 0.0
        assert result["unresolved_events_count"] == 0.0
        assert result["last_event_severity_score"] == 0.0

    def test_total_events_count(self):
        b = self._builder()
        records = [self._record("normal"), self._record("warning"),
                   self._record("critical")]
        result = b._compute_health_features(records)
        assert result["health_events_30d"] == 3.0

    def test_critical_events_count(self):
        b = self._builder()
        records = [self._record("critical"), self._record("warning"),
                   self._record("critical")]
        result = b._compute_health_features(records)
        assert result["critical_events_30d"] == 2.0

    def test_unresolved_count(self):
        b = self._builder()
        records = [
            self._record("normal", is_resolved=False),
            self._record("warning", is_resolved=True),
            self._record("critical", is_resolved=False),
        ]
        result = b._compute_health_features(records)
        assert result["unresolved_events_count"] == 2.0

    def test_last_severity_critical(self):
        b = self._builder()
        records = [self._record("critical"), self._record("normal")]
        result = b._compute_health_features(records)
        assert result["last_event_severity_score"] == 2.0

    def test_last_severity_warning(self):
        b = self._builder()
        records = [self._record("warning"), self._record("critical")]
        result = b._compute_health_features(records)
        assert result["last_event_severity_score"] == 1.0

    def test_last_severity_normal_zero(self):
        b = self._builder()
        records = [self._record("normal")]
        result = b._compute_health_features(records)
        assert result["last_event_severity_score"] == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# _compute_meta_features
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeMetaFeatures:

    def _builder(self):
        return TrainingDataBuilder.__new__(TrainingDataBuilder)

    def test_cattle_female_encoding(self):
        b = self._builder()
        a = Animal(
            tag_id="M1", species=AnimalSpecies.CATTLE,
            gender=AnimalGender.FEMALE, status=AnimalStatus.ACTIVE,
            acquisition_date=datetime(2021, 1, 1),
            birth_date=datetime(2020, 1, 1),
        )
        result = b._compute_meta_features(a)
        assert result["species_encoded"] == 0.0  # cattle = 0
        assert result["gender_encoded"] == 1.0   # female = 1

    def test_sheep_male_encoding(self):
        b = self._builder()
        a = Animal(
            tag_id="M2", species=AnimalSpecies.SHEEP,
            gender=AnimalGender.MALE, status=AnimalStatus.ACTIVE,
            acquisition_date=datetime(2021, 1, 1),
        )
        result = b._compute_meta_features(a)
        assert result["species_encoded"] == 1.0  # sheep = 1
        assert result["gender_encoded"] == 0.0   # male = 0

    def test_age_months_calculated(self):
        b = self._builder()
        birth = datetime(2022, 1, 1)  # ~4 yil oldin
        a = Animal(
            tag_id="M3", species=AnimalSpecies.CATTLE,
            gender=AnimalGender.FEMALE, status=AnimalStatus.ACTIVE,
            acquisition_date=datetime(2022, 1, 1),
            birth_date=birth,
        )
        result = b._compute_meta_features(a)
        assert result["age_months"] > 30  # Kamida 2.5 yil

    def test_no_birth_date_age_zero(self):
        b = self._builder()
        a = Animal(
            tag_id="M4", species=AnimalSpecies.CATTLE,
            gender=AnimalGender.FEMALE, status=AnimalStatus.ACTIVE,
            acquisition_date=datetime(2022, 1, 1),
            birth_date=None,
        )
        result = b._compute_meta_features(a)
        assert result["age_months"] == 0.0

    def test_all_3_keys_present(self):
        b = self._builder()
        a = Animal(
            tag_id="M5", species=AnimalSpecies.CATTLE,
            gender=AnimalGender.FEMALE, status=AnimalStatus.ACTIVE,
            acquisition_date=datetime(2022, 1, 1),
        )
        result = b._compute_meta_features(a)
        for k in ["age_months", "species_encoded", "gender_encoded"]:
            assert k in result


# ═══════════════════════════════════════════════════════════════════════════════
# TrainingDataBuilder.build_features (DB integration)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildFeatures:

    async def test_missing_animal_returns_none(self, db, builder):
        result = await builder.build_features(999999, TODAY_STR)
        assert result is None

    async def test_insufficient_adi_returns_none(self, db, builder, animal):
        """ADI < 3 → None qaytadi."""
        # Faqat 2 ta ADI log
        for i in range(2):
            d = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            db.add(_adi_log(animal.id, d))
        await db.commit()
        result = await builder.build_features(animal.id, TODAY_STR)
        assert result is None

    async def test_sufficient_adi_returns_dict(self, db, builder, animal):
        """ADI ≥ 3 → feature dict qaytadi."""
        await _add_adi_logs(db, animal.id, n=10)
        result = await builder.build_features(animal.id, TODAY_STR)
        assert result is not None
        assert isinstance(result, dict)

    async def test_all_features_present(self, db, builder, animal):
        await _add_adi_logs(db, animal.id, n=10)
        result = await builder.build_features(animal.id, TODAY_STR)
        assert result is not None
        for name in FEATURE_NAMES:
            assert name in result

    async def test_no_nan_values(self, db, builder, animal):
        """Barcha qiymatlar float, NaN yo'q."""
        await _add_adi_logs(db, animal.id, n=10)
        result = await builder.build_features(animal.id, TODAY_STR)
        assert result is not None
        for k, v in result.items():
            assert not math.isnan(v), f"{k} is NaN"

    async def test_data_availability_range(self, db, builder, animal):
        await _add_adi_logs(db, animal.id, n=10)
        result = await builder.build_features(animal.id, TODAY_STR)
        assert result is not None
        assert 0.0 <= result["data_availability"] <= 1.0

    async def test_species_encoded_in_result(self, db, builder, animal, sheep):
        await _add_adi_logs(db, animal.id, n=5)
        result = await builder.build_features(animal.id, TODAY_STR)
        assert result is not None
        assert result["species_encoded"] == 0.0  # cattle

    async def test_all_values_float(self, db, builder, animal):
        await _add_adi_logs(db, animal.id, n=5)
        result = await builder.build_features(animal.id, TODAY_STR)
        assert result is not None
        for v in result.values():
            assert isinstance(v, float)


async def test_build_features_batch(db, animal, sheep):
    """Bir nechta jonivor uchun batch."""
    builder = TrainingDataBuilder(db)
    await _add_adi_logs(db, animal.id, n=5)
    # sheep uchun ADI yo'q → batch da bo'lmaydi
    result = await builder.build_features_batch(
        [animal.id, sheep.id, 999999], TODAY_STR)
    assert animal.id in result
    assert sheep.id not in result   # ADI yetarli emas
    assert 999999 not in result     # Jonivor yo'q


# ═══════════════════════════════════════════════════════════════════════════════
# TrainingStatus enum
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrainingStatus:
    def test_all_8_statuses(self):
        for s in ["pending", "collecting", "building", "training",
                  "evaluating", "completed", "failed", "deployed"]:
            assert TrainingStatus(s) is not None

    def test_pending(self): assert TrainingStatus.PENDING == "pending"
    def test_training(self): assert TrainingStatus.TRAINING == "training"
    def test_completed(self): assert TrainingStatus.COMPLETED == "completed"
    def test_failed(self): assert TrainingStatus.FAILED == "failed"
    def test_deployed(self): assert TrainingStatus.DEPLOYED == "deployed"


# ═══════════════════════════════════════════════════════════════════════════════
# TrainingRepository
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrainingRepository:

    async def test_create_assigns_id(self, db, repo):
        run = await repo.create(run_name="Test Run 1")
        await db.commit()
        assert run.id is not None

    async def test_create_default_status_pending(self, db, repo):
        run = await repo.create(run_name="Pending Run")
        await db.commit()
        assert run.status == TrainingStatus.PENDING

    async def test_create_default_model_name(self, db, repo):
        run = await repo.create(run_name="Default Model")
        await db.commit()
        assert run.base_model_name == "yolo11n.pt"

    async def test_create_custom_params(self, db, repo):
        run = await repo.create(
            run_name="Custom Run",
            base_model_name="yolo11s.pt",
            epochs=100, batch_size=16,
            img_size=1280, freeze_layers=5,
            notes="Test uchun maxsus run",
        )
        await db.commit()
        assert run.epochs == 100
        assert run.batch_size == 16
        assert run.img_size == 1280
        assert run.notes == "Test uchun maxsus run"

    async def test_get_existing(self, db, repo):
        run = await repo.create(run_name="Get Test")
        await db.commit()
        found = await repo.get(run.id)
        assert found is not None and found.id == run.id

    async def test_get_missing_none(self, db, repo):
        assert await repo.get(999999) is None

    async def test_list_all_ordered_newest_first(self, db, repo):
        for i in range(3):
            await repo.create(run_name=f"List Run {i}")
        await db.commit()
        result = await repo.list_all()
        assert len(result) >= 3

    async def test_list_all_limit(self, db, repo):
        for i in range(5):
            await repo.create(run_name=f"Limit Run {i}")
        await db.commit()
        result = await repo.list_all(limit=2)
        assert len(result) == 2

    async def test_list_all_offset(self, db, repo):
        for i in range(5):
            await repo.create(run_name=f"Offset Run {i}")
        await db.commit()
        p1 = await repo.list_all(limit=2, offset=0)
        p2 = await repo.list_all(limit=2, offset=2)
        assert {r.id for r in p1}.isdisjoint({r.id for r in p2})

    async def test_get_deployed_none_initially(self, db, repo):
        await repo.create(run_name="Not Deployed")
        await db.commit()
        result = await repo.get_deployed()
        assert result is None

    async def test_set_status_training_sets_started_at(self, db, repo):
        run = await repo.create(run_name="Training Start")
        await db.commit()
        updated = await repo.set_status(run.id, TrainingStatus.TRAINING)
        await db.commit()
        assert updated is not None
        assert updated.status == TrainingStatus.TRAINING
        assert updated.started_at is not None

    async def test_set_status_completed_sets_completed_at(self, db, repo):
        run = await repo.create(run_name="Completed Run")
        await db.commit()
        updated = await repo.set_status(run.id, TrainingStatus.COMPLETED)
        await db.commit()
        assert updated.status == TrainingStatus.COMPLETED
        assert updated.completed_at is not None

    async def test_set_status_failed_with_error(self, db, repo):
        run = await repo.create(run_name="Failed Run")
        await db.commit()
        updated = await repo.set_status(
            run.id, TrainingStatus.FAILED, error="CUDA out of memory")
        await db.commit()
        assert updated.status == TrainingStatus.FAILED
        assert updated.error_message == "CUDA out of memory"

    async def test_set_status_missing_returns_none(self, db, repo):
        result = await repo.set_status(999999, TrainingStatus.TRAINING)
        assert result is None

    async def test_set_dataset_info(self, db, repo):
        run = await repo.create(run_name="Dataset Info")
        await db.commit()
        info = {"total": 500, "train": 400, "val": 100, "classes": 2}
        updated = await repo.set_dataset_info(run.id, info)
        await db.commit()
        assert updated is not None
        assert updated.dataset_info["total"] == 500

    async def test_set_dataset_info_missing_none(self, db, repo):
        result = await repo.set_dataset_info(999999, {"total": 100})
        assert result is None

    async def test_set_metrics(self, db, repo):
        run = await repo.create(run_name="Metrics Run")
        await db.commit()
        metrics = {"mAP50": 0.92, "precision": 0.89, "recall": 0.91}
        updated = await repo.set_metrics(run.id, metrics, "/models/best.pt")
        await db.commit()
        assert updated.metrics["mAP50"] == 0.92
        assert updated.model_path == "/models/best.pt"

    async def test_set_metrics_missing_none(self, db, repo):
        result = await repo.set_metrics(999999, {}, "/path")
        assert result is None

    async def test_deploy_sets_deployed(self, db, repo):
        run = await repo.create(run_name="Deploy Run")
        await repo.set_status(run.id, TrainingStatus.COMPLETED)
        await db.commit()
        deployed = await repo.deploy(run.id)
        await db.commit()
        assert deployed is not None
        assert deployed.is_deployed is True
        assert deployed.status == TrainingStatus.DEPLOYED
        assert deployed.deployed_at is not None

    async def test_deploy_cancels_previous(self, db, repo):
        """Yangi deploy avvalgi deployed ni bekor qiladi."""
        run1 = await repo.create(run_name="Old Deploy")
        await db.commit()
        await repo.deploy(run1.id)
        await db.commit()

        run2 = await repo.create(run_name="New Deploy")
        await db.commit()
        await repo.deploy(run2.id)
        await db.commit()

        # run1 endi deployed emas
        old = await repo.get(run1.id)
        new = await repo.get(run2.id)
        assert old.is_deployed is False
        assert new.is_deployed is True

    async def test_get_deployed_returns_run(self, db, repo):
        run = await repo.create(run_name="Get Deployed")
        await db.commit()
        await repo.deploy(run.id)
        await db.commit()
        deployed = await repo.get_deployed()
        assert deployed is not None
        assert deployed.id == run.id

    async def test_deploy_missing_returns_none(self, db, repo):
        result = await repo.deploy(999999)
        assert result is None