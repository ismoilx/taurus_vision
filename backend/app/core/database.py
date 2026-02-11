# """
# Database connection and session management.

# This module handles:
# - Database engine creation with connection pooling
# - Async session management
# - Dependency injection for FastAPI routes
# """

# from typing import AsyncGenerator
# from sqlalchemy.ext.asyncio import (
#     create_async_engine,
#     AsyncSession,
#     async_sessionmaker,
# )
# from sqlalchemy.pool import NullPool, QueuePool
# import logging

# from app.config import settings

# logger = logging.getLogger(__name__)


# # Convert PostgreSQL URL to async version
# DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")


# # Create async engine with connection pooling
# engine = create_async_engine(
#     DATABASE_URL,
#     echo=settings.DEBUG,  # Log SQL queries in debug mode
#     future=True,
#     pool_pre_ping=True,  # Verify connections before using
#     pool_size=5,  # Number of connections to maintain
#     max_overflow=10,  # Additional connections when needed
#     pool_recycle=3600,  # Recycle connections after 1 hour
#     poolclass=QueuePool if "postgresql" in DATABASE_URL else NullPool,
# )


# # Create session factory
# AsyncSessionLocal = async_sessionmaker(
#     engine,
#     class_=AsyncSession,
#     expire_on_commit=False,  # Don't expire objects after commit
#     autoflush=False,  # Manual flush control
#     autocommit=False,
# )


# async def get_db() -> AsyncGenerator[AsyncSession, None]:
#     """
#     Dependency for FastAPI routes to get database session.
    
#     Usage in routes:
#         @app.get("/items")
#         async def get_items(db: AsyncSession = Depends(get_db)):
#             ...
    
#     Yields:
#         Database session
        
#     Note:
#         Automatically handles session lifecycle:
#         - Creates session
#         - Commits on success
#         - Rolls back on error
#         - Closes session
#     """
#     async with AsyncSessionLocal() as session:
#         try:
#             yield session
#             await session.commit()
#         except Exception:
#             await session.rollback()
#             raise
#         finally:
#             await session.close()


# async def init_db() -> None:
#     """
#     Initialize database.
    
#     Creates all tables defined in models.
#     Should be called on application startup.
    
#     Note:
#         In production, use Alembic migrations instead.
#         This is mainly for development/testing.
#     """
#     from app.models.base import Base
    
#     async with engine.begin() as conn:
#         logger.info("Creating database tables...")
#         await conn.run_sync(Base.metadata.create_all)
#         logger.info("Database tables created successfully")


# async def close_db() -> None:
#     """
#     Close database connections.
    
#     Should be called on application shutdown.
#     """
#     logger.info("Closing database connections...")
#     await engine.dispose()
#     logger.info("Database connections closed")


# # Health check function
# async def check_db_connection() -> bool:
#     """
#     Check if database connection is healthy.
    
#     Returns:
#         True if connection is working, False otherwise
#     """
#     try:
#         async with AsyncSessionLocal() as session:
#             await session.execute("SELECT 1")
#             return True
#     except Exception as e:
#         logger.error(f"Database health check failed: {e}")
#         return False

##############################################################
# Gemini tavfsiya qildi 10/02/2026 

# """
# Database connection and session management.

# This module handles:
# - Database engine creation with connection pooling
# - Async session management
# - Dependency injection for FastAPI routes
# """

# from typing import AsyncGenerator
# from sqlalchemy.ext.asyncio import (
#     create_async_engine,
#     AsyncSession,
#     async_sessionmaker,
# )
# from sqlalchemy.pool import NullPool, QueuePool
# from sqlalchemy import text  # <--- YANGI QO'SHILGAN IMPORT
# import logging

# from app.config import settings

# logger = logging.getLogger(__name__)


# # Convert PostgreSQL URL to async version
# DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")


# # YANGI KUCHAYTIRILGAN MOTOR (ENGINE)
# engine = create_async_engine(
#     settings.DATABASE_URL,
#     echo=False,         # Loglarni o'chiramiz (tezlik uchun)
#     pool_size=20,       # Asosiy hovuz: 20 ta ulanish
#     max_overflow=40,    # Zaxira hovuz: 40 ta ulanish (Jami 60 ta)
#     pool_timeout=30,    # Navbatda 30 sekund kutish mumkin
#     pool_recycle=1800,  # Har yarim soatda ulanishlarni yangilash
# )


