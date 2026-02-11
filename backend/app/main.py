# # """
# # Taurus Vision - Main FastAPI Application

# # This is the entry point for the backend API server.
# # It initializes FastAPI, configures middleware, and includes API routes.
# # """

# # from fastapi import FastAPI
# # from fastapi.middleware.cors import CORSMiddleware
# # from fastapi.responses import JSONResponse
# # import logging
# # from datetime import datetime

# # from app.config import settings

# # # Configure logging
# # logging.basicConfig(
# #     level=settings.LOG_LEVEL,
# #     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
# # )
# # logger = logging.getLogger(__name__)


# # # Create FastAPI application
# # app = FastAPI(
# #     title=settings.APP_NAME,
# #     version=settings.APP_VERSION,
# #     description="Farm animal monitoring and management system",
# #     debug=settings.DEBUG,
# # )


# # # CORS middleware (frontend bilan aloqa uchun)
# # app.add_middleware(
# #     CORSMiddleware,
# #     allow_origins=settings.CORS_ORIGINS,
# #     allow_credentials=True,
# #     allow_methods=["*"],
# #     allow_headers=["*"],
# # )


# # # Health check endpoint
# # @app.get("/")
# # async def root():
# #     """
# #     Root endpoint - API health check.
    
# #     Returns:
# #         Basic API information and status
# #     """
# #     return {
# #         "name": settings.APP_NAME,
# #         "version": settings.APP_VERSION,
# #         "status": "running",
# #         "timestamp": datetime.utcnow().isoformat(),
# #     }


# # @app.get("/health")
# # async def health_check():
# #     """
# #     Health check endpoint for monitoring.
    
# #     Returns:
# #         System health status
# #     """
# #     return {
# #         "status": "healthy",
# #         "timestamp": datetime.utcnow().isoformat(),
# #     }


# # # Startup event
# # @app.on_event("startup")
# # async def startup_event():
# #     """
# #     Execute on application startup.
    
# #     Initialize database connections, load ML models, etc.
# #     """
# #     from app.core.database import check_db_connection
    
# #     logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
# #     logger.info(f"Debug mode: {settings.DEBUG}")
    
# #     # Check database connection
# #     db_healthy = await check_db_connection()
# #     if db_healthy:
# #         logger.info("✓ Database connection established")
# #     else:
# #         logger.error("✗ Database connection failed!")
    
# #     # TODO: Load ML models


# # # Shutdown event
# # @app.on_event("shutdown")
# # async def shutdown_event():
# #     """
# #     Execute on application shutdown.
    
# #     Clean up resources, close connections, etc.
# #     """
# #     from app.core.database import close_db
    
# #     logger.info("Shutting down application...")
# #     await close_db()
# #     logger.info("✓ Database connections closed")
# #     # TODO: Cleanup resources


# # # Exception handler
# # @app.exception_handler(Exception)
# # async def global_exception_handler(request, exc):
# #     """
# #     Global exception handler.
    
# #     Catches all unhandled exceptions and returns proper error response.
# #     """
# #     logger.error(f"Unhandled exception: {exc}", exc_info=True)
# #     return JSONResponse(
# #         status_code=500,
# #         content={
# #             "error": "Internal server error",
# #             "message": str(exc) if settings.DEBUG else "An error occurred",
# #         },
# #     )


# # if __name__ == "__main__":
# #     import uvicorn
    
# #     uvicorn.run(
# #         "app.main:app",
# #         host=settings.HOST,
# #         port=settings.PORT,
# #         reload=settings.DEBUG,  # Auto-reload in development
# #         log_level=settings.LOG_LEVEL.lower(),
# #     )
# ####################################################################
# # To'liq o'zgartirish kiritildi 10/02/2026
# # """
# # Taurus Vision - Main FastAPI Application

# # This is the entry point for the backend API server.
# # It initializes FastAPI, configures middleware, and includes API routes.
# # """

# # from fastapi import FastAPI
# # from fastapi.middleware.cors import CORSMiddleware
# # from fastapi.responses import JSONResponse
# # import logging
# # from datetime import datetime

