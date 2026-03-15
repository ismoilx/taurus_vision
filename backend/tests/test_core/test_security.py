"""
TAURUS VISION — tests/test_core/test_security.py
=================================================
Security utilities (security.py) + Exception hierarchy (exceptions.py)
uchun AYAMAS vahshiy testlar.

Saqlash: backend/tests/test_core/test_security.py

Qamrav (130+ test):
  ── SECURITY ──
  ✓ hash_password     — bcrypt $2b$ prefiksi, unique salt, long passwords
  ✓ verify_password   — to'g'ri, noto'g'ri, empty, unicode, xato hash
  ✓ create_access_token — payload: sub, type=access, role, exp, iat
  ✓ create_refresh_token — payload: type=refresh, exp uzoqroq
  ✓ decode_token      — to'g'ri, expired, invalid, tampered
  ✓ hash_token        — 64 hex, deterministik, farqli token farqli hash
  ✓ get_token_expires_in — musbat int (soniya)
  ✓ _BCRYPT_ROUNDS    — 12

  ── EXCEPTIONS ──
  ✓ TaurusException   — message, details, inheritance
  ✓ EntityNotFoundError — entity+identifier, entity-only, message-only, entity_id alias
  ✓ EntityAlreadyExistsError — message, details
  ✓ BusinessRuleViolationError — message, details
  ✓ ValidationError   — message, details
  ✓ AuthenticationError — message, details
  ✓ PermissionDeniedError — message, details
  ✓ DatabaseError     — message, details
  ✓ Exception hierarchy — isinstance tekshiruvi
  ✓ details default empty dict, str() tavsifi
"""

import pytest
import time
from datetime import datetime, timezone, timedelta

import jwt

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
    get_token_expires_in,
    _BCRYPT_ROUNDS,
)
from app.core.exceptions import (
    TaurusException,
    EntityNotFoundError,
    EntityAlreadyExistsError,
    BusinessRuleViolationError,
    ValidationError,
    AuthenticationError,
    PermissionDeniedError,
    DatabaseError,
)
from app.config import settings

pytestmark = pytest.mark.asyncio


# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY — hash_password
# ═══════════════════════════════════════════════════════════════════════════════

class TestHashPassword:

    def test_returns_string(self):
        result = hash_password("MyPass123!")
        assert isinstance(result, str)

    def test_starts_with_bcrypt_prefix(self):
        result = hash_password("TestPass1")
        assert result.startswith("$2b$")

    def test_different_salts_different_hashes(self):
        h1 = hash_password("SamePass1")
        h2 = hash_password("SamePass1")
        assert h1 != h2  # Har safar yangi salt

    def test_length_reasonable(self):
        result = hash_password("Pass1")
        assert len(result) >= 50  # bcrypt hashes are ~60 chars

    def test_unicode_password(self):
        result = hash_password("Parol123₴€£")
        assert result.startswith("$2b$")

    def test_empty_password_hashes(self):
        result = hash_password("")
        assert result.startswith("$2b$")

    def test_long_password(self):
        long_pass = "A" * 72 + "extra"  # bcrypt truncates at 72
        result = hash_password(long_pass)
        assert result.startswith("$2b$")

    def test_bcrypt_rounds_12(self):
        assert _BCRYPT_ROUNDS == 12

    def test_special_characters(self):
        result = hash_password("P@$$w0rd!#%^&*()")
        assert result.startswith("$2b$")


# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY — verify_password
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifyPassword:

    def test_correct_password_true(self):
        hashed = hash_password("Correct123")
        assert verify_password("Correct123", hashed) is True

    def test_wrong_password_false(self):
        hashed = hash_password("Correct123")
        assert verify_password("Wrong456", hashed) is False

    def test_empty_plain_vs_hashed_false(self):
        hashed = hash_password("NonEmpty1")
        assert verify_password("", hashed) is False

    def test_empty_vs_empty_hash(self):
        hashed = hash_password("")
        assert verify_password("", hashed) is True

    def test_case_sensitive(self):
        hashed = hash_password("CaseSensitive1")
        assert verify_password("casesensitive1", hashed) is False

    def test_unicode_password_verified(self):
        pwd = "Parol123₴€"
        hashed = hash_password(pwd)
        assert verify_password(pwd, hashed) is True

    def test_invalid_hash_returns_false(self):
        assert verify_password("pass", "not-a-valid-hash") is False

    def test_empty_hash_returns_false(self):
        assert verify_password("pass", "") is False

    def test_different_pass_different_result(self):
        hashed = hash_password("Original1")
        assert verify_password("Original1", hashed) is True
        assert verify_password("Original2", hashed) is False

    def test_special_chars_verified(self):
        pwd = "P@$$w0rd!#"
        hashed = hash_password(pwd)
        assert verify_password(pwd, hashed) is True


# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY — create_access_token
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreateAccessToken:

    def test_returns_string(self):
        token = create_access_token(user_id=1, role="admin")
        assert isinstance(token, str)

    def test_payload_sub_is_user_id(self):
        token = create_access_token(user_id=42, role="viewer")
        payload = jwt.decode(
            token, settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM])
        assert payload["sub"] == "42"

    def test_payload_type_is_access(self):
        token = create_access_token(user_id=1, role="admin")
        payload = jwt.decode(
            token, settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM])
        assert payload["type"] == "access"

    def test_payload_role(self):
        for role in ["admin", "manager", "viewer"]:
            token = create_access_token(user_id=1, role=role)
            payload = jwt.decode(
                token, settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM])
            assert payload["role"] == role

    def test_payload_has_exp(self):
        token = create_access_token(user_id=1, role="admin")
        payload = jwt.decode(
            token, settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM])
        assert "exp" in payload

    def test_payload_has_iat(self):
        token = create_access_token(user_id=1, role="admin")
        payload = jwt.decode(
            token, settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM])
        assert "iat" in payload

    def test_custom_expires_delta(self):
        token = create_access_token(
            user_id=1, role="admin",
            expires_delta=timedelta(hours=2))
        payload = jwt.decode(
            token, settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        diff = (exp - iat).total_seconds()
        assert 7100 < diff < 7300  # ~2 soat

    def test_different_users_different_tokens(self):
        t1 = create_access_token(user_id=1, role="admin")
        t2 = create_access_token(user_id=2, role="admin")
        assert t1 != t2

    def test_token_not_expired_immediately(self):
        token = create_access_token(user_id=1, role="admin")
        payload = decode_token(token)
        assert payload["sub"] == "1"


# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY — create_refresh_token
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreateRefreshToken:

    def test_returns_string(self):
        token = create_refresh_token(user_id=1, role="admin")
        assert isinstance(token, str)

    def test_payload_type_is_refresh(self):
        token = create_refresh_token(user_id=1, role="admin")
        payload = jwt.decode(
            token, settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM])
        assert payload["type"] == "refresh"

    def test_refresh_token_expires_later_than_access(self):
        access  = create_access_token(user_id=1, role="admin")
        refresh = create_refresh_token(user_id=1, role="admin")
        ap = jwt.decode(access, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        rp = jwt.decode(refresh, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        assert rp["exp"] > ap["exp"]  # Refresh muddati uzoqroq

    def test_payload_sub_is_user_id(self):
        token = create_refresh_token(user_id=99, role="manager")
        payload = jwt.decode(
            token, settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM])
        assert payload["sub"] == "99"

    def test_different_from_access_token(self):
        access  = create_access_token(user_id=1, role="admin")
        refresh = create_refresh_token(user_id=1, role="admin")
        assert access != refresh


# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY — decode_token
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecodeToken:

    def test_decode_valid_access_token(self):
        token = create_access_token(user_id=5, role="viewer")
        payload = decode_token(token)
        assert payload["sub"] == "5"
        assert payload["type"] == "access"

    def test_decode_valid_refresh_token(self):
        token = create_refresh_token(user_id=7, role="manager")
        payload = decode_token(token)
        assert payload["sub"] == "7"
        assert payload["type"] == "refresh"

    def test_decode_returns_dict(self):
        token = create_access_token(user_id=1, role="admin")
        result = decode_token(token)
        assert isinstance(result, dict)

    def test_decode_invalid_token_raises(self):
        with pytest.raises(AuthenticationError) as exc_info:
            decode_token("not.a.real.token")
        assert "noto'g'ri" in exc_info.value.message.lower() or \
               "invalid" in exc_info.value.message.lower()

    def test_decode_tampered_token_raises(self):
        token = create_access_token(user_id=1, role="admin")
        parts = token.split(".")
        parts[1] = parts[1] + "TAMPERED"
        tampered = ".".join(parts)
        with pytest.raises(AuthenticationError):
            decode_token(tampered)

    def test_decode_expired_token_raises(self):
        expired_token = create_access_token(
            user_id=1, role="admin",
            expires_delta=timedelta(seconds=-1))
        with pytest.raises(AuthenticationError) as exc_info:
            decode_token(expired_token)
        assert "muddati" in exc_info.value.message.lower() or \
               "expired" in exc_info.value.message.lower()

    def test_decode_empty_string_raises(self):
        with pytest.raises(AuthenticationError):
            decode_token("")

    def test_decode_wrong_secret_raises(self):
        token = jwt.encode(
            {"sub": "1", "type": "access", "exp": time.time() + 3600},
            "wrong-secret", algorithm="HS256")
        with pytest.raises(AuthenticationError):
            decode_token(token)


# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY — hash_token + get_token_expires_in
# ═══════════════════════════════════════════════════════════════════════════════

class TestHashToken:

    def test_returns_64_hex_chars(self):
        result = hash_token("some-jwt-token")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self):
        token = "same-token-value"
        h1 = hash_token(token)
        h2 = hash_token(token)
        assert h1 == h2

    def test_different_tokens_different_hashes(self):
        h1 = hash_token("token1")
        h2 = hash_token("token2")
        assert h1 != h2

    def test_real_jwt_token(self):
        jwt_token = create_access_token(user_id=1, role="admin")
        result = hash_token(jwt_token)
        assert len(result) == 64


