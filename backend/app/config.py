"""
Configuration settings for Taurus Vision backend.

This module uses Pydantic Settings to load configuration from environment
variables with sensible defaults for development.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings.
    
    All settings can be overridden via environment variables.
    For production, create a .env file in backend/ directory.
    """
    
    # Application
    APP_NAME: str = "Taurus Vision API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database
    DATABASE_URL: str = "postgresql://taurus:taurus123@localhost:5432/taurus_vision"
    # For SQLite in development (uncomment to use):
    # DATABASE_URL: str = "sqlite:///./taurus_vision.db"
    
    # CORS (keyinroq frontend uchun)
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",  # React dev server
        "http://localhost:8080",  # Alternative
    ]
    
    # ML Models
    ML_MODEL_PATH: str = "./ml/models"
    YOLO_MODEL: str = "yolov8n.pt"
    
    # Camera
    CAMERA_URL: Optional[str] = None  # rtsp://... yoki /dev/video0
    
    # File Storage
    UPLOAD_DIR: str = "./data/images"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./data/logs/app.log"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


# Global settings instance
settings = Settings()


# Helper function for database URL
def get_database_url() -> str:
    """
    Get database URL for SQLAlchemy.
    
    Returns:
        Database connection string
    """
    return settings.DATABASE_URL
