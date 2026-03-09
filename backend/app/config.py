"""
Taurus Vision — Application Configuration

Pydantic Settings orqali barcha sozlamalar environment variable yoki
.env faylidan o'qiladi. Hech qanday secret kod ichida hardcode qilinmagan.

MUHIM QOIDALAR:
    - Har bir sozlama faqat bir marta belgilanadi
    - Barcha default qiymatlar development uchun xavfsiz
    - Production uchun .env fayl orqali override qilish shart
    - Hech qachon Settings klassiga to'g'ridan-to'g'ri secret yozma

FOYDALANISH:
    from app.config import settings
    print(settings.DATABASE_URL)
"""

import secrets
from pathlib import Path
from typing import Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Tizim sozlamalari — environment variables yoki .env faylidan o'qiladi.

    Qo'shish tartibi (yuqoridan past — ustuvorlik pastdan yuqoriga):
        1. Class ichidagi default qiymatlar (eng past ustuvorlik)
        2. .env fayl qiymatlari
        3. Tizim environment variable (eng yuqori ustuvorlik)
    """

    # =========================================================================
    # APPLICATION
    # =========================================================================

    APP_NAME:    str  = "Taurus Vision API"
    APP_VERSION: str  = "0.1.0"
    DEBUG:       bool = True

    # =========================================================================
    # SERVER
    # =========================================================================

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # =========================================================================
    # DATABASE
    # =========================================================================

    DATABASE_URL: str = (
        "postgresql+asyncpg://taurus:taurus123@localhost:5432/taurus_vision"
    )

    # =========================================================================
    # CACHE & QUEUE (Redis)
    # =========================================================================

    REDIS_URL: str = "redis://localhost:6379/0"

    # =========================================================================
    # CELERY
    # =========================================================================

    CELERY_BROKER_URL:    str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # =========================================================================
    # CORS
    # =========================================================================

    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8080",
    ]

    # =========================================================================
    # FILE STORAGE
    # =========================================================================

    UPLOAD_DIR:      str = "./data/images"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024   # 10 MB

    # =========================================================================
    # ML MODELS
    # =========================================================================

    ML_MODEL_PATH: str = "./ml/models"

    # Faol YOLO model fayl nomi (ml/models/ papkasida).
    # YOLO26 — Ultralytics 2025-yil sentabr, CPU uchun 43% tezroq.
    # Deploy qilinsa bu qiymat yangilanadi.
    YOLO_MODEL: str = "yolo26n.pt"

    # =========================================================================
    # MUZZLE DETECTION (Ikkinchi bosqich identifikatsiya)
    # =========================================================================

    # Sigir bbox ichida muzzleni aniqlash uchun custom trained YOLO modeli.
    # Bu model YOLO26 detection dan keyingi ikkinchi bosqichda ishlatiladi:
    #   YOLO26 -> sigir bbox -> MUZZLE_MODEL -> muzzle bbox -> MobileNetV2 -> ID
    # Fayl: backend/ml/models/best.pt (local only, git excluded)
    MUZZLE_MODEL: str = "best.pt"

    # Muzzle detection uchun minimal confidence darajasi.
    # YOLO26 animal detection threshold dan alohida sozlanadi.
    MUZZLE_CONFIDENCE_THRESHOLD: float = 0.40

    # Muzzle topilmasa identifikatsiyani o'tkazib yuborish (True = strict mode).
    # False qilinsa eski heuristik (bbox pastki 45%) ga qaytadi.
    # Development: False (best.pt bo'lmasa ham ishlaydi)
    # Production:  True  (aniq identifikatsiya talab qilinadi)
    MUZZLE_STRICT_MODE: bool = False

    # =========================================================================
    # AI INFERENCE
    # =========================================================================

    AI_CONFIDENCE_THRESHOLD: float      = 0.5
    AI_TARGET_CLASSES:       list[int]  = [19, 20]  # COCO: cow, sheep
    FRAME_SKIP:              int        = 5

    # =========================================================================
    # ANIMAL IDENTIFICATION (MobileNetV2)
    # =========================================================================

    IDENTIFICATION_THRESHOLD:  float = 0.80
    MAX_EMBEDDINGS_PER_ANIMAL: int   = 10
    EMBEDDING_DIM:             int   = 1280

    # =========================================================================
    # CAMERA
    # =========================================================================

    CAMERA_URL: Optional[str] = None

    # =========================================================================
    # TRAINING PIPELINE (Sprint 15-16) ← YANGI BLOK
    # =========================================================================

    # Yig'ilgan training kadrlar papkasi
    # Detection pipeline ishlayotganda shu yerga yoziladi
    TRAINING_FRAMES_DIR: str = "./data/training/frames"

    # Yaratilgan YOLO dataset lari papkasi (har bir run uchun alohida)
    TRAINING_DATASETS_DIR: str = "./data/training/datasets"

    # O'qitilgan modellar saqlanadigan papka (har bir run uchun)
    TRAINING_MODELS_DIR: str = "./data/training/models"

    # Health prediction ML modellari saqlanadigan papka (RF + IsolationForest)
    # Bu papkadagi fayllar restart dan keyin yuklanadi — retrain shart emas.
    PREDICTION_MODELS_DIR: str = "./ml/models/prediction"

    # Fine-tuning uchun base model to'liq yo'li
    # docker-compose volume: /app/ml/models/yolo26n.pt
    TRAINING_BASE_MODEL_PATH: str = "./ml/models/yolo26n.pt"

    # Deploy qilingan custom model yo'li
    # Shu yo'lga nusxalangan model keyingi restart da YOLO_MODEL sifatida yuklanadi
    TRAINING_DEPLOY_MODEL_PATH: str = "./ml/models/yolo_custom.pt"

    # FrameCollector sozlamalari
    TRAINING_COLLECT_EVERY_N: int = 50     # Har 50 ta detectiondan bir kadr saqlash
    TRAINING_MIN_DETECTIONS:  int = 2      # Bir framda min detection soni
    TRAINING_MAX_PER_CAMERA:  int = 500    # Bir kamera uchun max kadr
    TRAINING_MAX_TOTAL:       int = 5000   # Jami max kadr soni
    TRAINING_JPEG_QUALITY:    int = 90     # Saqlash sifati (0-100)

    # Training faol yoki o'chirilganmi
    # False qilinganda FrameCollector kadrlarni yig'maydi (performance talab qilsa)
    TRAINING_COLLECTION_ENABLED: bool = True

    # =========================================================================
    # EMAIL / SMTP  (Bildirishnomalar uchun)
    # =========================================================================

    # Gmail uchun: Google Account → Security → App Passwords → Create
    # Yandex uchun: smtp.yandex.ru:587
    SMTP_HOST:     str  = ""
    SMTP_PORT:     int  = 587
    SMTP_USER:     str  = ""
    SMTP_PASSWORD: str  = ""
    SMTP_FROM:     str  = "Taurus Vision <noreply@taurus-vision.uz>"

    # SMTP_HOST bo'sh bo'lsa — email log ga yoziladi (development mode)
    @property
    def smtp_configured(self) -> bool:
        """SMTP to'liq sozlanganmi (host va user mavjudmi)?"""
        return bool(self.SMTP_HOST and self.SMTP_USER)

    # Vergul bilan ajratilgan email manzillar — alert qabul qiluvchilar
    # Misol: "admin@farm.uz,vet@farm.uz"
    NOTIFICATION_EMAILS: str = ""

    @property
    def notification_recipients(self) -> list[str]:
        """Bildirishnoma oluvchilar ro'yxati (tozalangan)."""
        if not self.NOTIFICATION_EMAILS:
            return []
        return [e.strip() for e in self.NOTIFICATION_EMAILS.split(",") if e.strip()]

    # =========================================================================
    # TELEGRAM NOTIFICATIONS
    # =========================================================================

    # Telegram Bot token: @BotFather → /newbot → token
    TELEGRAM_BOT_TOKEN: str = ""

    # Vergul bilan ajratilgan Telegram chat IDlar
    # Bot bilan /start yozgach: https://api.telegram.org/bot{TOKEN}/getUpdates
    # Misol: "123456789,987654321"
    TELEGRAM_CHAT_IDS: str = ""

    @property
    def telegram_chat_ids(self) -> list[str]:
        """Telegram chat ID ro'yxati (tozalangan)."""
        if not self.TELEGRAM_CHAT_IDS:
            return []
        return [c.strip() for c in self.TELEGRAM_CHAT_IDS.split(",") if c.strip()]

    @property
    def telegram_configured(self) -> bool:
        """Telegram bot sozlanganmi?"""
        return bool(self.TELEGRAM_BOT_TOKEN and self.TELEGRAM_CHAT_IDS)
    
    # =========================================================================
    # LOGGING
    # =========================================================================

    LOG_LEVEL:          str  = "INFO"
    LOG_DIR:            str  = "./data/logs"
    LOG_FORMAT:         str  = "json"
    LOG_ROTATION:       bool = True
    LOG_RETENTION_DAYS: int  = 30

    # =========================================================================
    # SECURITY (JWT)
    # =========================================================================

    SECRET_KEY:                    str = "changeme-use-secrets-token-hex-32-in-production"
    JWT_ALGORITHM:                 str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES:   int = 60
    REFRESH_TOKEN_EXPIRE_DAYS:     int = 7

    # =========================================================================
    # INITIAL ADMIN (Seeder)
    # =========================================================================

    INITIAL_ADMIN_EMAIL:    str = "admin@taurus.uz"
    INITIAL_ADMIN_USERNAME: str = "admin"
    INITIAL_ADMIN_PASSWORD: str = "Admin1234"
    INITIAL_ADMIN_FULLNAME: str = "System Administrator"

    # =========================================================================
    # PYDANTIC SETTINGS
    # =========================================================================

    @model_validator(mode="after")
    def _enforce_secret_key_security(self) -> "Settings":
        """
        SECRET_KEY xavfsizligini Pydantic darajasida tekshirish.

        Bu validator Settings ob'ekti yaratilayotganda (import vaqtida) ishga
        tushadi — ya'ni application start bo'lishidan AVVAL.

        QOIDALAR:
            Production (DEBUG=False):
                - Default yoki zaif kalit → ValueError → tizim ISHGA TUSHMAYDI.
                - Kalit uzunligi < 32 belgi → ValueError → tizim ISHGA TUSHMAYDI.
            Development (DEBUG=True):
                - Default yoki zaif kalit → faqat stderr ga ogohlantirish.
                - Kalit uzunligi < 32 → faqat ogohlantirish.

        YANGI KALIT YARATISH:
            python -c "import secrets; print(secrets.token_hex(32))"
            # yoki
            openssl rand -hex 32
            # yoki Makefile orqali:
            make gen-secret
        """
        import sys

        _INSECURE_DEFAULTS: frozenset[str] = frozenset({
            "changeme-use-secrets-token-hex-32-in-production",
            "CHANGE_THIS_IN_PRODUCTION_USE_OPENSSL_RAND_HEX_32",
            "changeme",
            "secret",
            "your-secret-key",
            "development-secret",
            "test-secret",
            "your-secret-key-here-change-in-production",
            "",
        })

        key        = self.SECRET_KEY
        is_debug   = self.DEBUG
        hint       = (
            "\n  Yangi xavfsiz kalit yaratish uchun:\n"
            "    python -c \"import secrets; print(secrets.token_hex(32))\"\n"
            "  yoki:\n"
            "    make gen-secret\n"
            "  Yaratilgan kalitni backend/.env fayliga yozing:\n"
            "    SECRET_KEY=<yaratilgan_kalit>\n"
        )

        if key in _INSECURE_DEFAULTS:
            msg = (
                f"[TAURUS VISION] SECRET_KEY xavfli default qiymatda!{hint}"
            )
            if not is_debug:
                # Production: to'xtatish — bu KRITIK xavfsizlik xatosi
                raise ValueError(
                    f"[PRODUCTION BLOCKER] {msg}"
                )
            # Development: faqat ogohlantirish, ishga tushishga ruxsat
            print(f"\n{'='*70}\n⚠️  SECURITY WARNING: {msg}{'='*70}\n",
                  file=sys.stderr)
            return self

        if len(key) < 32:
            msg = (
                f"[TAURUS VISION] SECRET_KEY juda qisqa "
                f"({len(key)} belgi, minimum 32 kerak)!{hint}"
            )
            if not is_debug:
                raise ValueError(
                    f"[PRODUCTION BLOCKER] {msg}"
                )
            print(f"\n{'='*70}\n⚠️  SECURITY WARNING: {msg}{'='*70}\n",
                  file=sys.stderr)

        return self

    model_config = SettingsConfigDict(
        env_file          = ".env",
        env_file_encoding = "utf-8",
        case_sensitive    = True,
        extra             = "ignore",
    )

    # =========================================================================
    # COMPUTED PROPERTIES
    # =========================================================================

    @property
    def training_frames_path(self) -> Path:
        """TRAINING_FRAMES_DIR ni Path ob'ektida qaytarish."""
        return Path(self.TRAINING_FRAMES_DIR)

    @property
    def training_models_path(self) -> Path:
        """TRAINING_MODELS_DIR ni Path ob'ektida qaytarish."""
        return Path(self.TRAINING_MODELS_DIR)

    @property
    def prediction_models_path(self) -> Path:
        """Health prediction ML modellari yo'li (RF + IsolationForest)."""
        return Path(self.PREDICTION_MODELS_DIR)

    @property
    def yolo_model_path(self) -> Path:
        """Faol YOLO26 model to'liq yo'li."""
        return Path(self.ML_MODEL_PATH) / self.YOLO_MODEL

    @property
    def muzzle_model_path(self) -> Path:
        """Muzzle detection modeli to'liq yo'li."""
        return Path(self.ML_MODEL_PATH) / self.MUZZLE_MODEL


# =============================================================================
# Global settings instance
# =============================================================================

settings = Settings()


def get_database_url() -> str:
    """SQLAlchemy uchun database URL ni qaytaradi."""
    return settings.DATABASE_URL