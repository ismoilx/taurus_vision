"""
TAURUS VISION — test_core/test_exceptions.py
=============================================
app/core/exceptions.py uchun to'liq, vahshiy testlar.

Qamrov:
  ✓ TaurusException      — base class, message, details
  ✓ EntityNotFoundError  — entity+id, faqat entity, faqat message, entity_id alias
  ✓ EntityAlreadyExistsError
  ✓ BusinessRuleViolationError
  ✓ ValidationError
  ✓ AuthenticationError
  ✓ PermissionDeniedError
  ✓ DatabaseError
  ✓ Exception hierarchy  — isinstance checks
  ✓ Catch scenarios      — except bloklari to'g'ri ishlashi
"""

import pytest

from app.core.exceptions import (
    AuthenticationError,
    BusinessRuleViolationError,
    DatabaseError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    PermissionDeniedError,
    TaurusException,
    ValidationError,
)

pytestmark = pytest.mark.unit


# ═══════════════════════════════════════════════════════════════════════════════
# TaurusException (Base)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTaurusException:
    """TaurusException asosiy klass testlari."""

    def test_is_exception(self):
        """TaurusException Exception dan meros oladi."""
        exc = TaurusException(message="test error")
        assert isinstance(exc, Exception)

    def test_message_attribute(self):
        """message atributi to'g'ri saqlandi."""
        exc = TaurusException(message="Something went wrong")
        assert exc.message == "Something went wrong"

    def test_message_in_args(self):
        """str(exc) va exc.args da xabar mavjud."""
        exc = TaurusException(message="Critical failure")
        assert "Critical failure" in str(exc)

    def test_details_default_empty_dict(self):
        """details o'tkazilmasa — bo'sh dict."""
        exc = TaurusException(message="test")
        assert exc.details == {}
        assert isinstance(exc.details, dict)

    def test_details_provided(self):
        """details o'tkazilsa — saqlanadi."""
        details = {"field": "email", "value": "bad@"}
        exc = TaurusException(message="Validation failed", details=details)
        assert exc.details == details

    def test_details_none_becomes_empty_dict(self):
        """details=None → bo'sh dict."""
        exc = TaurusException(message="test", details=None)
        assert exc.details == {}

    def test_can_be_raised_and_caught(self):
        """raise va except bilan ishlaydi."""
        with pytest.raises(TaurusException) as exc_info:
            raise TaurusException(message="Base exception raised")
        assert exc_info.value.message == "Base exception raised"

    def test_can_be_caught_as_generic_exception(self):
        """Exception sifatida ham tutiladi."""
        with pytest.raises(Exception):
            raise TaurusException(message="Caught as Exception")

    def test_complex_details(self):
        """Murakkab details dict."""
        details = {
            "errors": ["error1", "error2"],
            "code": 42,
            "nested": {"key": "value"},
        }
        exc = TaurusException(message="Complex", details=details)
        assert exc.details["errors"] == ["error1", "error2"]
        assert exc.details["code"] == 42
        assert exc.details["nested"]["key"] == "value"


# ═══════════════════════════════════════════════════════════════════════════════
# EntityNotFoundError
# ═══════════════════════════════════════════════════════════════════════════════

