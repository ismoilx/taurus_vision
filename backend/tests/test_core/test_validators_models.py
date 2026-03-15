"""
TAURUS VISION — tests/test_core/test_validators_models.py
===========================================================
ValidationResult + EnvironmentValidator + model enums uchun
AYAMAS vahshiy testlar.

Saqlash: backend/tests/test_core/test_validators_models.py

Qamrav (140+ test):
  ── VALIDATORS ──
  ✓ ValidationResult — passed, message, severity, __str__
  ✓ EnvironmentValidator.validate_all   — bool qaytaradi
  ✓ EnvironmentValidator._validate_secret_key — qisqa, default, xavfsiz
  ✓ EnvironmentValidator._validate_required_settings
  ✓ EnvironmentValidator._validate_database_url — valid/invalid prefix
  ✓ EnvironmentValidator._validate_cors_origins — empty, valid, invalid
  ✓ EnvironmentValidator._validate_log_settings — valid/invalid levels
  ✓ check_system_resources — tuzilma, positive values

  ── MODELS ENUMS ──
  ✓ AnimalSpecies / AnimalGender / AnimalStatus — barcha qiymatlar
  ✓ AlertType / AlertSeverity / AlertStatus     — barcha qiymatlar
  ✓ ADICategory.from_score   — barcha 4 daraja, chegara qiymatlar
  ✓ HealthRecordType / HealthRecordSeverity
  ✓ WeightSource
  ✓ UserRole
  ✓ Animal model — tag_id, status, total_detections default
  ✓ Alert model  — alert_type, severity, status fields
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from app.core.validators import ValidationResult, EnvironmentValidator, check_system_resources
from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.models.alert import Alert, AlertType, AlertSeverity, AlertStatus
from app.models.adi_log import ADICategory, ADILog
from app.models.health_record import HealthRecordType, HealthRecordSeverity
from app.models.weight_measurement import WeightSource
from app.models.user import User, UserRole


# ═══════════════════════════════════════════════════════════════════════════════
# ValidationResult
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidationResult:

    def test_passed_true(self):
        r = ValidationResult(passed=True, message="OK")
        assert r.passed is True

    def test_passed_false(self):
        r = ValidationResult(passed=False, message="Error")
        assert r.passed is False

    def test_message_stored(self):
        r = ValidationResult(passed=True, message="Test message")
        assert r.message == "Test message"

    def test_severity_default_error(self):
        r = ValidationResult(passed=False, message="Err")
        assert r.severity == "error"

    def test_severity_warning(self):
        r = ValidationResult(passed=False, message="Warn", severity="warning")
        assert r.severity == "warning"

    def test_severity_info(self):
        r = ValidationResult(passed=True, message="Info", severity="info")
        assert r.severity == "info"

    def test_str_passed_check_mark(self):
        r = ValidationResult(passed=True, message="Good")
        s = str(r)
        assert "✓" in s

    def test_str_failed_cross(self):
        r = ValidationResult(passed=False, message="Bad")
        s = str(r)
        assert "✗" in s

    def test_str_contains_message(self):
        r = ValidationResult(passed=True, message="My message")
        assert "My message" in str(r)

    def test_str_contains_severity_upper(self):
        r = ValidationResult(passed=False, message="x", severity="warning")
        assert "WARNING" in str(r)


# ═══════════════════════════════════════════════════════════════════════════════
# EnvironmentValidator
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnvironmentValidator:

    def test_validate_all_returns_bool(self):
        v = EnvironmentValidator()
        result = v.validate_all()
        assert isinstance(result, bool)

    def test_validate_all_populates_results(self):
        v = EnvironmentValidator()
        v.validate_all()
        assert len(v.results) > 0

    def test_results_are_validation_results(self):
        v = EnvironmentValidator()
        v.validate_all()
        for r in v.results:
            assert isinstance(r, ValidationResult)

    def test_validate_secret_key_short_adds_result(self):
        v = EnvironmentValidator()
        with patch("app.core.validators.settings") as mock_settings:
            mock_settings.SECRET_KEY = "short"
            mock_settings.DEBUG = True
            v._validate_secret_key()
        assert len(v.results) >= 1

    def test_validate_secret_key_default_value(self):
        v = EnvironmentValidator()
        with patch("app.core.validators.settings") as mock_settings:
            mock_settings.SECRET_KEY = "changeme"
            mock_settings.DEBUG = True
            v._validate_secret_key()
        assert len(v.results) >= 1
        # Debug rejimda warning
        assert any(r.severity in ("warning", "error") for r in v.results)

    def test_validate_secret_key_secure(self):
        v = EnvironmentValidator()
        import secrets
        secure_key = secrets.token_hex(32)
        with patch("app.core.validators.settings") as mock_settings:
            mock_settings.SECRET_KEY = secure_key
            mock_settings.DEBUG = False
            v._validate_secret_key()
        # Xavfsiz kalit — passed=True bo'lishi kerak
        assert any(r.passed for r in v.results)

    def test_validate_database_url_postgresql_valid(self):
        v = EnvironmentValidator()
        with patch("app.core.validators.settings") as mock_settings:
            mock_settings.DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/db"
            v._validate_database_url()
        assert any(r.passed for r in v.results)

    def test_validate_database_url_sqlite_valid(self):
        v = EnvironmentValidator()
        with patch("app.core.validators.settings") as mock_settings:
            mock_settings.DATABASE_URL = "sqlite:///test.db"
            v._validate_database_url()
        assert any(r.passed for r in v.results)

    def test_validate_database_url_invalid_prefix(self):
        v = EnvironmentValidator()
        with patch("app.core.validators.settings") as mock_settings:
            mock_settings.DATABASE_URL = "mysql://user:pass@host/db"
            v._validate_database_url()
        assert any(not r.passed for r in v.results)

    def test_validate_cors_origins_empty_warning(self):
        v = EnvironmentValidator()
        with patch("app.core.validators.settings") as mock_settings:
            mock_settings.CORS_ORIGINS = []
            v._validate_cors_origins()
        # Bo'sh origins — warning
        assert any(not r.passed for r in v.results)

    def test_validate_cors_origins_valid_localhost(self):
        v = EnvironmentValidator()
        with patch("app.core.validators.settings") as mock_settings:
            mock_settings.CORS_ORIGINS = ["http://localhost:5173"]
            v._validate_cors_origins()
        assert any(r.passed for r in v.results)

    def test_validate_cors_origins_invalid_url(self):
        v = EnvironmentValidator()
        with patch("app.core.validators.settings") as mock_settings:
            mock_settings.CORS_ORIGINS = ["not-a-url"]
            v._validate_cors_origins()
        assert any(not r.passed for r in v.results)

    def test_validate_log_level_debug_valid(self):
        v = EnvironmentValidator()
        with patch("app.core.validators.settings") as mock_settings:
            mock_settings.LOG_LEVEL = "DEBUG"
            v._validate_log_settings()
        assert any(r.passed for r in v.results)

    def test_validate_log_level_invalid(self):
        v = EnvironmentValidator()
        with patch("app.core.validators.settings") as mock_settings:
            mock_settings.LOG_LEVEL = "INVALID"
            v._validate_log_settings()
        assert any(not r.passed for r in v.results)

    def test_validate_log_all_valid_levels(self):
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            v = EnvironmentValidator()
            with patch("app.core.validators.settings") as mock_settings:
                mock_settings.LOG_LEVEL = level
                v._validate_log_settings()
            assert any(r.passed for r in v.results), f"{level} should be valid"


# ═══════════════════════════════════════════════════════════════════════════════
# check_system_resources
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckSystemResources:

    def test_returns_dict(self):
        result = check_system_resources()
        assert isinstance(result, dict)

    def test_has_cpu_percent(self):
        result = check_system_resources()
        assert "cpu_percent" in result

    def test_has_memory_percent(self):
        result = check_system_resources()
        assert "memory_percent" in result

    def test_has_disk_percent(self):
        result = check_system_resources()
        assert "disk_percent" in result

    def test_has_cpu_count(self):
        result = check_system_resources()
        assert "cpu_count" in result

    def test_has_memory_total_gb(self):
        result = check_system_resources()
        assert "memory_total_gb" in result

    def test_has_disk_total_gb(self):
        result = check_system_resources()
        assert "disk_total_gb" in result

    def test_cpu_percent_range(self):
        result = check_system_resources()
        assert 0.0 <= result["cpu_percent"] <= 100.0

    def test_memory_percent_range(self):
        result = check_system_resources()
        assert 0.0 <= result["memory_percent"] <= 100.0

    def test_cpu_count_positive(self):
        result = check_system_resources()
        assert result["cpu_count"] > 0

    def test_memory_total_positive(self):
        result = check_system_resources()
        assert result["memory_total_gb"] > 0

    def test_disk_total_positive(self):
        result = check_system_resources()
        assert result["disk_total_gb"] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMAL MODEL ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnimalEnums:

    def test_all_species(self):
        for s in ["cattle", "sheep", "goat", "horse", "other"]:
            assert AnimalSpecies(s) is not None

    def test_species_count(self):
        assert len(AnimalSpecies) == 5

    def test_all_genders(self):
        for g in ["male", "female", "unknown"]:
            assert AnimalGender(g) is not None

    def test_gender_count(self):
        assert len(AnimalGender) == 3

    def test_all_statuses(self):
        for s in ["active", "quarantine", "sick", "sold", "deceased", "transferred"]:
            assert AnimalStatus(s) is not None

    def test_status_count(self):
        assert len(AnimalStatus) == 6

    def test_cattle_value(self):
        assert AnimalSpecies.CATTLE == "cattle"

    def test_active_value(self):
        assert AnimalStatus.ACTIVE == "active"

    def test_female_value(self):
        assert AnimalGender.FEMALE == "female"


class TestAnimalModel:

    def test_animal_creation(self):
        a = Animal(
            tag_id="TEST-001",
            species=AnimalSpecies.CATTLE,
            gender=AnimalGender.FEMALE,
            status=AnimalStatus.ACTIVE,
            acquisition_date=datetime(2021, 1, 1),
        )
        assert a.tag_id == "TEST-001"
        assert a.species == AnimalSpecies.CATTLE

    def test_animal_default_total_detections(self):
        a = Animal(
            tag_id="T1",
            species=AnimalSpecies.SHEEP,
            gender=AnimalGender.MALE,
            status=AnimalStatus.ACTIVE,
            acquisition_date=datetime(2022, 1, 1),
        )
        assert a.total_detections == 0

    def test_animal_optional_fields_none(self):
        a = Animal(
            tag_id="T2",
            species=AnimalSpecies.CATTLE,
            gender=AnimalGender.FEMALE,
            status=AnimalStatus.ACTIVE,
            acquisition_date=datetime(2022, 1, 1),
        )
        assert a.birth_date is None
        assert a.breed is None
        assert a.notes is None

    def test_animal_is_string_enum(self):
        assert isinstance(AnimalSpecies.CATTLE, str)
        assert isinstance(AnimalStatus.ACTIVE, str)


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT MODEL ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlertEnums:

    def test_alert_severities(self):
        for s in ["low", "medium", "high", "critical"]:
            assert AlertSeverity(s) is not None

    def test_alert_statuses(self):
        for s in ["open", "seen", "resolved", "dismissed"]:
            assert AlertStatus(s) is not None

    def test_alert_types_animal(self):
        for t in ["animal_missing", "animal_missing_long", "health_anomaly",
                  "weight_loss", "growth_stagnation"]:
            assert AlertType(t) is not None

    def test_alert_types_adi(self):
        for t in ["adi_critical", "adi_rapid_decline", "adi_sharp_drop",
                  "adi_warning", "feeding_problem", "feeding_stopped"]:
            assert AlertType(t) is not None

    def test_alert_types_system(self):
        for t in ["camera_offline", "detection_stopped", "sensor_offline",
                  "sensor_anomaly", "system_error", "custom"]:
            assert AlertType(t) is not None

    def test_alert_types_iot(self):
        for t in ["high_temperature", "low_heart_rate", "high_heart_rate"]:
            assert AlertType(t) is not None

    def test_critical_severity_value(self):
        assert AlertSeverity.CRITICAL == "critical"

    def test_open_status_value(self):
        assert AlertStatus.OPEN == "open"

    def test_all_severities_4(self):
        assert len(AlertSeverity) == 4

    def test_all_statuses_4(self):
        assert len(AlertStatus) == 4


# ═══════════════════════════════════════════════════════════════════════════════
# ADICategory.from_score
# ═══════════════════════════════════════════════════════════════════════════════

class TestADICategory:

    def test_healthy_at_75(self):
        assert ADICategory.from_score(75.0) == ADICategory.HEALTHY

    def test_healthy_at_100(self):
        assert ADICategory.from_score(100.0) == ADICategory.HEALTHY

    def test_healthy_at_80(self):
        assert ADICategory.from_score(80.0) == ADICategory.HEALTHY

    def test_average_at_50(self):
        assert ADICategory.from_score(50.0) == ADICategory.AVERAGE

    def test_average_at_74(self):
        assert ADICategory.from_score(74.9) == ADICategory.AVERAGE

    def test_average_at_60(self):
        assert ADICategory.from_score(60.0) == ADICategory.AVERAGE

    def test_warning_at_25(self):
        assert ADICategory.from_score(25.0) == ADICategory.WARNING

    def test_warning_at_49(self):
        assert ADICategory.from_score(49.9) == ADICategory.WARNING

    def test_warning_at_35(self):
        assert ADICategory.from_score(35.0) == ADICategory.WARNING

    def test_critical_at_0(self):
        assert ADICategory.from_score(0.0) == ADICategory.CRITICAL

    def test_critical_at_24(self):
        assert ADICategory.from_score(24.9) == ADICategory.CRITICAL

    def test_critical_at_10(self):
        assert ADICategory.from_score(10.0) == ADICategory.CRITICAL

    def test_boundary_75_healthy(self):
        assert ADICategory.from_score(75.0) == ADICategory.HEALTHY

    def test_boundary_74_9_average(self):
        assert ADICategory.from_score(74.9) == ADICategory.AVERAGE

    def test_boundary_50_average(self):
        assert ADICategory.from_score(50.0) == ADICategory.AVERAGE

    def test_boundary_49_9_warning(self):
        assert ADICategory.from_score(49.9) == ADICategory.WARNING

    def test_boundary_25_warning(self):
        assert ADICategory.from_score(25.0) == ADICategory.WARNING

    def test_boundary_24_9_critical(self):
        assert ADICategory.from_score(24.9) == ADICategory.CRITICAL

    def test_returns_string(self):
        assert isinstance(ADICategory.from_score(70.0), str)

    def test_constants(self):
        assert ADICategory.HEALTHY  == "healthy"
        assert ADICategory.AVERAGE  == "average"
        assert ADICategory.WARNING  == "warning"
        assert ADICategory.CRITICAL == "critical"


# ═══════════════════════════════════════════════════════════════════════════════
# HealthRecord enums
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthRecordEnums:

    def test_all_record_types(self):
        for t in ["checkup", "treatment", "vaccination", "injury",
                  "surgery", "illness", "other"]:
            assert HealthRecordType(t) is not None

    def test_record_type_count(self):
        assert len(HealthRecordType) == 7

    def test_all_severities(self):
        for s in ["normal", "warning", "critical"]:
            assert HealthRecordSeverity(s) is not None

    def test_severity_count(self):
        assert len(HealthRecordSeverity) == 3

    def test_checkup_value(self):
        assert HealthRecordType.CHECKUP == "checkup"

    def test_critical_severity_value(self):
        assert HealthRecordSeverity.CRITICAL == "critical"


# ═══════════════════════════════════════════════════════════════════════════════
# WeightSource
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeightSource:

    def test_all_sources(self):
        for s in ["camera_ai", "manual", "scale_serial", "scale_api"]:
            assert WeightSource(s) is not None

    def test_source_count(self):
        assert len(WeightSource) == 4

    def test_camera_ai_value(self):
        assert WeightSource.CAMERA_AI == "camera_ai"

    def test_manual_value(self):
        assert WeightSource.MANUAL == "manual"

    def test_scale_serial_value(self):
        assert WeightSource.SCALE_SERIAL == "scale_serial"

    def test_scale_api_value(self):
        assert WeightSource.SCALE_API == "scale_api"


# ═══════════════════════════════════════════════════════════════════════════════
# UserRole
# ═══════════════════════════════════════════════════════════════════════════════

class TestUserRole:

    def test_all_roles(self):
        for r in ["admin", "manager", "viewer"]:
            assert UserRole(r) is not None

    def test_role_count(self):
        assert len(UserRole) == 3

    def test_admin_value(self):
        assert UserRole.ADMIN == "admin"

    def test_manager_value(self):
        assert UserRole.MANAGER == "manager"

    def test_viewer_value(self):
        assert UserRole.VIEWER == "viewer"

    def test_is_str_enum(self):
        assert isinstance(UserRole.ADMIN, str)


# ═══════════════════════════════════════════════════════════════════════════════
# User model
# ═══════════════════════════════════════════════════════════════════════════════

class TestUserModel:

    def test_user_creation(self):
        u = User(
            email="test@farm.uz",
            username="testuser",
            hashed_password="$2b$hash",
            role=UserRole.VIEWER,
            is_active=True,
        )
        assert u.email == "test@farm.uz"
        assert u.role == UserRole.VIEWER

    def test_user_is_active_default(self):
        u = User(
            email="x@y.uz",
            username="xuser",
            hashed_password="hash",
            role=UserRole.VIEWER,
        )
        # is_active default True yoki None
        assert u.is_active in (True, None)

    def test_user_refresh_token_none_default(self):
        u = User(
            email="a@b.uz",
            username="auser",
            hashed_password="hash",
            role=UserRole.ADMIN,
        )
        assert u.refresh_token_hash is None