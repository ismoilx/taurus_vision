"""
Taurus Vision — Main FastAPI Application

Backend API server uchun kirish nuqtasi.
Middleware, router va lifecycle event larini sozlaydi.

SPRINT 15-16 QO'SHIMCHA:
    startup_event() da FrameCollector inicializatsiya qilinadi.
    Collection TRAINING_COLLECTION_ENABLED=True bo'lsa avtomatik yoqiladi.
"""

from fastapi import FastAPI, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.config import settings
from app.core.logging_config import setup_logging, get_logger
from app.core.middleware import (
    RequestLoggingMiddleware,
    PerformanceMonitoringMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
)
from app.core.validators import validate_environment, check_system_resources
from app.core.database import get_db

from app.api.v1 import router as api_v1_router
from app.api.v1.exception_handlers import (
    entity_not_found_handler,
    entity_already_exists_handler,
    business_rule_violation_handler,
    validation_error_handler,
    authentication_error_handler,
    permission_denied_handler,
    database_error_handler,
)
from app.core.exceptions import (
    EntityNotFoundError,
    EntityAlreadyExistsError,
    BusinessRuleViolationError,
    ValidationError,
    AuthenticationError,
    PermissionDeniedError,
    DatabaseError,
)

# Logging ni bir marta sozlash
setup_logging()
logger = get_logger(__name__)


# =============================================================================
# APPLICATION
# =============================================================================

app = FastAPI(
    title       = settings.APP_NAME,
    version     = settings.APP_VERSION,
    description = (
        "AI-powered livestock farm monitoring system. "
        "Real-time animal detection, identification, ADI scoring and alerts."
    ),
    debug    = settings.DEBUG,
    docs_url = "/docs",
    redoc_url = "/redoc",
)


# =============================================================================
# MIDDLEWARE (pastdan yuqoriga tartibda qo'llaniladi)
# =============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins      = settings.CORS_ORIGINS,
    allow_credentials  = True,
    allow_methods      = ["*"],
    allow_headers      = ["*"],
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, enabled=not settings.DEBUG)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(PerformanceMonitoringMiddleware)


# =============================================================================
# ROUTERS
# =============================================================================

app.include_router(api_v1_router, prefix="/api")


# =============================================================================
# EXCEPTION HANDLERS
# =============================================================================

app.add_exception_handler(EntityNotFoundError,        entity_not_found_handler)
app.add_exception_handler(EntityAlreadyExistsError,   entity_already_exists_handler)
app.add_exception_handler(BusinessRuleViolationError, business_rule_violation_handler)
app.add_exception_handler(ValidationError,            validation_error_handler)
app.add_exception_handler(AuthenticationError,        authentication_error_handler)
app.add_exception_handler(PermissionDeniedError,      permission_denied_handler)
app.add_exception_handler(DatabaseError,              database_error_handler)


# =============================================================================
# CORE ENDPOINTS
# =============================================================================

@app.get("/", tags=["System"])
async def root():
    """API haqida umumiy ma'lumot."""
    return {
        "name":      settings.APP_NAME,
        "version":   settings.APP_VERSION,
        "status":    "running",
        "timestamp": datetime.utcnow().isoformat(),
        "docs":      "/docs",
        "api":       "/api/v1",
        "health":    "/health",
        "metrics":   "/metrics",
    }


