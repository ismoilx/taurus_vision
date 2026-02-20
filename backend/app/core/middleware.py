"""
FastAPI middleware for request logging and tracing.

Automatically logs all incoming requests and responses with timing.
"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging

from app.core.logging_config import request_id_var, log_with_context


logger = logging.getLogger("api.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging HTTP requests and responses.
    
    Features:
    - Assigns unique request ID to each request
    - Logs request method, path, and parameters
    - Logs response status and timing
    - Tracks performance metrics
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details."""
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)
        
        # Add request ID to request state (accessible in routes)
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Log incoming request
        log_with_context(
            logger,
            logging.INFO,
            f"Request started: {request.method} {request.url.path}",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query_params=str(request.query_params),
            client_host=request.client.host if request.client else "unknown",
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate request duration
            duration = time.time() - start_time
            
            # Log response
            log_with_context(
                logger,
                logging.INFO,
                f"Request completed: {request.method} {request.url.path}",
                request_id=request_id,
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2),
            )
            
            # Record metrics
            from app.core.metrics import metrics
            metrics.record_http_request(
                method=request.method,
                path=request.url.path,
                duration=duration
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Log error
            duration = time.time() - start_time
            log_with_context(
                logger,
                logging.ERROR,
                f"Request failed: {request.method} {request.url.path}",
                request_id=request_id,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration * 1000, 2),
            )
            raise


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """
    Middleware for monitoring slow requests.
    
    Logs warning if request takes longer than threshold.
    """
    
    SLOW_REQUEST_THRESHOLD = 1.0  # seconds
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor request performance."""
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Log slow requests
        if duration > self.SLOW_REQUEST_THRESHOLD:
            logger.warning(
                f"Slow request detected: {request.method} {request.url.path}",
                extra={
                    "extra_data": {
                        "duration_seconds": round(duration, 2),
                        "path": request.url.path,
                        "method": request.method,
                    }
                },
            )
        
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Security headers middleware for production.
    
    Adds security-related HTTP headers to all responses:
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking
    - X-XSS-Protection: Enables XSS filter
    - Strict-Transport-Security: Enforces HTTPS (production only)
    - Content-Security-Policy: Prevents XSS attacks
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Enable XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Content Security Policy (basic)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:;"
        )
        
        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions Policy (formerly Feature Policy)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=()"
        )
        
        # Only add HSTS in production (requires HTTPS)
        from app.config import settings
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        
        return response

# ============================================================================
# Rate Limiting Middleware — Sprint 6
# ============================================================================

import time
from collections import defaultdict
from threading import Lock


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    In-memory rate limiting middleware.

    Sliding window algoritmi — IP boshiga so'rovlar sonini cheklaydi.
    Production da Redis-based rate limiting (FastAPI-limiter) tavsiya etiladi.

    Limits:
        /api/v1/detection/*  — 60 req/min  (kamera so'rovlari)
        /api/v1/animals/*    — 120 req/min (CRUD)
        /api/v1/analytics/*  — 30  req/min (og'ir so'rovlar)
        Boshqa /api/*        — 200 req/min

    Returns:
        429 Too Many Requests — limit oshganda
    """

    # Route-specific limits (requests per minute)
    LIMITS: dict[str, int] = {
        "/api/v1/detection":  60,
        "/api/v1/analytics":  30,
        "/api/v1/reports":    20,
        "/api/v1/export":     10,
        "/api/v1/animals":   120,
        "/api/v1/weights":   120,
    }
    DEFAULT_LIMIT = 200   # req/min
    WINDOW = 60           # seconds

    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self._enabled  = enabled
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def _get_limit(self, path: str) -> int:
        for prefix, limit in self.LIMITS.items():
            if path.startswith(prefix):
                return limit
        return self.DEFAULT_LIMIT

    def _is_limited(self, key: str, limit: int) -> bool:
        """Sliding window rate check. Thread-safe."""
        now = time.monotonic()
        window_start = now - self.WINDOW
        with self._lock:
            # Eski so'rovlarni tozalash
            self._requests[key] = [
                ts for ts in self._requests[key] if ts > window_start
            ]
            if len(self._requests[key]) >= limit:
                return True
            self._requests[key].append(now)
            return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Health check, metrics, WebSocket — limit qo'llanilmaydi
        path = request.url.path
        if not self._enabled or path in ("/health", "/health/live", "/metrics"):
            return await call_next(request)

        if path.startswith("/api/"):
            ip    = request.client.host if request.client else "unknown"
            key   = f"{ip}:{path.split('/')[3] if len(path.split('/')) > 3 else 'api'}"
            limit = self._get_limit(path)

            if self._is_limited(key, limit):
                return Response(
                    content='{"detail":"Too Many Requests. Iltimos, biroz kuting."}',
                    status_code=429,
                    media_type="application/json",
                    headers={
                        "Retry-After": str(self.WINDOW),
                        "X-RateLimit-Limit":  str(limit),
                        "X-RateLimit-Reset":  str(int(time.time()) + self.WINDOW),
                    },
                )

        return await call_next(request)