# # from app.config import settings
# # from app.api.v1 import router as api_v1_router
# # from app.api.v1.exception_handlers import (
# #     entity_not_found_handler,
# #     entity_already_exists_handler,
# #     business_rule_violation_handler,
# #     validation_error_handler,
# #     database_error_handler,
# # )
# # from app.core.exceptions import (
# #     EntityNotFoundError,
# #     EntityAlreadyExistsError,
# #     BusinessRuleViolationError,
# #     ValidationError,
# #     DatabaseError,
# # )

# # # Configure logging
# # logging.basicConfig(
# #     level=settings.LOG_LEVEL,
# #     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
# # )
# # logger = logging.getLogger(__name__)


# # # Create FastAPI application
# # app = FastAPI(
# #     title=settings.APP_NAME,
# #     version=settings.APP_VERSION,
# #     description="Farm animal monitoring and management system with AI-powered detection",
# #     debug=settings.DEBUG,
# #     docs_url="/docs",  # Swagger UI
# #     redoc_url="/redoc",  # ReDoc
# # )


# # # CORS middleware (frontend bilan aloqa uchun)
# # app.add_middleware(
# #     CORSMiddleware,
# #     allow_origins=settings.CORS_ORIGINS,
# #     allow_credentials=True,
# #     allow_methods=["*"],
# #     allow_headers=["*"],
# # )


# # # Include API routers
# # app.include_router(api_v1_router, prefix="/api")


# # # Register exception handlers
# # app.add_exception_handler(EntityNotFoundError, entity_not_found_handler)
# # app.add_exception_handler(EntityAlreadyExistsError, entity_already_exists_handler)
# # app.add_exception_handler(BusinessRuleViolationError, business_rule_violation_handler)
# # app.add_exception_handler(ValidationError, validation_error_handler)
# # app.add_exception_handler(DatabaseError, database_error_handler)


# # # Health check endpoint
# # @app.get("/")
# # async def root():
# #     """
# #     Root endpoint - API health check.
    
# #     Returns:
# #         Basic API information and status
# #     """
# #     return {
# #         "name": settings.APP_NAME,
# #         "version": settings.APP_VERSION,
# #         "status": "running",
# #         "timestamp": datetime.utcnow().isoformat(),
# #         "docs": "/docs",
# #         "api": "/api/v1",
# #     }


# # @app.get("/health")
# # async def health_check():
# #     """
# #     Health check endpoint for monitoring.
    
# #     Returns:
# #         System health status including database connection
# #     """
# #     from app.core.database import check_db_connection
    
# #     db_healthy = await check_db_connection()
    
# #     return {
# #         "status": "healthy" if db_healthy else "degraded",
# #         "database": "connected" if db_healthy else "disconnected",
# #         "timestamp": datetime.utcnow().isoformat(),
# #     }


# # # Startup event
# # @app.on_event("startup")
# # async def startup_event():
# #     """
# #     Execute on application startup.
    
# #     Initialize database connections, load ML models, etc.
# #     """
# #     from app.core.database import check_db_connection
    
# #     logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
# #     logger.info(f"Debug mode: {settings.DEBUG}")
    
# #     # Check database connection
# #     db_healthy = await check_db_connection()
# #     if db_healthy:
# #         logger.info("✓ Database connection established")
# #     else:
# #         logger.error("✗ Database connection failed!")
    
# #     logger.info("✓ Application startup complete")
# #     # TODO: Load ML models


# # # Shutdown event
# # @app.on_event("shutdown")
# # async def shutdown_event():
# #     """
# #     Execute on application shutdown.
    
# #     Clean up resources, close connections, etc.
# #     """
# #     from app.core.database import close_db
    
# #     logger.info("Shutting down application...")
# #     await close_db()
# #     logger.info("✓ Database connections closed")
# #     logger.info("✓ Application shutdown complete")


# # # Global exception handler (catch-all)
# # @app.exception_handler(Exception)
# # async def global_exception_handler(request, exc):
# #     """
# #     Global exception handler for unexpected errors.
    