@app.get("/health", tags=["System"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    To'liq health check — monitoring va load balancer uchun.

    Returns:
        200: Tizim sog'lom
        503: Tizim ishlamayapti
    """
    from app.core.health import health_checker
    health_report = await health_checker.check_all(db)
    status_code   = 503 if health_report["status"] == "unhealthy" else 200
    return JSONResponse(status_code=status_code, content=health_report)


@app.get("/health/ready", tags=["System"])
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Kubernetes readiness probe."""
    from app.core.health import health_checker
    health_report = await health_checker.check_all(db)
    if health_report["status"] in ("healthy", "degraded"):
        return {"status": "ready"}
    return JSONResponse(
        status_code=503,
        content={"status": "not_ready", "reason": "System unhealthy"},
    )


@app.get("/health/live", tags=["System"])
async def liveness_check():
    """Kubernetes liveness probe."""
    return {"status": "alive"}


@app.get("/metrics", tags=["System"])
async def metrics_endpoint(db: AsyncSession = Depends(get_db)):
    """Prometheus metrics endpoint."""
    from app.core.metrics import metrics as metrics_collector
    from app.models import Animal, Detection, WeightMeasurement

    try:
        animals_count      = await db.scalar(select(func.count(Animal.id)))
        detections_count   = await db.scalar(select(func.count(Detection.id)))
        measurements_count = await db.scalar(select(func.count(WeightMeasurement.id)))

        metrics_collector.update_business_metrics(
            animals      = animals_count      or 0,
            detections   = detections_count   or 0,
            measurements = measurements_count or 0,
        )
    except Exception as exc:
        logger.warning(f"Could not update business metrics: {exc}")

    return Response(
        content    = metrics_collector.get_prometheus_metrics(),
        media_type = "text/plain; version=0.0.4",
    )


# =============================================================================
# LIFECYCLE EVENTS
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Application ishga tushganda bajariladigan amallar."""
    logger.info("=" * 70)
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("=" * 70)

    # 1. Environment validatsiya
    try:
        validate_environment()
        logger.info("✓ Environment validation passed")
    except RuntimeError as exc:
        logger.critical(f"❌ Startup failed: {exc}")
        import sys
        sys.exit(1)

    # 2. Tizim resurslari
    try:
        resources = check_system_resources()
        logger.info("System resources", extra={"extra_data": resources})
    except Exception as exc:
        logger.warning(f"⚠️ Could not check system resources: {exc}")

    # 3. Database
    from app.core.database import check_db_connection
    db_healthy = await check_db_connection()
    if db_healthy:
        logger.info("✓ Database connection established")
    else:
        logger.error("✗ Database connection failed!")

    # 3.5. Database Seeder
    from app.core.seeder import run_seeder
    await run_seeder()

    # 3.6. Redis Cache
    from app.core.cache import get_redis
    redis_client = await get_redis()
    if redis_client is not None:
        logger.info("✓ Redis cache connected")
    else:
        logger.warning("⚠️ Redis unavailable — caching disabled")

    # 4. WebSocket Manager
    from app.api.v1.websocket import initialize_ws_manager
    initialize_ws_manager()
    logger.info("✓ WebSocket manager initialized")

    # 5. AI Models
    from app.services.ai.yolo_service import initialize_yolo_service
    from app.services.ai.feature_extractor import initialize_feature_extractor

    try:
        await initialize_yolo_service()
        logger.info("✓ YOLO model loaded")
    except Exception as exc:
        logger.error(f"✗ YOLO model loading failed: {exc}")
        logger.warning("⚠️ Detection endpoints will not work")

    try:
        await initialize_feature_extractor()
        logger.info("✓ Feature extractor (MobileNetV2) loaded")
    except Exception as exc:
        logger.error(f"✗ Feature extractor loading failed: {exc}")
        logger.warning("⚠️ Identification endpoints will not work")

    # 6. Sprint 15-16: Frame Collector — training dataset uchun kadrlarni yig'ish
    if settings.TRAINING_COLLECTION_ENABLED:
        try:
            from app.services.ai.frame_collector import initialize_frame_collector
            import os
            os.makedirs(settings.TRAINING_FRAMES_DIR, exist_ok=True)
            initialize_frame_collector(
                save_dir        = settings.TRAINING_FRAMES_DIR,
                collect_every_n = settings.TRAINING_COLLECT_EVERY_N,
                min_detections  = settings.TRAINING_MIN_DETECTIONS,
                max_per_camera  = settings.TRAINING_MAX_PER_CAMERA,
                max_total       = settings.TRAINING_MAX_TOTAL,
                jpeg_quality    = settings.TRAINING_JPEG_QUALITY,
            )
            logger.info(
                f"✓ Frame collector initialized | "
                f"dir={settings.TRAINING_FRAMES_DIR} | "
                f"every_n={settings.TRAINING_COLLECT_EVERY_N}"
            )
        except Exception as exc:
            logger.error(f"✗ Frame collector initialization failed: {exc}")
            logger.warning("⚠️ Training data collection disabled")
    else:
        logger.info("ℹ️ Training frame collection disabled (TRAINING_COLLECTION_ENABLED=False)")

    logger.info("=" * 70)
    logger.info("✅ Application startup complete")
    logger.info(f"📡 API: http://{settings.HOST}:{settings.PORT}")
    logger.info(f"📖 Docs: http://{settings.HOST}:{settings.PORT}/docs")
    logger.info("=" * 70)


@app.on_event("shutdown")
async def shutdown_event():
    """Application to'xtatilganda resurslarni tozalash."""
    logger.info("=" * 70)
    logger.info("🛑 Shutting down application...")

    from app.services.ai.yolo_service import shutdown_yolo_service
    from app.services.ai.feature_extractor import shutdown_feature_extractor
    from app.api.v1.websocket import shutdown_ws_manager
    from app.core.database import close_db
    from app.core.cache import close_redis

    for name, coro in [
        ("YOLO model",        shutdown_yolo_service()),
        ("Feature extractor", shutdown_feature_extractor()),
        ("WebSocket manager", shutdown_ws_manager()),
        ("Redis cache",       close_redis()),
        ("Database",          close_db()),
    ]:
        try:
            await coro
            logger.info(f"✓ {name} shut down")
        except Exception as exc:
            logger.error(f"❌ {name} shutdown error: {exc}")

    logger.info("✅ Shutdown complete")
    logger.info("=" * 70)


# =============================================================================
# GLOBAL EXCEPTION HANDLER
# =============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Boshqa handler lar tutib qolmagan barcha xatolar uchun."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code = 500,
        content     = {
            "error":   "Internal Server Error",
            "message": str(exc) if settings.DEBUG else "Kutilmagan xato yuz berdi.",
        },
    )