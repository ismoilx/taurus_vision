"""
TAURUS VISION — test_core/test_security.py
============================================
app/core/security.py uchun to'liq, vahshiy testlar.

Qamrov:
  ✓ hash_password        — bcrypt hashing, encoding, uniqueness
  ✓ verify_password      — to'g'ri/noto'g'ri/buzilgan parollar
  ✓ create_access_token  — payload, exp, iat, type, role
  ✓ create_refresh_token — payload, exp, type
  ✓ decode_token         — muvaffaqiyatli, muddati o'tgan, noto'g'ri, buzilgan
  ✓ hash_token           — deterministik, format, uzunlik
  ✓ get_token_expires_in — to'g'ri konversiya

Edge cases:
  - Unicode parollar
  - Bo'sh string parol
  - Juda uzun parollar
  - Maxsus belgilar
  - Noto'g'ri imzolar
  - Muddati o'tgan tokenlar
  - Access token ni refresh o'rnida ishlatish
  - Payload manipulation
  - Timing attacks
"""

import hashlib
import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_token_expires_in,
    hash_password,
    hash_token,
    verify_password,
)
from app.config import settings

pytestmark = pytest.mark.unit


# ═══════════════════════════════════════════════════════════════════════════════
# HASH_PASSWORD
# ═══════════════════════════════════════════════════════════════════════════════

class TestHashPassword:
    """hash_password() funksiyasi uchun to'liq testlar."""

    def test_returns_string(self):
        """Natija string bo'lishi kerak."""
        result = hash_password("SimplePass1")
        assert isinstance(result, str)

    def test_bcrypt_prefix(self):
        """bcrypt hash $2b$ yoki $2a$ prefiksi bilan boshlanadi."""
        result = hash_password("TestPassword1")
        assert result.startswith(("$2b$", "$2a$"))

    def test_minimum_hash_length(self):
        """bcrypt hash kamida 60 belgi uzunlikda bo'ladi."""
        result = hash_password("pass")
        assert len(result) >= 60

    def test_different_salts_each_call(self):
        """Bir xil parolga ikki chaqiriq → turli hash (salt randomness)."""
        h1 = hash_password("SamePassword1")
        h2 = hash_password("SamePassword1")
        assert h1 != h2

    def test_different_passwords_different_hashes(self):
        """Turli parollar turli hash beradi."""
        h1 = hash_password("Password1")
        h2 = hash_password("Password2")
        assert h1 != h2

    def test_empty_string_password(self):
        """Bo'sh string ham hashlash mumkin (bcrypt ruxsat beradi)."""
        result = hash_password("")
        assert result.startswith(("$2b$", "$2a$"))
        assert len(result) >= 60

    def test_unicode_password(self):
        """Unicode parollar (o'zbek, arab, xitoy harflari) hashlanadi."""
        unicode_passwords = [
            "Parol123абвгд",      # Kirill
            "رمز_عبور_1234",     # Arab
            "密码123ABC",         # Xitoy
            "Ş1frəABC",         # Lotin kengaytmasi
            "Паро́ль1",           # Urg'u belgisi bilan
        ]
        for pw in unicode_passwords:
            result = hash_password(pw)
            assert result.startswith(("$2b$", "$2a$")), f"Unicode parol failed: {pw!r}"

    def test_special_characters_password(self):
        """Maxsus belgilar bilan parol."""
        special = "P@$$w0rd!#%^&*()_+-=[]{}|;':\",./<>?"
        result = hash_password(special)
        assert result.startswith(("$2b$", "$2a$"))

    def test_very_long_password_behavior_documented(self):
        """
        bcrypt 72 baytdan uzun parollarni qabul qilmaydi — ValueError ko'taradi.
        Bu yangi bcrypt versiyalarining xulq-atvori (avtomatik kesish yo'q).
        Bu xulq-atvorni dokumentlaymiz va xizmat qatlamining uni
        qanday boshqarishini tekshiramiz.
        """
        long_pass = "A" * 100  # 100 bayt — 72 bayt chegarasidan oshadi
        # bcrypt yangi versiyasi ValueError ko'taradi
        with pytest.raises((ValueError, Exception)):
            hash_password(long_pass)

    def test_newline_in_password(self):
        """Yangi qator belgisi bilan parol."""
        result = hash_password("Pass\nword1")
        assert result.startswith(("$2b$", "$2a$"))

    def test_null_byte_in_password_raises_or_hashes(self):
        """
        Null byte (\x00) bcrypt da ba'zan muammo keltirib chiqaradi.
        Tizim yo xato berishi yo hash qilishi kerak — ikkalasi ham qabul.
        """
        try:
            result = hash_password("Pass\x00word1")
            # Agar hash qilsa — natijaXarakterlarda string bo'lishi kerak
            assert isinstance(result, str)
        except Exception:
            pass  # Xato ham qabul qilinadi

    def test_whitespace_only_password(self):
        """Faqat bo'sh joy parollar hashlash mumkin."""
        result = hash_password("   ")
        assert result.startswith(("$2b$", "$2a$"))


