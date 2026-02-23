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

from typing import Optional
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

    APP_NAME: str = "Taurus Vision API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # =========================================================================
    # SERVER
    # =========================================================================

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # =========================================================================
    # DATABASE
    # =========================================================================

    DATABASE_URL: str = "postgresql+asyncpg://taurus:taurus123@localhost:5432/taurus_vision"

    # =========================================================================
    # CACHE & QUEUE (Redis)
    # =========================================================================

    REDIS_URL: str = "redis://localhost:6379/0"

    # =========================================================================
    # CELERY
    # =========================================================================

    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # =========================================================================
    # CORS
    # =========================================================================

    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",  # Vite dev server (frontend)
        "http://localhost:3000",  # Muqobil React dev server
        "http://localhost:8080",  # Muqobil port
    ]

    # =========================================================================
    # FILE STORAGE
    # =========================================================================

    # Yuklangan rasm va fayllar saqlanadigan papka
    UPLOAD_DIR: str = "./data/images"

    # Maksimal fayl hajmi (bytes): 10 MB
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024

    # =========================================================================
    # ML MODELS
    # =========================================================================

    # ML model fayllari papkasi (Docker ichida: /app/ml/models)
    ML_MODEL_PATH: str = "./ml/models"

    # YOLO model fayl nomi (ml/models/ papkasida bo'lishi kerak)
    YOLO_MODEL: str = "yolo11n.pt"

    # =========================================================================
    # AI INFERENCE
    # =========================================================================

    # Minimum detection confidence (0.0 — 1.0)
    AI_CONFIDENCE_THRESHOLD: float = 0.5

    # COCO dataset klasslar: 19 = cow, 20 = sheep
    AI_TARGET_CLASSES: list[int] = [19, 20]

    # Har N-nchi kadrni qayta ishlash (performance optimizatsiya)
    FRAME_SKIP: int = 5

    # =========================================================================
    # ANIMAL IDENTIFICATION (MobileNetV2 muzzle recognition)
    # =========================================================================

    # Cosine similarity threshold: bu qiymatdan yuqori = tanildi
    # 0.80 = MobileNetV2 muzzle recognition uchun optimal qiymat (README ga mos)
    # ESLATMA: 0.10 xato edi — deyarli har qanday jonivor false match berardi
    IDENTIFICATION_THRESHOLD: float = 0.80

    # Har bir jonivor uchun maksimal saqlangan embedding soni
    MAX_EMBEDDINGS_PER_ANIMAL: int = 10

    # MobileNetV2 chiqish vektori o'lchami
    EMBEDDING_DIM: int = 1280

    # =========================================================================
    # CAMERA
    # =========================================================================

    # Kamera manzili: "rtsp://ip:554/stream" yoki "/dev/video0" yoki None
    # None bo'lsa — SimulatedCamera ishlatiladi (development uchun)
    CAMERA_URL: Optional[str] = None

    # =========================================================================
    # LOGGING
    # =========================================================================

    # Log darajasi: DEBUG | INFO | WARNING | ERROR | CRITICAL
    LOG_LEVEL: str = "INFO"

    # Log fayllari papkasi
    LOG_DIR: str = "./data/logs"

    # Log formati: "json" (production) | "console" (development)
    LOG_FORMAT: str = "json"

    # Avtomatik log rotation (kunlik)
    LOG_ROTATION: bool = True

    # Log fayllarini necha kun saqlash
    LOG_RETENTION_DAYS: int = 30

    # =========================================================================
    # SECURITY (JWT — Authentication uchun)
    # =========================================================================

    # JWT imzolash uchun maxfiy kalit
    # DIQQAT: Production da shu qiymatni murakkab random string bilan almashtiring!
    # Generatsiya: python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY: str = "changeme-use-secrets-token-hex-32-in-production"

    # JWT algoritmi
    JWT_ALGORITHM: str = "HS256"

    # Access token amal qilish muddati (daqiqa)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Refresh token amal qilish muddati (kun)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # =========================================================================
    # PYDANTIC SETTINGS CONFIG
    # =========================================================================

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# =============================================================================
# Global settings instance
# Butun application bo'ylab shu obyekt import qilinadi:
#     from app.config import settings
# =============================================================================

settings = Settings()


def get_database_url() -> str:
    """
    SQLAlchemy uchun database URL ni qaytaradi.

    Returns:
        str: Async PostgreSQL connection string
    """
    return settings.DATABASE_URL