# #     Catches all unhandled exceptions and returns proper error response.
# #     """
# #     logger.error(f"Unhandled exception: {exc}", exc_info=True)
# #     return JSONResponse(
# #         status_code=500,
# #         content={
# #             "error": "Internal Server Error",
# #             "message": str(exc) if settings.DEBUG else "An unexpected error occurred",
# #         },
# #     )


# # if __name__ == "__main__":
# #     import uvicorn
    
# #     uvicorn.run(
# #         "app.main:app",
# #         host=settings.HOST,
# #         port=settings.PORT,
# #         reload=settings.DEBUG,  # Auto-reload in development
# #         log_level=settings.LOG_LEVEL.lower(),
# #     )
# #########################################################################################
# # To'liq o'zgartirish kiritildi 10/02/2026
# """
# Taurus Vision - Main FastAPI Application

# This is the entry point for the backend API server.
# It initializes FastAPI, configures middleware, and includes API routes.
# """

# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# import logging
# from datetime import datetime

# # Settings va Routerlarni import qilish
# try:
#     from app.config import settings
# except ImportError:
#     from app.core.config import settings

# from app.api.v1 import router as api_v1_router
# from app.api.v1.exception_handlers import (
#     entity_not_found_handler,
#     entity_already_exists_handler,
#     business_rule_violation_handler,
#     validation_error_handler,
#     database_error_handler,
# )
# from app.core.exceptions import (
#     EntityNotFoundError,
#     EntityAlreadyExistsError,
#     BusinessRuleViolationError,
#     ValidationError,
#     DatabaseError,
# )

# # Logging sozlamalari
# logging.basicConfig(
#     level=settings.LOG_LEVEL,
#     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
# )
# logger = logging.getLogger(__name__)

# # FastAPI ilovasini yaratish
# app = FastAPI(
#     title=settings.APP_NAME,
#     version=settings.APP_VERSION,
#     description="Farm animal monitoring and management system with AI-powered detection",
#     debug=settings.DEBUG,
#     docs_url="/docs",
#     redoc_url="/redoc",
# )

# # --- 1. CORS VA XAVFSIZLIK SOZLAMALARI (Senior darajada) ---
# # allow_credentials=True bo'lganda origins ["*"] bo'lishi mumkin emas.
# origins = [
#     "http://localhost:5173",    # Vite default port
#     "http://127.0.0.1:5173",
#     "http://localhost:8000",    # Backend o'z-o'ziga
#     "http://0.0.0.0:5173",
# ]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # --- 2. API ROUTERLARINI ULASH ---
# # Claude'ning tuzilmasini saqlab qolamiz
# app.include_router(api_v1_router, prefix="/api")

# # --- 3. EXCEPTION HANDLERLAR ---
# app.add_exception_handler(EntityNotFoundError, entity_not_found_handler)
# app.add_exception_handler(EntityAlreadyExistsError, entity_already_exists_handler)
# app.add_exception_handler(BusinessRuleViolationError, business_rule_violation_handler)
# app.add_exception_handler(ValidationError, validation_error_handler)
# app.add_exception_handler(DatabaseError, database_error_handler)

# # --- 4. ENDPOINTLAR (Root va Health Check) ---
# @app.get("/")
# async def root():
#     return {
#         "name": settings.APP_NAME,
#         "version": settings.APP_VERSION,
#         "status": "running",
#         "timestamp": datetime.utcnow().isoformat(),
#     }

# @app.get("/health")
# async def health_check():
#     from app.core.database import check_db_connection
#     db_healthy = await check_db_connection()
#     return {
#         "status": "healthy" if db_healthy else "degraded",
#         "database": "connected" if db_healthy else "disconnected",
#         "timestamp": datetime.utcnow().isoformat(),
#     }

# # --- 5. STARTUP VA SHUTDOWN (Birlashtirilgan va tozalangan) ---
# @app.on_event("startup")
# async def startup_event():
#     logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
#     try:
#         from app.core.database import check_db_connection
#         from app.api.v1.websocket import initialize_ws_manager
        
