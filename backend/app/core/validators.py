"""
Environment and configuration validation utilities.

Validates that all required settings are properly configured
before application starts. Prevents runtime errors due to
missing or invalid configuration.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

from app.config import settings


logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""
    
    passed: bool
    message: str
    severity: str = "error"  # "error", "warning", "info"
    
    def __str__(self) -> str:
        """String representation."""
        icon = "✓" if self.passed else "✗"
        return f"{icon} [{self.severity.upper()}] {self.message}"


class EnvironmentValidator:
    """
    Validates application environment and configuration.
    
    Performs comprehensive checks on:
    - Required environment variables
    - File system paths and permissions
    - Database connectivity
    - External service availability
    """
    
    def __init__(self):
        """Initialize validator."""
        self.results: List[ValidationResult] = []
    
    def validate_all(self) -> bool:
        """
        Run all validation checks.
        
        Returns:
            True if all critical checks passed, False otherwise
        """
        logger.info("Starting environment validation...")
        
        # Run all checks
        self._validate_secret_key()       # ← BIRINCHI — xavfsizlik
        self._validate_required_settings()
        self._validate_database_url()
        self._validate_directories()
        self._validate_cors_origins()
        self._validate_log_settings()
        self._validate_ml_settings()
        
        # Print results
        self._print_results()
        
        # Check if any critical errors
        critical_errors = [
            r for r in self.results 
            if not r.passed and r.severity == "error"
        ]
        
        if critical_errors:
            logger.error(f"Validation failed with {len(critical_errors)} critical errors")
            return False
        
        logger.info("Environment validation passed ✓")
        return True

    def _validate_secret_key(self) -> None:
        """
        JWT SECRET_KEY xavfsizligini tekshirish.

        Agar default yoki zaif kalit ishlatilsa — production da CRITICAL xato.
        Development rejimda faqat ogohlantirish.
        """
        INSECURE_DEFAULTS = {
            "changeme-use-secrets-token-hex-32-in-production",
            "CHANGE_THIS_IN_PRODUCTION_USE_OPENSSL_RAND_HEX_32",
            "your-secret-key-here-change-in-production",
            "changeme",
            "secret",
            "your-secret-key",
            "development-secret",
            "test-secret",
            "",
        }
        key = settings.SECRET_KEY

        if key in INSECURE_DEFAULTS:
            if not settings.DEBUG:
                self.results.append(ValidationResult(
                    passed=False,
                    message=(
                        "SECRET_KEY default qiymatda! Production da bu KRITIK xavfsizlik zaifligidir. "
                        "Yangi kalit yaratish: python -c \"import secrets; print(secrets.token_hex(32))\""
                    ),
                    severity="error",
                ))
            else:
                self.results.append(ValidationResult(
                    passed=False,
                    message=(
                        "SECRET_KEY default qiymatda (debug rejim uchun qabul qilinadi). "
                        "Production ga o'tishdan oldin albatta o'zgartiring!"
                    ),
                    severity="warning",
                ))
            return

        if len(key) < 32:
            self.results.append(ValidationResult(
                passed=False,
                message=(
                    f"SECRET_KEY juda qisqa ({len(key)} belgi). "
                    "Kamida 32 belgi bo'lishi kerak. "
                    "Yangi kalit: python -c \"import secrets; print(secrets.token_hex(32))\""
                ),
                severity="error" if not settings.DEBUG else "warning",
            ))
            return

        self.results.append(ValidationResult(
            passed=True,
            message=f"SECRET_KEY xavfsiz konfiguratsiya qilingan ({len(key)} belgi)",
            severity="info",
        ))
    
    def _validate_required_settings(self) -> None:
        """Check that required settings are set."""
        required = [
            ("APP_NAME", settings.APP_NAME),
            ("APP_VERSION", settings.APP_VERSION),
            ("DATABASE_URL", settings.DATABASE_URL),
        ]
        
        for name, value in required:
            if not value or value.strip() == "":
                self.results.append(ValidationResult(
                    passed=False,
                    message=f"Required setting {name} is not set",
                    severity="error"
                ))
            else:
                self.results.append(ValidationResult(
                    passed=True,
                    message=f"Setting {name} is configured",
                    severity="info"
                ))
    
    def _validate_database_url(self) -> None:
        """Validate database URL format."""
        db_url = settings.DATABASE_URL
        
        # Check if URL is valid
        valid_prefixes = ["postgresql://", "postgresql+asyncpg://", "sqlite://"]
        
        if not any(db_url.startswith(prefix) for prefix in valid_prefixes):
            self.results.append(ValidationResult(
                passed=False,
                message=f"Invalid DATABASE_URL format. Must start with {valid_prefixes}",
                severity="error"
            ))
            return
        
        # Check if contains credentials (for PostgreSQL)
        if db_url.startswith("postgresql"):
            if "@" not in db_url:
                self.results.append(ValidationResult(
                    passed=False,
                    message="DATABASE_URL missing credentials (username:password@host)",
                    severity="error"
                ))
            else:
                self.results.append(ValidationResult(
                    passed=True,
                    message="Database URL format is valid",
                    severity="info"
                ))
        else:
            self.results.append(ValidationResult(
                passed=True,
                message="Database URL format is valid",
                severity="info"
            ))
    
    def _validate_directories(self) -> None:
        """Validate that required directories exist or can be created."""
        directories = [
            ("Log directory", settings.LOG_DIR),
            ("Upload directory", settings.UPLOAD_DIR if hasattr(settings, 'UPLOAD_DIR') else "./data/uploads"),
            ("ML models directory", settings.ML_MODEL_PATH if hasattr(settings, 'ML_MODEL_PATH') else "./ml/models"),
        ]
        
        for name, path_str in directories:
            path = Path(path_str)
            
            try:
                # Try to create directory if it doesn't exist
                path.mkdir(parents=True, exist_ok=True)
                
                # Check if writable
                test_file = path / ".write_test"
                test_file.touch()
                test_file.unlink()
                
                self.results.append(ValidationResult(
                    passed=True,
                    message=f"{name} exists and is writable: {path}",
                    severity="info"
                ))
            except PermissionError:
                self.results.append(ValidationResult(
                    passed=False,
                    message=f"{name} is not writable: {path}",
                    severity="error"
                ))
            except Exception as e:
                self.results.append(ValidationResult(
                    passed=False,
                    message=f"Failed to validate {name}: {str(e)}",
                    severity="error"
                ))
    
    def _validate_cors_origins(self) -> None:
        """Validate CORS origins configuration."""
        origins = settings.CORS_ORIGINS
        
        if not origins:
            self.results.append(ValidationResult(
                passed=False,
                message="CORS_ORIGINS is empty. Frontend won't be able to connect!",
                severity="warning"
            ))
            return
        
        # Check if origins are valid URLs
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE
        )
        
        invalid_origins = []
        for origin in origins:
            if not url_pattern.match(origin):
                invalid_origins.append(origin)
        
        if invalid_origins:
            self.results.append(ValidationResult(
                passed=False,
                message=f"Invalid CORS origins: {invalid_origins}",
                severity="warning"
            ))
        else:
            self.results.append(ValidationResult(
                passed=True,
                message=f"CORS configured with {len(origins)} origin(s)",
                severity="info"
            ))
    
    def _validate_log_settings(self) -> None:
        """Validate logging configuration."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        
        if settings.LOG_LEVEL.upper() not in valid_levels:
            self.results.append(ValidationResult(
                passed=False,
                message=f"Invalid LOG_LEVEL: {settings.LOG_LEVEL}. Must be one of {valid_levels}",
                severity="error"
            ))
        else:
            self.results.append(ValidationResult(
                passed=True,
                message=f"Log level set to {settings.LOG_LEVEL}",
                severity="info"
            ))
    
    def _validate_ml_settings(self) -> None:
        """Validate ML/AI settings."""
        # Check if YOLO model is specified
        if not hasattr(settings, 'YOLO_MODEL'):
            self.results.append(ValidationResult(
                passed=False,
                message="YOLO_MODEL not configured",
                severity="warning"
            ))
            return
        
        # Check if model file exists
        model_path = Path(settings.ML_MODEL_PATH) / settings.YOLO_MODEL
        
        if not model_path.exists():
            self.results.append(ValidationResult(
                passed=False,
                message=f"YOLO model file not found: {model_path}",
                severity="warning"
            ))
        else:
            self.results.append(ValidationResult(
                passed=True,
                message=f"YOLO model found: {model_path.name}",
                severity="info"
            ))
    
    def _print_results(self) -> None:
        """Print validation results to console."""
        print("\n" + "="*70)
        print("ENVIRONMENT VALIDATION RESULTS")
        print("="*70 + "\n")
        
        # Group by severity
        errors = [r for r in self.results if not r.passed and r.severity == "error"]
        warnings = [r for r in self.results if not r.passed and r.severity == "warning"]
        passed = [r for r in self.results if r.passed]
        
        # Print errors first
        if errors:
            print("🔴 CRITICAL ERRORS:")
            for result in errors:
                print(f"   {result}")
            print()
        
        # Then warnings
        if warnings:
            print("🟡 WARNINGS:")
            for result in warnings:
                print(f"   {result}")
            print()
        
        # Finally passed checks (only in debug mode)
        if settings.DEBUG and passed:
            print("✅ PASSED CHECKS:")
            for result in passed:
                print(f"   {result}")
            print()
        
        # Summary
        total = len(self.results)
        passed_count = len(passed)
        print(f"Summary: {passed_count}/{total} checks passed")
        print("="*70 + "\n")


def validate_environment() -> bool:
    """
    Convenience function to validate environment.
    
    Returns:
        True if validation passed, False otherwise
    
    Raises:
        RuntimeError: If critical validation errors found
    """
    validator = EnvironmentValidator()
    passed = validator.validate_all()
    
    if not passed:
        raise RuntimeError(
            "Environment validation failed. "
            "Please fix the errors above before starting the application."
        )
    
    return True


def check_system_resources() -> Dict[str, Any]:
    """
    Check system resources (CPU, memory, disk).
    
    Returns:
        Dictionary with resource information
    """
    import psutil
    
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
        "cpu_count": psutil.cpu_count(),
        "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "disk_total_gb": round(psutil.disk_usage("/").total / (1024**3), 2),
    }