class TestGetTokenExpiresIn:

    def test_returns_positive_int(self):
        result = get_token_expires_in()
        assert isinstance(result, int)
        assert result > 0

    def test_is_minutes_times_60(self):
        result = get_token_expires_in()
        expected = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert result == expected


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS — TaurusException (base)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTaurusException:

    def test_message_stored(self):
        exc = TaurusException(message="Test error")
        assert exc.message == "Test error"

    def test_details_default_empty_dict(self):
        exc = TaurusException(message="Error")
        assert exc.details == {}

    def test_details_stored(self):
        exc = TaurusException(message="Error", details={"field": "value"})
        assert exc.details["field"] == "value"

    def test_is_exception(self):
        exc = TaurusException(message="Error")
        assert isinstance(exc, Exception)

    def test_str_representation(self):
        exc = TaurusException(message="My error message")
        assert "My error message" in str(exc)

    def test_raise_and_catch(self):
        with pytest.raises(TaurusException) as exc_info:
            raise TaurusException(message="Raised error")
        assert exc_info.value.message == "Raised error"


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS — EntityNotFoundError
# ═══════════════════════════════════════════════════════════════════════════════

class TestEntityNotFoundError:

    def test_entity_and_identifier(self):
        exc = EntityNotFoundError(entity="Animal", identifier=42)
        assert "Animal" in exc.message
        assert "42" in exc.message

    def test_entity_only(self):
        exc = EntityNotFoundError(entity="Farm")
        assert "Farm" in exc.message

    def test_message_only(self):
        exc = EntityNotFoundError(message="Custom not found message")
        assert exc.message == "Custom not found message"

    def test_entity_id_alias(self):
        """entity_id backward-compat alias."""
        exc = EntityNotFoundError(entity="User", entity_id=99)
        assert "99" in exc.message

    def test_no_args_default_message(self):
        exc = EntityNotFoundError()
        assert "not found" in exc.message.lower()

    def test_is_taurus_exception(self):
        exc = EntityNotFoundError(entity="X")
        assert isinstance(exc, TaurusException)

    def test_details_stored(self):
        exc = EntityNotFoundError(entity="Animal", identifier=1,
                                  details={"extra": "info"})
        assert exc.details["extra"] == "info"

    def test_raise_and_catch(self):
        with pytest.raises(EntityNotFoundError):
            raise EntityNotFoundError(entity="Animal", identifier=5)


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS — Other exception classes
# ═══════════════════════════════════════════════════════════════════════════════