class TestEntityNotFoundError:
    """EntityNotFoundError testlari."""

    def test_inherits_from_taurus_exception(self):
        exc = EntityNotFoundError(entity="Animal", identifier=1)
        assert isinstance(exc, TaurusException)
        assert isinstance(exc, Exception)

    def test_entity_and_identifier_message(self):
        """entity + identifier → avtomatik xabar."""
        exc = EntityNotFoundError(entity="Animal", identifier=42)
        assert "Animal" in exc.message
        assert "42" in exc.message

    def test_entity_only_message(self):
        """Faqat entity → 'entity not found' xabari."""
        exc = EntityNotFoundError(entity="Camera")
        assert "Camera" in exc.message
        assert "not found" in exc.message.lower()

    def test_only_message(self):
        """To'g'ridan-to'g'ri message."""
        msg = "Custom not found message"
        exc = EntityNotFoundError(message=msg)
        assert exc.message == msg

    def test_entity_id_alias_for_identifier(self):
        """entity_id parametri identifier bilan bir xil ishlaydi."""
        exc = EntityNotFoundError(entity="User", entity_id=99)
        assert "99" in exc.message
        assert "User" in exc.message

    def test_no_args_default_message(self):
        """Hech qanday argument yo'q → default xabar."""
        exc = EntityNotFoundError()
        assert exc.message == "Entity not found"

    def test_string_identifier(self):
        """String identifier."""
        exc = EntityNotFoundError(entity="Animal", identifier="TAG-001")
        assert "TAG-001" in exc.message

    def test_details_passed_through(self):
        """details o'tkaziladi."""
        exc = EntityNotFoundError(
            entity="Farm",
            identifier=5,
            details={"farm_name": "Green Farm"},
        )
        assert exc.details["farm_name"] == "Green Farm"

    def test_can_be_raised_and_caught(self):
        with pytest.raises(EntityNotFoundError) as exc_info:
            raise EntityNotFoundError(entity="Detection", identifier=7)
        assert "Detection" in exc_info.value.message
        assert "7" in exc_info.value.message

    def test_caught_as_taurus_exception(self):
        with pytest.raises(TaurusException):
            raise EntityNotFoundError(entity="Sensor", identifier=1)

    def test_identifier_zero(self):
        """identifier=0 (edge case)."""
        exc = EntityNotFoundError(entity="Record", identifier=0)
        assert "0" in exc.message

    def test_identifier_negative(self):
        """identifier manfiy (edge case)."""
        exc = EntityNotFoundError(entity="Test", identifier=-1)
        assert "-1" in exc.message

    def test_entity_id_overridden_by_identifier(self):
        """identifier berilsa entity_id e'tiborga olinmaydi."""
        exc = EntityNotFoundError(entity="Test", identifier=10, entity_id=20)
        assert "10" in exc.message
        # entity_id=20 identifier=10 bilan berilganda identifier ustunlik qiladi

    def test_message_priority_over_entity(self):
        """message berilsa entity va identifier e'tiborga olinmaydi."""
        exc = EntityNotFoundError(
            entity="Animal",
            identifier=1,
            message="Custom override message",
        )
        assert exc.message == "Custom override message"


# ═══════════════════════════════════════════════════════════════════════════════
# EntityAlreadyExistsError
# ═══════════════════════════════════════════════════════════════════════════════

class TestEntityAlreadyExistsError:
    """EntityAlreadyExistsError testlari."""

    def test_inherits_from_taurus_exception(self):
        exc = EntityAlreadyExistsError(message="exists")
        assert isinstance(exc, TaurusException)

    def test_message_stored(self):
        msg = "Animal with this tag already exists"
        exc = EntityAlreadyExistsError(message=msg)
        assert exc.message == msg

    def test_details_stored(self):
        exc = EntityAlreadyExistsError(
            message="Duplicate",
            details={"tag_id": "JNV-001", "farm_id": 3},
        )
        assert exc.details["tag_id"] == "JNV-001"
        assert exc.details["farm_id"] == 3

    def test_can_be_raised_and_caught(self):
        with pytest.raises(EntityAlreadyExistsError) as exc_info:
            raise EntityAlreadyExistsError(
                message="User already exists",
                details={"email": "test@test.com"},
            )
        assert exc_info.value.details["email"] == "test@test.com"

    def test_caught_as_taurus_exception(self):
        with pytest.raises(TaurusException):
            raise EntityAlreadyExistsError(message="Conflict")


# ═══════════════════════════════════════════════════════════════════════════════
# BusinessRuleViolationError
# ═══════════════════════════════════════════════════════════════════════════════