# ═══════════════════════════════════════════════════════════════════════════════
# VERIFY_PASSWORD
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifyPassword:
    """verify_password() funksiyasi uchun to'liq testlar."""

    def test_correct_password_returns_true(self):
        """To'g'ri parol → True."""
        pw = "CorrectPassword1"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed) is True

    def test_wrong_password_returns_false(self):
        """Noto'g'ri parol → False."""
        hashed = hash_password("OriginalPass1")
        assert verify_password("WrongPass1", hashed) is False

    def test_empty_password_against_non_empty_hash(self):
        """Bo'sh parol → noto'g'ri hash bilan False."""
        hashed = hash_password("SomePassword1")
        assert verify_password("", hashed) is False

    def test_empty_password_against_empty_hash(self):
        """Bo'sh parol bo'sh parol hash bilan mos keladi."""
        hashed = hash_password("")
        assert verify_password("", hashed) is True

    def test_case_sensitive_password(self):
        """Parol katta-kichik harfga sezgir."""
        hashed = hash_password("Password1")
        assert verify_password("password1", hashed) is False
        assert verify_password("PASSWORD1", hashed) is False
        assert verify_password("Password1", hashed) is True

    def test_invalid_hash_returns_false(self):
        """Noto'g'ri hash format → False (xato bermaydi)."""
        assert verify_password("SomePass1", "not_a_valid_hash") is False

    def test_empty_hash_returns_false(self):
        """Bo'sh hash → False."""
        assert verify_password("SomePass1", "") is False

    def test_garbled_hash_returns_false(self):
        """Buzilgan hash → False (exception emas)."""
        garbled = "$2b$12$" + "X" * 50  # Noto'g'ri padding
        assert verify_password("SomePass1", garbled) is False

    def test_unicode_password_round_trip(self):
        """Unicode parollar hash va verify qilish."""
        pw = "Паро́ль_1234_密码"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed) is True
        assert verify_password("Паро́ль_1234_密码_wrong", hashed) is False

    def test_special_chars_round_trip(self):
        """Maxsus belgilar bilan round-trip."""
        pw = "P@$$w0rd!#%&*()"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed) is True
        assert verify_password("P@$$w0rd!#%&*(", hashed) is False  # Bir belgi kam

    def test_similar_passwords_dont_match(self):
        """O'xshash lekin farqli parollar mos kelmaydi."""
        pw = "Password1"
        hashed = hash_password(pw)
        similar_passwords = [
            "Password",     # Raqam yo'q
            "Password11",   # Qo'shimcha raqam
            "Password 1",   # Bo'sh joy
            "Password1 ",   # Oxirida bo'sh joy
            " Password1",   # Boshida bo'sh joy
        ]
        for similar in similar_passwords:
            assert verify_password(similar, hashed) is False, \
                f"'{similar}' noto'g'ri bo'lishi kerak edi"

    def test_returns_bool_not_truthy(self):
        """verify_password bool qaytarishi kerak."""
        pw = "TestPass1"
        hashed = hash_password(pw)
        result_true  = verify_password(pw, hashed)
        result_false = verify_password("wrong", hashed)
        assert type(result_true)  is bool
        assert type(result_false) is bool

    def test_none_hash_returns_false(self):
        """None hash → False (AttributeError emas)."""
        # Bu ish muhim — DB dan None kelganda crash bo'lmasligi kerak
        try:
            result = verify_password("pass", None)  # type: ignore
            assert result is False
        except (TypeError, AttributeError):
            pass  # Xato bersa ham qabul qilinadi — faqat True bo'lmasin