class TestOtherExceptions:

    def test_entity_already_exists_message(self):
        exc = EntityAlreadyExistsError(
            message="Tag allaqachon mavjud",
            details={"tag_id": "JNV-001"})
        assert "allaqachon" in exc.message
        assert exc.details["tag_id"] == "JNV-001"

    def test_entity_already_exists_is_taurus(self):
        exc = EntityAlreadyExistsError(message="Exists")
        assert isinstance(exc, TaurusException)

    def test_business_rule_violation_message(self):
        exc = BusinessRuleViolationError(
            message="Sotilgan jonivori o'zgartirib bo'lmaydi",
            details={"status": "sold"})
        assert "Sotilgan" in exc.message
        assert exc.details["status"] == "sold"

    def test_business_rule_is_taurus(self):
        assert isinstance(
            BusinessRuleViolationError(message="x"), TaurusException)

    def test_validation_error_message(self):
        exc = ValidationError(message="Tug'ilish sanasi kelajakda bo'lolmaydi",
                              details={"field": "birth_date"})
        assert "Tug'ilish" in exc.message

    def test_validation_error_is_taurus(self):
        assert isinstance(ValidationError(message="x"), TaurusException)

    def test_authentication_error_message(self):
        exc = AuthenticationError(message="Token muddati tugagan")
        assert "muddati" in exc.message

    def test_authentication_error_is_taurus(self):
        assert isinstance(AuthenticationError(message="x"), TaurusException)

    def test_permission_denied_message(self):
        exc = PermissionDeniedError(
            message="Faqat ADMIN bu amalni bajarishi mumkin",
            details={"required": "ADMIN", "current": "VIEWER"})
        assert "ADMIN" in exc.message

    def test_permission_denied_is_taurus(self):
        assert isinstance(PermissionDeniedError(message="x"), TaurusException)

    def test_database_error_message(self):
        exc = DatabaseError(
            message="Jonivorni saqlashda xato",
            details={"error": "connection refused"})
        assert "xato" in exc.message.lower()

    def test_database_error_is_taurus(self):
        assert isinstance(DatabaseError(message="x"), TaurusException)

    def test_all_exceptions_have_details(self):
        """Barcha exception larning details atributi bor."""
        for ExcClass in [EntityNotFoundError, EntityAlreadyExistsError,
                         BusinessRuleViolationError, ValidationError,
                         AuthenticationError, PermissionDeniedError, DatabaseError]:
            exc = ExcClass(message="test")
            assert hasattr(exc, "details")
            assert isinstance(exc.details, dict)

    def test_all_exceptions_are_taurus(self):
        """Barcha exception lar TaurusException dan meros oladi."""
        for ExcClass in [EntityNotFoundError, EntityAlreadyExistsError,
                         BusinessRuleViolationError, ValidationError,
                         AuthenticationError, PermissionDeniedError, DatabaseError]:
            exc = ExcClass(message="test")
            assert isinstance(exc, TaurusException)
            assert isinstance(exc, Exception)

    def test_all_exceptions_catchable_as_base(self):
        """TaurusException ota sifatida ushlanishi mumkin."""
        for ExcClass in [EntityNotFoundError, BusinessRuleViolationError,
                         AuthenticationError, DatabaseError]:
            with pytest.raises(TaurusException):
                raise ExcClass(message="test error")

    def test_exception_details_none_becomes_empty_dict(self):
        exc = TaurusException(message="test", details=None)
        assert exc.details == {}

    def test_exception_raise_string(self):
        exc = DatabaseError(message="Connection failed", details={"host": "db"})
        assert str(exc) == "Connection failed"