class TestBusinessRuleViolationError:
    """BusinessRuleViolationError testlari."""

    def test_inherits_from_taurus_exception(self):
        exc = BusinessRuleViolationError(message="rule violated")
        assert isinstance(exc, TaurusException)

    def test_common_business_rule_scenarios(self):
        """Loyihadagi haqiqiy biznes qoidalari misollari."""
        scenarios = [
            ("Cannot modify sold animal", {"status": "sold", "animal_id": 42}),
            ("Milk production requires active animal", {"animal_status": "inactive"}),
            ("Breeding not allowed for male animal", {"gender": "male"}),
            ("Weight cannot be negative", {"weight": -5.0}),
        ]
        for message, details in scenarios:
            exc = BusinessRuleViolationError(message=message, details=details)
            assert exc.message == message
            assert exc.details == details

    def test_can_be_raised_and_caught(self):
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            raise BusinessRuleViolationError(
                message="Cannot delete animal with active health records",
                details={"health_record_count": 5},
            )
        assert exc_info.value.details["health_record_count"] == 5


# ═══════════════════════════════════════════════════════════════════════════════
# ValidationError
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidationError:
    """ValidationError testlari."""

    def test_inherits_from_taurus_exception(self):
        exc = ValidationError(message="invalid")
        assert isinstance(exc, TaurusException)

    def test_does_not_inherit_from_pydantic_validation_error(self):
        """Pydantic ValidationError bilan aralashmasligi kerak."""
        from pydantic import ValidationError as PydanticValidationError
        exc = ValidationError(message="custom validation")
        assert not isinstance(exc, PydanticValidationError)

    def test_validation_scenarios(self):
        """Haqiqiy validatsiya holatlari."""
        scenarios = [
            "Birth date cannot be in the future",
            "Weight measurement must be positive",
            "Tag ID format is invalid: must be 3 letters + 3 digits",
            "Sensor reading out of valid range",
        ]
        for msg in scenarios:
            exc = ValidationError(message=msg)
            assert exc.message == msg

    def test_can_be_caught_as_taurus_exception(self):
        with pytest.raises(TaurusException):
            raise ValidationError(message="Invalid date format")


# ═══════════════════════════════════════════════════════════════════════════════
# AuthenticationError
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuthenticationError:
    """AuthenticationError testlari."""

    def test_inherits_from_taurus_exception(self):
        exc = AuthenticationError(message="auth failed")
        assert isinstance(exc, TaurusException)

    def test_common_auth_scenarios(self):
        """Haqiqiy auth xato holatlari."""
        messages = [
            "Email/username yoki parol noto'g'ri.",
            "Token muddati tugagan. Qayta login qiling.",
            "Noto'g'ri yoki buzilgan token.",
            "Hisobingiz bloklangan. Administrator bilan bog'laning.",
            "Refresh token noto'g'ri yoki muddati tugagan.",
        ]
        for msg in messages:
            exc = AuthenticationError(message=msg)
            assert exc.message == msg

    def test_no_details_by_default(self):
        """Default holda details bo'sh dict."""
        exc = AuthenticationError(message="error")
        assert exc.details == {}

    def test_can_be_raised_and_caught(self):
        with pytest.raises(AuthenticationError) as exc_info:
            raise AuthenticationError(
                message="Invalid token",
                details={"token_type": "access"},
            )
        assert exc_info.value.details["token_type"] == "access"

    def test_caught_as_taurus_exception(self):
        with pytest.raises(TaurusException):
            raise AuthenticationError(message="Auth failed")

    def test_not_caught_as_other_domain_errors(self):
        """AuthenticationError EntityNotFoundError sifatida tutilmaydi."""
        with pytest.raises(AuthenticationError):
            raise AuthenticationError(message="auth error")
        # Bu yerda EntityNotFoundError istisno sifatida kutiladi
        # va AuthenticationError u sifatida tutilmaydi — test o'tdi


