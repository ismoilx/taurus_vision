"""
Taurus Vision - Main FastAPI Application

This is the entry point for the backend API server.
It initializes FastAPI, configures middleware, and includes API routes.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from datetime import datetime

from app.config import settings

# Configure logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Farm animal monitoring and management system",
    debug=settings.DEBUG,
)


# CORS middleware (frontend bilan aloqa uchun)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/")
async def root():
    """
    Root endpoint - API health check.
    
    Returns:
        Basic API information and status
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    
    Returns:
        System health status
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    """
    Execute on application startup.
    
    Initialize database connections, load ML models, etc.
    """
    from app.core.database import check_db_connection
    
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    
    # Check database connection
    db_healthy = await check_db_connection()
    if db_healthy:
        logger.info("✓ Database connection established")
    else:
        logger.error("✗ Database connection failed!")
    
    # TODO: Load ML models


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """
    Execute on application shutdown.
    
    Clean up resources, close connections, etc.
    """
    from app.core.database import close_db
    
    logger.info("Shutting down application...")
    await close_db()
    logger.info("✓ Database connections closed")
    # TODO: Cleanup resources


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler.
    
    Catches all unhandled exceptions and returns proper error response.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.DEBUG else "An error occurred",
        },
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,  # Auto-reload in development
        log_level=settings.LOG_LEVEL.lower(),
    )