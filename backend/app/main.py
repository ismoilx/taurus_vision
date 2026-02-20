"""
Taurus Vision - Main FastAPI Application

This is the entry point for the backend API server.
It initializes FastAPI, configures middleware, and includes API routes.
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
    RateLimitMiddleware,          # Sprint 6: Rate limiting
)
from app.core.validators import validate_environment, check_system_resources
from app.core.database import get_db

from app.api.v1 import router as api_v1_router
from app.api.v1.exception_handlers import (
    entity_not_found_handler,
    entity_already_exists_handler,
    business_rule_violation_handler,
    validation_error_handler,
    database_error_handler,
)
from app.core.exceptions import (
    EntityNotFoundError,
    EntityAlreadyExistsError,
    BusinessRuleViolationError,
    ValidationError,
    DatabaseError,
)

# Initialize logging (call once at module level)
setup_logging()
logger = get_logger(__name__)


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Farm animal monitoring and management system with AI-powered detection",
    debug=settings.DEBUG,
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
)


# ============================================================================
# MIDDLEWARE CONFIGURATION
# Order matters! Applied in reverse order (bottom to top during request)
# ============================================================================

# CORS middleware (frontend bilan aloqa uchun)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers (Production-ready security)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, enabled=not settings.DEBUG)  # Sprint 6

# Request logging and performance monitoring
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(PerformanceMonitoringMiddleware)


# ============================================================================
# API ROUTERS
# ============================================================================

# Include API routers
app.include_router(api_v1_router, prefix="/api")


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

# Register custom exception handlers
app.add_exception_handler(EntityNotFoundError, entity_not_found_handler)
app.add_exception_handler(EntityAlreadyExistsError, entity_already_exists_handler)
app.add_exception_handler(BusinessRuleViolationError, business_rule_violation_handler)
app.add_exception_handler(ValidationError, validation_error_handler)
app.add_exception_handler(DatabaseError, database_error_handler)


# ============================================================================
# CORE ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """
    Root endpoint - API information.
    
    Returns:
        Basic API information and available endpoints
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "docs": "/docs",
        "api": "/api/v1",
        "health": "/health",
        "metrics": "/metrics",
    }