# # Create session factory
# AsyncSessionLocal = async_sessionmaker(
#     engine,
#     class_=AsyncSession,
#     expire_on_commit=False,  # Don't expire objects after commit
#     autoflush=False,  # Manual flush control
#     autocommit=False,
# )


# async def get_db() -> AsyncGenerator[AsyncSession, None]:
#     """
#     Dependency for FastAPI routes to get database session.
#     """
#     async with AsyncSessionLocal() as session:
#         try:
#             yield session
#             await session.commit()
#         except Exception:
#             await session.rollback()
#             raise
#         finally:
#             await session.close()


# async def init_db() -> None:
#     """Initialize database tables (Dev only)."""
#     from app.models.base import Base
    
#     async with engine.begin() as conn:
#         logger.info("Creating database tables...")
#         await conn.run_sync(Base.metadata.create_all)
#         logger.info("Database tables created successfully")


# async def close_db() -> None:
#     """Close database connections."""
#     logger.info("Closing database connections...")
#     await engine.dispose()
#     logger.info("Database connections closed")


# # Health check function
# async def check_db_connection() -> bool:
#     """
#     Check if database connection is healthy.
    
#     Returns:
#         True if connection is working, False otherwise
#     """
#     try:
#         async with AsyncSessionLocal() as session:
#             # O'ZGARISH SHU YERDA: oddiy string emas, text() ishlatildi
#             await session.execute(text("SELECT 1"))
#             return True
#     except Exception as e:
#         logger.error(f"Database health check failed: {e}")
#         return False

##############################################################
"""
Database connection and session management.

This module handles:
- Database engine creation with connection pooling
- Async session management
- Dependency injection for FastAPI routes
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy import text
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# 1. URLni TO'G'IRLASH (CRITICAL FIX)
# -------------------------------------------------------------------
# SQLAlchemy Async ishlashi uchun drayver nomi "postgresql+asyncpg" bo'lishi SHART.
# Agar .env faylda oddiy "postgresql://" bo'lsa, biz uni shu yerda to'g'irlaymiz.

DB_URL = str(settings.DATABASE_URL)
if DB_URL.startswith("postgresql://"):
    DB_URL = DB_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# -------------------------------------------------------------------
# 2. KUCHAYTIRILGAN MOTOR (ENGINE)
# -------------------------------------------------------------------
engine = create_async_engine(
    DB_URL,  # <--- DIQQAT: Bu yerda to'g'irlangan DB_URL ishlatilishi shart!
    echo=False,          # Loglarni o'chiramiz (Tezlik uchun)
    pool_size=20,        # Asosiy hovuz: 20 ta doimiy ulanish
    max_overflow=40,     # Zaxira hovuz: Yuklama oshganda yana 40 ta ochadi
    pool_timeout=30,     # Bo'sh joy chiqishini 30 sekund kutadi
    pool_recycle=1800,   # Har 30 daqiqada ulanishni yangilaydi (uzilib qolmasligi uchun)
    pool_pre_ping=True,  # Har safar so'rovdan oldin "Aloqa bormi?" deb tekshiradi
)

# -------------------------------------------------------------------
# 3. SESSIYA FABRIKASI (SESSION FACTORY)
# -------------------------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False, # Commit qilgandan keyin obyektlar xotirada tursin
    autoflush=False,
    autocommit=False,
)


# -------------------------------------------------------------------
# 4. FASTAPI UCHUN DEPENDENCY
# -------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI routes to get database session.
    Har bir so'rov uchun yangi sessiya ochadi va ish bitgach yopadi.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # 🔥 ENG MUHIM QATOR: Ish bitgach, bazaga "Muhr bosamiz" (Save)
            await session.commit()
        except Exception:
            # Agar xato chiqsa, orqaga qaytaradi (Rollback)
            await session.rollback()
            raise
        finally:
            # Har qanday holatda ham sessiyani yopish shart
            await session.close()


# -------------------------------------------------------------------
# 5. YORDAMCHI FUNKSIYALAR
# -------------------------------------------------------------------

async def check_db_connection() -> bool:
    """
    Database bilan aloqa borligini tekshirish (Health Check).
    """
    try:
        async with AsyncSessionLocal() as session:
            # Oddiy SQL so'rov yuborib ko'ramiz
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False

async def close_db() -> None:
    """
    Dastur o'chayotganda barcha ulanishlarni uzish.
    """
    logger.info("Closing database connections...")
    await engine.dispose()
    logger.info("Database connections closed.")