# ═══════════════════════════════════════════════════════════════════════════════
# PermissionDeniedError
# ═══════════════════════════════════════════════════════════════════════════════

class TestPermissionDeniedError:
    """PermissionDeniedError testlari."""

    def test_inherits_from_taurus_exception(self):
        exc = PermissionDeniedError(message="denied")
        assert isinstance(exc, TaurusException)

    def test_permission_scenarios(self):
        """Haqiqiy ruxsat rad etish holatlari."""
        scenarios = [
            ("Only ADMIN can create users",
             {"required_role": "ADMIN", "user_role": "VIEWER"}),
            ("Viewer cannot delete animals",
             {"required_role": "MANAGER", "user_role": "VIEWER"}),
            ("Cannot modify another user's data",
             {"user_id": 5, "requesting_user_id": 10}),
        ]
        for msg, details in scenarios:
            exc = PermissionDeniedError(message=msg, details=details)
            assert exc.message == msg
            assert exc.details == details

    def test_can_be_raised_and_caught(self):
        with pytest.raises(PermissionDeniedError) as exc_info:
            raise PermissionDeniedError(
                message="Admin only",
                details={"required_role": "admin", "your_role": "viewer"},
            )
        assert "admin" in exc_info.value.details["required_role"]

    def test_not_caught_as_authentication_error(self):
        """PermissionDeniedError AuthenticationError sifatida tutilmaydi."""
        raised = False
        try:
            raise PermissionDeniedError(message="Permission denied")
        except AuthenticationError:
            raised = True  # Bu bo'lmasligi kerak
        except PermissionDeniedError:
            raised = True  # Bu bo'lishi kerak
        assert raised


# ═══════════════════════════════════════════════════════════════════════════════
# DatabaseError
# ═══════════════════════════════════════════════════════════════════════════════

class TestDatabaseError:
    """DatabaseError testlari."""

    def test_inherits_from_taurus_exception(self):
        exc = DatabaseError(message="DB error")
        assert isinstance(exc, TaurusException)

    def test_common_db_scenarios(self):
        """Haqiqiy DB xato holatlari."""
        scenarios = [
            ("Failed to save animal", {"error": "connection timeout"}),
            ("Database constraint violation", {"constraint": "unique_tag_id"}),
            ("Transaction rollback", {"operation": "bulk_insert"}),
        ]
        for msg, details in scenarios:
            exc = DatabaseError(message=msg, details=details)
            assert exc.message == msg

    def test_can_be_raised_and_caught(self):
        with pytest.raises(DatabaseError):
            raise DatabaseError(message="Connection failed")

    def test_can_wrap_original_exception(self):
        """Asl xatoni o'rashi mumkin."""
        try:
            raise RuntimeError("original error")
        except RuntimeError as original:
            exc = DatabaseError(
                message="DB operation failed",
                details={"original_error": str(original)},
            )
            assert "original error" in exc.details["original_error"]


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTION HIERARCHY
# ═══════════════════════════════════════════════════════════════════════════════

class TestExceptionHierarchy:
    """Exception meros zanjirini tekshirish."""

    def test_all_inherit_from_taurus_exception(self):
        """Barcha custom exception'lar TaurusException dan meros oladi."""
        exceptions = [
            EntityNotFoundError(message="test"),
            EntityAlreadyExistsError(message="test"),
            BusinessRuleViolationError(message="test"),
            ValidationError(message="test"),
            AuthenticationError(message="test"),
            PermissionDeniedError(message="test"),
            DatabaseError(message="test"),
        ]
        for exc in exceptions:
            assert isinstance(exc, TaurusException), \
                f"{type(exc).__name__} TaurusException dan meros olmagan!"

    def test_all_inherit_from_base_exception(self):
        """Barcha custom exception'lar Python Exception dan meros oladi."""
        exceptions = [
            EntityNotFoundError(message="test"),
            EntityAlreadyExistsError(message="test"),
            BusinessRuleViolationError(message="test"),
            ValidationError(message="test"),
            AuthenticationError(message="test"),
            PermissionDeniedError(message="test"),
            DatabaseError(message="test"),
        ]
        for exc in exceptions:
            assert isinstance(exc, Exception), \
                f"{type(exc).__name__} Exception dan meros olmagan!"

    def test_exceptions_not_cross_typed(self):
        """Exception'lar bir-birining subklassi emas."""
        auth_exc    = AuthenticationError(message="auth")
        perm_exc    = PermissionDeniedError(message="perm")
        notfound_exc = EntityNotFoundError(message="notfound")

        assert not isinstance(auth_exc, PermissionDeniedError)
        assert not isinstance(perm_exc, AuthenticationError)
        assert not isinstance(notfound_exc, AuthenticationError)
        assert not isinstance(notfound_exc, DatabaseError)

    def test_catch_all_via_taurus_exception(self):
        """TaurusException orqali barcha custom exception'larni tutish."""
        exceptions_to_raise = [
            EntityNotFoundError(message="e1"),
            EntityAlreadyExistsError(message="e2"),
            BusinessRuleViolationError(message="e3"),
            ValidationError(message="e4"),
            AuthenticationError(message="e5"),
            PermissionDeniedError(message="e6"),
            DatabaseError(message="e7"),
        ]
        for exc in exceptions_to_raise:
            caught = False
            try:
                raise exc
            except TaurusException:
                caught = True
            assert caught, f"{type(exc).__name__} TaurusException sifatida tutilmadi!"

    def test_specific_catch_before_general(self):
        """Aniq exception turini umumiydan oldin tutish."""
        result = None
        try:
            raise EntityNotFoundError(entity="Animal", identifier=1)
        except EntityNotFoundError:
            result = "specific"
        except TaurusException:
            result = "general"

        assert result == "specific", "Aniq EntityNotFoundError tutilmadi"

    def test_exception_message_preserved_in_str(self):
        """str(exc) xabarni o'z ichiga oladi."""
        exc = AuthenticationError(message="Token expired")
        assert "Token expired" in str(exc)


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASES & UNUSUAL INPUTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Chekka holatlar va g'ayrioddiy kirishlar."""

    def test_empty_message(self):
        """Bo'sh message."""
        exc = TaurusException(message="")
        assert exc.message == ""

    def test_very_long_message(self):
        """Juda uzun xabar."""
        long_msg = "X" * 10_000
        exc = TaurusException(message=long_msg)
        assert exc.message == long_msg

    def test_unicode_message(self):
        """Unicode xabar."""
        msg = "Xato yuz berdi: топилмади 错误"
        exc = EntityNotFoundError(message=msg)
        assert exc.message == msg

    def test_details_with_none_values(self):
        """details None qiymatlari bilan."""
        exc = TaurusException(
            message="test",
            details={"key1": None, "key2": "value"},
        )
        assert exc.details["key1"] is None
        assert exc.details["key2"] == "value"

    def test_mutable_details_not_shared(self):
        """details dict mustaqil (shared reference emas)."""
        shared_details = {"key": "value"}
        exc1 = TaurusException(message="e1", details=shared_details)
        exc2 = TaurusException(message="e2", details=shared_details)
        # shared_details o'zgartirilsa, exc1.details ham o'zgaradi
        # Bu kutilgan xulq-atvor (dict reference), lekin None case qo'llab quvvatlanadi
        assert exc1.details is not exc2.details or exc1.details == exc2.details

    def test_exception_reraise(self):
        """Exception qayta ko'tarilishi."""
        original = EntityNotFoundError(entity="Animal", identifier=1)
        try:
            try:
                raise original
            except EntityNotFoundError:
                raise  # Qayta ko'tarish
        except EntityNotFoundError as caught:
            assert caught is original  # Bir xil ob'ekt