#         # Baza bilan aloqani tekshirish
#         db_healthy = await check_db_connection()
#         if db_healthy:
#             logger.info("✓ Database connection established")
        
#         # WebSocketni to'g'ri nom bilan ishga tushirish
#         initialize_ws_manager()
#         logger.info("✓ WebSocket manager initialized")
        
#     except Exception as e:
#         logger.error(f"❌ Startup error: {e}")

# @app.on_event("shutdown")
# async def shutdown_event():
#     logger.info("🛑 Shutting down application...")
#     try:
#         from app.core.database import close_db
#         from app.api.v1.websocket import shutdown_ws_manager
        
#         await shutdown_ws_manager()
#         await close_db()
#         logger.info("✓ Cleanup complete")
#     except Exception as e:
#         logger.error(f"❌ Shutdown error: {e}")

# # Global xatolik ushlagichi
# @app.exception_handler(Exception)
# async def global_exception_handler(request, exc):
#     logger.error(f"Unhandled exception: {exc}", exc_info=True)
#     return JSONResponse(
#         status_code=500,
#         content={"error": "Internal Server Error", "message": str(exc) if settings.DEBUG else "Error occurred"},
#     )

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(
#         "app.main:app",
#         host=settings.HOST,
#         port=settings.PORT,
#         reload=settings.DEBUG,
#         log_level=settings.LOG_LEVEL.lower(),
#     )


























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

# Settings va Routerlarni import qilish
try:
    from app.config import settings
except ImportError:
    from app.core.config import settings

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

# Logging sozlamalari
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# FastAPI ilovasini yaratish
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Farm animal monitoring and management system with AI-powered detection",
    debug=settings.DEBUG,
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- 1. CORS VA XAVFSIZLIK SOZLAMALARI (Senior darajada) ---
# allow_credentials=True bo'lganda origins ["*"] bo'lishi mumkin emas.
origins = [
    "http://localhost:5173",    # Vite default port
    "http://127.0.0.1:5173",
    "http://localhost:8000",    # Backend o'z-o'ziga
    "http://0.0.0.0:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. API ROUTERLARINI ULASH ---
# Claude'ning tuzilmasini saqlab qolamiz
app.include_router(api_v1_router, prefix="/api")

# --- 3. EXCEPTION HANDLERLAR ---
app.add_exception_handler(EntityNotFoundError, entity_not_found_handler)
app.add_exception_handler(EntityAlreadyExistsError, entity_already_exists_handler)
app.add_exception_handler(BusinessRuleViolationError, business_rule_violation_handler)
app.add_exception_handler(ValidationError, validation_error_handler)
app.add_exception_handler(DatabaseError, database_error_handler)

# --- 4. ENDPOINTLAR (Root va Health Check) ---
@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
    }

@app.get("/health")
async def health_check():
    from app.core.database import check_db_connection
    db_healthy = await check_db_connection()
    return {
        "status": "healthy" if db_healthy else "degraded",
        "database": "connected" if db_healthy else "disconnected",
        "timestamp": datetime.utcnow().isoformat(),
    }

# --- 5. STARTUP VA SHUTDOWN (Birlashtirilgan va tozalangan) ---
@app.on_event("startup")
async def startup_event():
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    try:
        from app.core.database import check_db_connection
        from app.api.v1.websocket import initialize_ws_manager
        
        # Baza bilan aloqani tekshirish
        db_healthy = await check_db_connection()
        if db_healthy:
            logger.info("✓ Database connection established")
        
        # WebSocketni to'g'ri nom bilan ishga tushirish
        initialize_ws_manager()
        logger.info("✓ WebSocket manager initialized")
        
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Shutting down application...")
    try:
        from app.core.database import close_db
        from app.api.v1.websocket import shutdown_ws_manager
        
        await shutdown_ws_manager()
        await close_db()
        logger.info("✓ Cleanup complete")
    except Exception as e:
        logger.error(f"❌ Shutdown error: {e}")

# Global xatolik ushlagichi
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "message": str(exc) if settings.DEBUG else "Error occurred"},
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )