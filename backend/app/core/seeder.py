"""
Taurus Vision — Database Seeder

Tizim birinchi marta ishga tushganda zarur boshlang'ich ma'lumotlarni yaratadi.

VAZIFA:
    - Agar `users` jadvali bo'sh bo'lsa va environment da
      INITIAL_ADMIN_EMAIL / INITIAL_ADMIN_PASSWORD belgilangan bo'lsa,
      birinchi ADMIN foydalanuvchini avtomatik yaratadi.
    - Ikkinchi marta ishga tushganda hech narsa qilmaydi (idempotent).

FOYDALANISH:
    main.py startup_event ichida chaqiriladi:
        from app.core.seeder import run_seeder
        await run_seeder()

ENVIRONMENT VARIABLES:
    INITIAL_ADMIN_EMAIL    — Admin email (masalan: admin@taurus.uz)
    INITIAL_ADMIN_USERNAME — Admin username (default: admin)
    INITIAL_ADMIN_PASSWORD — Admin paroli (kamida 8 belgi, 1 katta harf, 1 raqam)
    INITIAL_ADMIN_FULLNAME — Admin to'liq ismi (ixtiyoriy)
"""

import os
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


async def _create_initial_admin(db: AsyncSession) -> None:
    """
    Birinchi ADMIN foydalanuvchini yaratadi.

    Faqat:
      1. Environment da INITIAL_ADMIN_EMAIL va INITIAL_ADMIN_PASSWORD bor bo'lsa
      2. `users` jadvali bo'sh bo'lsa (hech qanday foydalanuvchi yo'q)

    Args:
        db: Async database session

    Returns:
        None
    """
    email    = os.getenv("INITIAL_ADMIN_EMAIL", "").strip()
    password = os.getenv("INITIAL_ADMIN_PASSWORD", "").strip()
    username = os.getenv("INITIAL_ADMIN_USERNAME", "admin").strip()
    fullname = os.getenv("INITIAL_ADMIN_FULLNAME", "System Administrator").strip()

    # Environment da belgilanmagan bo'lsa — o'tkazib yuboramiz
    if not email or not password:
        logger.info(
            "⏭️  Seeder: INITIAL_ADMIN_EMAIL yoki INITIAL_ADMIN_PASSWORD "
            "belgilanmagan — admin yaratilmadi."
        )
        return

    # Parol minimal talablarini tekshirish
    if len(password) < 8:
        logger.error(
            "❌ Seeder: INITIAL_ADMIN_PASSWORD kamida 8 belgidan iborat bo'lishi kerak!"
        )
        return

    # Jadvalda foydalanuvchi bormi tekshirish
    count_result = await db.execute(select(func.count(User.id)))
    user_count   = count_result.scalar_one()

    if user_count > 0:
        logger.info(
            f"⏭️  Seeder: Allaqachon {user_count} ta foydalanuvchi mavjud — "
            "admin yaratilmadi."
        )
        return

    # Email allaqachon band emasligini tekshirish (ehtiyot uchun)
    existing = await db.execute(
        select(User).where(User.email == email.lower())
    )
    if existing.scalar_one_or_none():
        logger.warning(
            f"⚠️  Seeder: {email} email bilan foydalanuvchi allaqachon mavjud."
        )
        return

    # Admin yaratish
    admin = User(
        email           = email.lower(),
        username        = username.lower(),
        full_name       = fullname,
        hashed_password = hash_password(password),
        role            = UserRole.ADMIN,
        is_active       = True,
    )

    db.add(admin)
    await db.flush()
    await db.refresh(admin)
    await db.commit()

    logger.info("=" * 60)
    logger.info("✅ Seeder: Birinchi ADMIN foydalanuvchi yaratildi!")
    logger.info(f"   📧 Email:    {admin.email}")
    logger.info(f"   👤 Username: {admin.username}")
    logger.info(f"   🔑 Role:     {admin.role.value}")
    logger.info(f"   🆔 ID:       {admin.id}")
    logger.info("=" * 60)


async def run_seeder() -> None:
    """
    Seeder ni ishga tushiradi.

    Alohida DB session yaratadi — main.py startup_event dan mustaqil.
    Xato bo'lsa log yozadi, lekin applicationni to'xtatmaydi.

    Returns:
        None
    """
    logger.info("🌱 Seeder ishga tushmoqda...")

    try:
        async with AsyncSessionLocal() as db:
            await _create_initial_admin(db)
    except Exception as exc:
        # Seeder xatosi applicationni to'xtatmasligi kerak
        logger.error(
            f"❌ Seeder xatosi: {exc}",
            exc_info=True,
        )

    logger.info("🌱 Seeder tugadi.")