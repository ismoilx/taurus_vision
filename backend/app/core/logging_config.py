"""
Professional logging configuration for Taurus Vision.

Features:
- JSON structured logging for production
- Console logging for development
- Log rotation with size and time limits
- Request ID tracking
- Performance logging
- Separate log files by severity
"""

import logging
import sys
from pathlib import Path
from typing import Any
import json
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from contextvars import ContextVar

from app.config import settings


# Context variable for request ID tracking
request_id_var: ContextVar[str] = ContextVar("request_id", default="system")


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    
    Outputs logs in JSON format for easy parsing by log aggregators
    like ELK stack, CloudWatch, etc.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "request_id": request_id_var.get(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data
        
        return json.dumps(log_data)


class ColoredConsoleFormatter(logging.Formatter):
    """
    Colored console formatter for development.
    
    Makes logs easier to read during development.
    """
    
    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
        "RESET": "\033[0m",       # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]
        
        # Format: [TIME] LEVEL | logger | message
        log_message = (
            f"{color}[{self.formatTime(record, '%H:%M:%S')}] "
            f"{record.levelname:8s}{reset} | "
            f"{record.name:20s} | "
            f"{record.getMessage()}"
        )
        
        if record.exc_info:
            log_message += f"\n{self.formatException(record.exc_info)}"
        
        return log_message


def setup_logging() -> None:
    """
    Setup application logging configuration.
    
    This function should be called once at application startup.
    Configures both file and console logging with appropriate formatters.
    """
    # Create logs directory if it doesn't exist
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all levels
    
    # Remove any existing handlers
    root_logger.handlers.clear()
    
    # ===== CONSOLE HANDLER (Development) =====
    if settings.DEBUG:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(ColoredConsoleFormatter())
        root_logger.addHandler(console_handler)
    
    # ===== FILE HANDLERS (Production) =====
    
    # 1. All logs (INFO and above) - Rotating by size
    all_logs_handler = RotatingFileHandler(
        filename=log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    all_logs_handler.setLevel(logging.INFO)
    all_logs_handler.setFormatter(
        JSONFormatter() if not settings.DEBUG else ColoredConsoleFormatter()
    )
    root_logger.addHandler(all_logs_handler)
    
    # 2. Error logs only - Rotating daily
    error_handler = TimedRotatingFileHandler(
        filename=log_dir / "error.log",
        when="midnight",
        interval=1,
        backupCount=30,  # Keep 30 days
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(error_handler)
    
    # 3. Access logs (for FastAPI requests)
    access_handler = RotatingFileHandler(
        filename=log_dir / "access.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    access_handler.setLevel(logging.INFO)
    access_handler.setFormatter(JSONFormatter())
    
    # Create separate logger for access logs
    access_logger = logging.getLogger("api.access")
    access_logger.addHandler(access_handler)
    access_logger.propagate = False
    
    # ===== THIRD-PARTY LIBRARY LOGGERS =====
    
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured successfully",
        extra={
            "extra_data": {
                "log_dir": str(log_dir),
                "debug_mode": settings.DEBUG,
                "log_level": settings.LOG_LEVEL,
            }
        },
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Configured logger instance
    
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Something happened")
    """
    return logging.getLogger(name)


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    **extra_data: Any,
) -> None:
    """
    Log message with additional context data.
    
    Args:
        logger: Logger instance
        level: Log level (logging.INFO, logging.ERROR, etc.)
        message: Log message
        **extra_data: Additional data to include in log
    
    Example:
        >>> log_with_context(
        ...     logger,
        ...     logging.INFO,
        ...     "User action",
        ...     user_id=123,
        ...     action="login"
        ... )
    """
    logger.log(level, message, extra={"extra_data": extra_data})