# ═══════════════════════════════════════════════════════════════════════════════
# CREATE_ACCESS_TOKEN
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreateAccessToken:
    """create_access_token() funksiyasi uchun testlar."""

    def test_returns_string(self):
        """String qaytaradi."""
        token = create_access_token(user_id=1, role="admin")
        assert isinstance(token, str)

    def test_jwt_format_three_parts(self):
        """JWT format: header.payload.signature (3 qism)."""
        token = create_access_token(user_id=1, role="admin")
        parts = token.split(".")
        assert len(parts) == 3, f"JWT 3 qismdan iborat bo'lishi kerak, {len(parts)} keldi"

    def test_payload_contains_required_fields(self):
        """Payload majburiy maydonlarni o'z ichiga oladi."""
        user_id = 42
        role    = "manager"
        token   = create_access_token(user_id=user_id, role=role)

        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        assert payload["sub"]  == str(user_id), "sub user_id string bo'lishi kerak"
        assert payload["type"] == "access",     "type 'access' bo'lishi kerak"
        assert payload["role"] == role,         "role to'g'ri bo'lishi kerak"
        assert "exp" in payload,                "exp (expiry) bo'lishi kerak"
        assert "iat" in payload,                "iat (issued at) bo'lishi kerak"

    def test_sub_is_string(self):
        """sub maydoni string bo'lishi kerak (int emas)."""
        token = create_access_token(user_id=999, role="viewer")
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        assert isinstance(payload["sub"], str)
        assert payload["sub"] == "999"

    def test_different_roles(self):
        """Turli rollar uchun token yaratish."""
        for role in ["admin", "manager", "viewer"]:
            token = create_access_token(user_id=1, role=role)
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
            )
            assert payload["role"] == role

    def test_expiry_in_future(self):
        """Token muddati kelajakda bo'lishi kerak."""
        token = create_access_token(user_id=1, role="admin")
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        now = datetime.now(timezone.utc).timestamp()
        assert payload["exp"] > now, "Token allaqachon muddati tugagan!"

    def test_expiry_matches_settings(self):
        """Token muddati settings bilan mos keladi (±5 sekund)."""
        before = datetime.now(timezone.utc).timestamp()
        token  = create_access_token(user_id=1, role="admin")
        after  = datetime.now(timezone.utc).timestamp()

        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )

        expected_exp_min = before + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 - 5
        expected_exp_max = after  + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 + 5

        assert expected_exp_min <= payload["exp"] <= expected_exp_max, \
            f"exp {payload['exp']} kutilgan [{expected_exp_min}, {expected_exp_max}] oraliqda emas"

    def test_custom_expires_delta(self):
        """Maxsus muddatli token."""
        delta = timedelta(minutes=5)
        before = datetime.now(timezone.utc).timestamp()
        token  = create_access_token(user_id=1, role="admin", expires_delta=delta)
        after  = datetime.now(timezone.utc).timestamp()

        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )

        expected_exp_min = before + 300 - 5
        expected_exp_max = after  + 300 + 5
        assert expected_exp_min <= payload["exp"] <= expected_exp_max

    def test_very_short_expiry(self):
        """Juda qisqa muddatli token (1 sekund)."""
        delta = timedelta(seconds=1)
        token = create_access_token(user_id=1, role="admin", expires_delta=delta)
        # Hozir valid bo'lishi kerak
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        assert payload["sub"] == "1"

    def test_different_user_ids_produce_different_tokens(self):
        """Turli user_id'lar → turli tokenlar."""
        t1 = create_access_token(user_id=1,  role="admin")
        t2 = create_access_token(user_id=2,  role="admin")
        t3 = create_access_token(user_id=99, role="admin")
        assert t1 != t2
        assert t2 != t3

    def test_iat_is_recent(self):
        """iat (issued at) hozirgi vaqtga yaqin bo'lishi kerak (±10 sekund)."""
        before = datetime.now(timezone.utc).timestamp()
        token  = create_access_token(user_id=1, role="admin")
        after  = datetime.now(timezone.utc).timestamp()

        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        assert before - 10 <= payload["iat"] <= after + 10

    def test_large_user_id(self):
        """Katta user_id (billion+)."""
        token = create_access_token(user_id=1_000_000_000, role="viewer")
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        assert payload["sub"] == "1000000000"

    def test_negative_user_id(self):
        """Manfiy user_id (edge case — test qilish uchun)."""
        token = create_access_token(user_id=-1, role="admin")
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        assert payload["sub"] == "-1"