# ============================================================================
# HEALTH CHECK ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Comprehensive health check endpoint.
    
    Returns detailed health status for all system components.
    Used by monitoring tools, load balancers, and orchestrators.
    
    Returns:
        Complete health report with status of all subsystems
    """
    from app.core.health import health_checker
    
    health_report = await health_checker.check_all(db)
    
    # Set appropriate HTTP status code
    status_code = 200
    if health_report["status"] == "unhealthy":
        status_code = 503  # Service Unavailable
    elif health_report["status"] == "degraded":
        status_code = 200  # Still accepting requests
    
    return JSONResponse(
        status_code=status_code,
        content=health_report
    )


@app.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """
    Kubernetes readiness probe.
    
    Returns 200 if application is ready to serve requests.
    Returns 503 if not ready (still starting up or unhealthy).
    """
    from app.core.health import health_checker
    
    health_report = await health_checker.check_all(db)
    
    if health_report["status"] in ["healthy", "degraded"]:
        return {"status": "ready"}
    else:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "System unhealthy"}
        )


@app.get("/health/live")
async def liveness_check():
    """
    Kubernetes liveness probe.
    
    Returns 200 if application is alive (even if not fully functional).
    Returns 503 only if application should be restarted.
    """
    return {"status": "alive"}


# ============================================================================
# MONITORING ENDPOINTS
# ============================================================================

@app.get("/metrics")
async def metrics_endpoint(db: AsyncSession = Depends(get_db)):
    """
    Prometheus metrics endpoint.
    
    Returns application metrics in Prometheus format.
    Used by Prometheus scraper for monitoring.
    
    Returns:
        Metrics in Prometheus exposition format
    """
    from app.core.metrics import metrics as metrics_collector
    from app.models import Animal, Detection, WeightMeasurement
    
    # Update business metrics from database
    try:
        animals_count = await db.scalar(select(func.count(Animal.id)))
        detections_count = await db.scalar(select(func.count(Detection.id)))
        measurements_count = await db.scalar(select(func.count(WeightMeasurement.id)))
        
        metrics_collector.update_business_metrics(
            animals=animals_count or 0,
            detections=detections_count or 0,
            measurements=measurements_count or 0,
        )
    except Exception as e:
        logger.warning(f"Could not update business metrics: {e}")
    
    # Generate Prometheus format
    prometheus_metrics = metrics_collector.get_prometheus_metrics()
    
    return Response(
        content=prometheus_metrics,
        media_type="text/plain; version=0.0.4",
    )


# ============================================================================
# LIFECYCLE EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    Execute on application startup.
    
    Validates environment, initializes services, and loads ML models.
    """
    logger.info("=" * 70)
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("=" * 70)
    
    # ===== STEP 1: Environment Validation =====
    try:
        validate_environment()
        logger.info("✓ Environment validation passed")
    except RuntimeError as e:
        logger.critical(f"❌ Startup failed: {e}")
        import sys
        sys.exit(1)
    
    # ===== STEP 2: System Resources Check =====
    try:
        resources = check_system_resources()
        logger.info(
            "System resources",
            extra={
                "extra_data": {
                    "cpu_percent": resources["cpu_percent"],
                    "memory_percent": resources["memory_percent"],
                    "disk_percent": resources["disk_percent"],
                    "cpu_count": resources["cpu_count"],
                    "memory_total_gb": resources["memory_total_gb"],
                }
            }
        )
    except Exception as e:
        logger.warning(f"⚠️ Could not check system resources: {e}")
    
    # ===== STEP 3: Database Connection =====
    from app.core.database import check_db_connection
    
    logger.info(f"Debug mode: {settings.DEBUG}")
    
    db_healthy = await check_db_connection()
    if db_healthy:
        logger.info("✓ Database connection established")
    else:
        logger.error("✗ Database connection failed!")
    
    # ===== STEP 4: WebSocket Manager =====
    from app.api.v1.websocket import initialize_ws_manager
    
    initialize_ws_manager()
    logger.info("✓ WebSocket manager initialized")
    
    # ===== STEP 5: AI Models =====
    from app.services.ai.yolo_service import initialize_yolo_service
    from app.services.ai.feature_extractor import initialize_feature_extractor
    
    try:
        await initialize_yolo_service()
        logger.info("✓ YOLO model loaded successfully")
    except Exception as e:
        logger.error(f"✗ YOLO model loading failed: {e}")
        logger.warning("⚠️ Detection endpoints will not work")

    try:
        await initialize_feature_extractor()
        logger.info("✓ Feature extractor (MobileNetV2) loaded successfully")
    except Exception as e:
        logger.error(f"✗ Feature extractor loading failed: {e}")
        logger.warning("⚠️ Identification endpoints will not work")
    
    # ===== STARTUP COMPLETE =====
    logger.info("=" * 70)
    logger.info("✅ Application startup complete")
    logger.info(f"📡 API available at: http://{settings.HOST}:{settings.PORT}")
    logger.info(f"📖 Documentation: http://{settings.HOST}:{settings.PORT}/docs")
    logger.info("=" * 70)


@app.on_event("shutdown")
async def shutdown_event():
    """
    Execute on application shutdown.
    
    Clean up resources, close connections, etc.
    """
    logger.info("=" * 70)
    logger.info("🛑 Shutting down application...")
    logger.info("=" * 70)
    
    # ===== STEP 1: Shutdown AI models =====
    from app.services.ai.yolo_service import shutdown_yolo_service
    from app.services.ai.feature_extractor import shutdown_feature_extractor
    
    try:
        await shutdown_yolo_service()
        logger.info("✓ YOLO model unloaded")
    except Exception as e:
        logger.error(f"❌ Error unloading YOLO model: {e}")

    try:
        await shutdown_feature_extractor()
        logger.info("✓ Feature extractor unloaded")
    except Exception as e:
        logger.error(f"❌ Error unloading feature extractor: {e}")
    
    # ===== STEP 2: Shutdown WebSocket connections =====
    from app.api.v1.websocket import shutdown_ws_manager
    
    try:
        await shutdown_ws_manager()
        logger.info("✓ WebSocket connections closed")
    except Exception as e:
        logger.error(f"❌ Error closing WebSocket connections: {e}")
    
    # ===== STEP 3: Close database =====
    from app.core.database import close_db
    
    try:
        await close_db()
        logger.info("✓ Database connections closed")
    except Exception as e:
        logger.error(f"❌ Error closing database: {e}")
    
    # ===== SHUTDOWN COMPLETE =====
    logger.info("=" * 70)
    logger.info("✅ Application shutdown complete")
    logger.info("=" * 70)


# ============================================================================
# GLOBAL EXCEPTION HANDLER
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler for unexpected errors.
    
    Catches all unhandled exceptions and returns proper error response.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc) if settings.DEBUG else "An unexpected error occurred",
        },
    )


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,  # Auto-reload in development
        log_level=settings.LOG_LEVEL.lower(),
    )