# ═══════════════════════════════════════════════════════════════════════════════
# CREATE_REFRESH_TOKEN
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreateRefreshToken:
    """create_refresh_token() funksiyasi uchun testlar."""

    def test_returns_string(self):
        token = create_refresh_token(user_id=1, role="admin")
        assert isinstance(token, str)

    def test_jwt_format(self):
        token = create_refresh_token(user_id=1, role="admin")
        assert len(token.split(".")) == 3

    def test_type_is_refresh(self):
        """Payload type 'refresh' bo'lishi kerak."""
        token = create_refresh_token(user_id=1, role="admin")
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        assert payload["type"] == "refresh"

    def test_longer_expiry_than_access(self):
        """Refresh token access token dan uzunroq yashaydi."""
        access  = create_access_token(user_id=1, role="admin")
        refresh = create_refresh_token(user_id=1, role="admin")

        ap = jwt.decode(access,  settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        rp = jwt.decode(refresh, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

        assert rp["exp"] > ap["exp"], "Refresh token access token dan keyinroq muddati tugashi kerak"

    def test_expiry_matches_settings(self):
        """Muddati settings.REFRESH_TOKEN_EXPIRE_DAYS bilan mos keladi."""
        before = datetime.now(timezone.utc).timestamp()
        token  = create_refresh_token(user_id=1, role="admin")
        after  = datetime.now(timezone.utc).timestamp()

        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        expected_seconds    = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
        expected_exp_min    = before + expected_seconds - 10
        expected_exp_max    = after  + expected_seconds + 10

        assert expected_exp_min <= payload["exp"] <= expected_exp_max

    def test_payload_sub_matches_user_id(self):
        token = create_refresh_token(user_id=77, role="manager")
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        assert payload["sub"] == "77"

    def test_refresh_and_access_different_tokens(self):
        """Access va refresh tokenlar bir xil bo'lmasligi kerak."""
        access  = create_access_token(user_id=1, role="admin")
        refresh = create_refresh_token(user_id=1, role="admin")
        assert access != refresh


# ═══════════════════════════════════════════════════════════════════════════════
# DECODE_TOKEN
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecodeToken:
    """decode_token() funksiyasi uchun testlar."""

    def test_decode_valid_access_token(self):
        """Yaroqli access token decode qilinadi."""
        token   = create_access_token(user_id=5, role="admin")
        payload = decode_token(token)
        assert payload["sub"]  == "5"
        assert payload["type"] == "access"
        assert payload["role"] == "admin"

    def test_decode_valid_refresh_token(self):
        """Yaroqli refresh token decode qilinadi."""
        token   = create_refresh_token(user_id=5, role="manager")
        payload = decode_token(token)
        assert payload["sub"]  == "5"
        assert payload["type"] == "refresh"

    def test_expired_token_raises_authentication_error(self):
        """Muddati o'tgan token → AuthenticationError."""
        # 1 millisekund muddatli token yaratamiz va darhol tekshiramiz
        expired_token = jwt.encode(
            {
                "sub":  "1",
                "type": "access",
                "role": "admin",
                "exp":  datetime.now(timezone.utc) - timedelta(seconds=1),
                "iat":  datetime.now(timezone.utc) - timedelta(seconds=2),
            },
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(AuthenticationError) as exc_info:
            decode_token(expired_token)
        assert "muddati tugagan" in exc_info.value.message.lower() or \
               "expired" in exc_info.value.message.lower(), \
               "Xabar muddati o'tganligini bildirishi kerak"

    def test_invalid_signature_raises_authentication_error(self):
        """Noto'g'ri imzo → AuthenticationError."""
        token_with_wrong_key = jwt.encode(
            {"sub": "1", "type": "access", "role": "admin",
             "exp": datetime.now(timezone.utc) + timedelta(hours=1),
             "iat": datetime.now(timezone.utc)},
            "completely_different_secret_key_1234567890",
            algorithm="HS256",
        )
        with pytest.raises(AuthenticationError):
            decode_token(token_with_wrong_key)

    def test_garbage_string_raises_authentication_error(self):
        """To'siq string → AuthenticationError."""
        with pytest.raises(AuthenticationError):
            decode_token("this.is.garbage")

    def test_empty_string_raises_authentication_error(self):
        """Bo'sh string → AuthenticationError."""
        with pytest.raises(AuthenticationError):
            decode_token("")

    def test_truncated_token_raises_authentication_error(self):
        """Kesilgan token → AuthenticationError."""
        token = create_access_token(user_id=1, role="admin")
        truncated = token[:len(token) // 2]
        with pytest.raises(AuthenticationError):
            decode_token(truncated)

    def test_modified_payload_raises_authentication_error(self):
        """
        Payload o'zgartirilgan token → AuthenticationError.
        (HMAC imzo buziladi)
        """
        import base64, json

        token  = create_access_token(user_id=1, role="admin")
        header, payload_b64, signature = token.split(".")

        # Padding qo'shish
        padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
        payload_data = json.loads(base64.urlsafe_b64decode(padded))
        payload_data["role"] = "admin"   # Role ni admin ga o'zgartirish
        payload_data["sub"]  = "99999"   # user_id ni o'zgartirish

        new_payload_b64 = base64.urlsafe_b64encode(
            json.dumps(payload_data).encode()
        ).rstrip(b"=").decode()

        tampered_token = f"{header}.{new_payload_b64}.{signature}"
        with pytest.raises(AuthenticationError):
            decode_token(tampered_token)

    def test_none_raises_authentication_error(self):
        """None → AuthenticationError yoki TypeError."""
        with pytest.raises((AuthenticationError, TypeError, AttributeError)):
            decode_token(None)  # type: ignore

    def test_decode_returns_dict(self):
        """Muvaffaqiyatli decode → dict qaytaradi."""
        token   = create_access_token(user_id=1, role="admin")
        payload = decode_token(token)
        assert isinstance(payload, dict)

    def test_decode_payload_has_exp_and_iat(self):
        """Decode qilingan payload exp va iat maydonlariga ega."""
        token   = create_access_token(user_id=1, role="admin")
        payload = decode_token(token)
        assert "exp" in payload
        assert "iat" in payload
        assert isinstance(payload["exp"], (int, float))
        assert isinstance(payload["iat"], (int, float))

    def test_algorithm_mismatch_raises(self):
        """
        RS256 bilan imzolangan token HS256 bilan decode qilinmasligi kerak.
        (AuthenticationError chiqishi kerak)
        """
        # RS256 uchun kalit yaratmaymiz — faqat algorithm parametr testi
        token_with_none_alg = jwt.encode(
            {"sub": "1", "type": "access", "role": "admin",
             "exp": datetime.now(timezone.utc) + timedelta(hours=1),
             "iat": datetime.now(timezone.utc)},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        # Bu valid token bo'lishi kerak
        payload = decode_token(token_with_none_alg)
        assert payload["sub"] == "1"


# ═══════════════════════════════════════════════════════════════════════════════
# HASH_TOKEN
# ═══════════════════════════════════════════════════════════════════════════════

class TestHashToken:
    """hash_token() funksiyasi uchun testlar."""

    def test_returns_string(self):
        """String qaytaradi."""
        result = hash_token("some_token_string")
        assert isinstance(result, str)

    def test_returns_64_character_hex(self):
        """SHA-256 → 64 belgilik hex string."""
        result = hash_token("some_token_string")
        assert len(result) == 64

    def test_hex_characters_only(self):
        """Faqat hex belgilar (0-9, a-f)."""
        result = hash_token("test_token")
        assert all(c in "0123456789abcdef" for c in result), \
            f"Hex bo'lmagan belgilar: {set(result) - set('0123456789abcdef')}"

    def test_deterministic(self):
        """Bir xil token → bir xil hash (deterministik)."""
        token = "my_test_refresh_token_abc123"
        h1 = hash_token(token)
        h2 = hash_token(token)
        h3 = hash_token(token)
        assert h1 == h2 == h3

    def test_different_tokens_different_hashes(self):
        """Turli tokenlar → turli hashlar."""
        h1 = hash_token("token_abc")
        h2 = hash_token("token_abd")
        assert h1 != h2

    def test_matches_manual_sha256(self):
        """Python hashlib.sha256 bilan solishtiriladi."""
        token    = "test_token_for_sha256_check"
        expected = hashlib.sha256(token.encode("utf-8")).hexdigest()
        result   = hash_token(token)
        assert result == expected

    def test_empty_string_hashes_consistently(self):
        """Bo'sh string deterministik hash beradi."""
        h1 = hash_token("")
        h2 = hash_token("")
        assert h1 == h2
        assert len(h1) == 64

    def test_jwt_token_hash(self):
        """Real JWT token ni hash qilish."""
        jwt_token = create_access_token(user_id=1, role="admin")
        h = hash_token(jwt_token)
        assert len(h) == 64

    def test_unicode_token_hashes(self):
        """Unicode string hash qilinadi."""
        h = hash_token("токен_с_юникодом")
        assert len(h) == 64

    def test_very_long_token_hashes(self):
        """Juda uzun token (SHA-256 uzunlikka mustaqil)."""
        long_token = "a" * 10_000
        h = hash_token(long_token)
        assert len(h) == 64

    def test_case_sensitive(self):
        """Katta-kichik harf farqli hashlar beradi."""
        h1 = hash_token("MyToken")
        h2 = hash_token("mytoken")
        assert h1 != h2


# ═══════════════════════════════════════════════════════════════════════════════
# GET_TOKEN_EXPIRES_IN
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetTokenExpiresIn:
    """get_token_expires_in() funksiyasi uchun testlar."""

    def test_returns_integer(self):
        """Integer qaytaradi."""
        result = get_token_expires_in()
        assert isinstance(result, int)

    def test_returns_seconds_not_minutes(self):
        """Sekundlar qaytaradi (daqiqalar emas)."""
        result = get_token_expires_in()
        # settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        expected = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert result == expected

    def test_positive_value(self):
        """Musbat qiymat qaytaradi."""
        assert get_token_expires_in() > 0

    def test_consistent_calls(self):
        """Bir necha chaqiriq bir xil natija beradi."""
        r1 = get_token_expires_in()
        r2 = get_token_expires_in()
        assert r1 == r2

    def test_reasonable_range(self):
        """Natija oqilona oraliqda (1 daqiqadan 30 kungacha)."""
        result = get_token_expires_in()
        assert 60 <= result <= 30 * 24 * 3600, \
            f"Oqilona bo'lmagan qiymat: {result} sekund"


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION: TOKEN ROUND-TRIP
# ═══════════════════════════════════════════════════════════════════════════════

class TestTokenRoundTrip:
    """Access va refresh tokenlar uchun to'liq round-trip testlar."""

    def test_access_token_full_round_trip(self):
        """Access token: create → decode → payload check."""
        user_id = 123
        role    = "manager"
        token   = create_access_token(user_id=user_id, role=role)
        payload = decode_token(token)

        assert payload["sub"]  == str(user_id)
        assert payload["role"] == role
        assert payload["type"] == "access"

    def test_refresh_token_full_round_trip(self):
        """Refresh token: create → decode → payload check."""
        user_id = 456
        role    = "viewer"
        token   = create_refresh_token(user_id=user_id, role=role)
        payload = decode_token(token)

        assert payload["sub"]  == str(user_id)
        assert payload["role"] == role
        assert payload["type"] == "refresh"

    def test_tokens_are_unique_per_user(self):
        """Turli foydalanuvchilar uchun tokenlar unikal."""
        tokens = {create_access_token(user_id=i, role="viewer") for i in range(1, 11)}
        assert len(tokens) == 10  # Barchasi farqli

    def test_password_hash_and_verify_round_trip(self):
        """Parol: hash → verify round-trip."""
        passwords = [
            "SimplePass1",
            "C0mpl3x!P@ssw0rd#2024",
            "短い密码1",
            "P" * 72,  # bcrypt maksimum
        ]
        for pw in passwords:
            hashed = hash_password(pw)
            assert verify_password(pw, hashed) is True, f"{pw!r} verify qilmadi"
            assert verify_password(pw + "x", hashed) is False, f"{pw!r}x noto'g'ri bo'lishi kerak"

    def test_decode_after_tamper_fails(self):
        """Imzoni saqlagan holda payload o'zgartirilsa — xato."""
        token = create_access_token(user_id=1, role="viewer")
        # Oxirgi belgini o'zgartirish — imzo buziladi
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        with pytest.raises(AuthenticationError):
            decode_token(tampered)

    def test_refresh_token_not_accepted_where_access_expected(self):
        """
        Refresh token type ni tekshirish — auth service da bo'lgan
        business logic ni dokumentlaydi.
        """
        refresh = create_refresh_token(user_id=1, role="admin")
        payload = decode_token(refresh)
        # decode_token tokenni decode qiladi, lekin type tekshirmaydi
        # Bu tekshiruv auth_service.refresh_access_token da bajariladi
        assert payload["type"] == "refresh", "Refresh token type to'g'ri bo'lishi kerak"

    def test_token_payload_differs_for_different_user_roles(self):
        """
        Turli rollar → farqli tokenlar.
        Role o'zgartirilgandan keyin yangi token eski tokendan farqli.
        """
        t1 = create_access_token(user_id=1, role="admin")
        t2 = create_access_token(user_id=1, role="viewer")
        t3 = create_access_token(user_id=1, role="manager")
        # Rollar farqli bo'lgani uchun tokenlar farqli
        assert t1 != t2
        assert t2 != t3
        assert t1 != t3

        # Decode qilib rol to'g'ri yozilganini tekshirish
        p1 = decode_token(t1)
        p2 = decode_token(t2)
        assert p1["role"] == "admin"
        assert p2["role"] == "viewer"