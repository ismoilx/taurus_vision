"""
Taurus Vision — Boshlang'ich Admin Foydalanuvchi Yaratish

Ishlatish (Docker ichidan):
    docker exec taurus-backend python scripts/create_admin.py

Yoki parametrlar bilan:
    docker exec taurus-backend python scripts/create_admin.py \
        --email admin@farm.com \
        --username admin \
        --password MySecurePass123 \
        --fullname "Farm Admin"

Nima qiladi:
    - Berilgan ma'lumotlar bilan ADMIN roli foydalanuvchi yaratadi
    - Agar shu email/username mavjud bo'lsa — ogohlantirib to'xtatadi
    - Muvaffaqiyatli bo'lsa login qilish uchun ma'lumotlarni ko'rsatadi
"""

import asyncio
import argparse
import sys
import os

# Docker ichida /app, lokal ishlatishda backend/ papkasidan
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole


# =============================================================================
# DEFAULT QIYMATLAR
# =============================================================================

DEFAULT_EMAIL    = "admin@taurus.local"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "Admin1234!"
DEFAULT_FULLNAME = "System Administrator"


# =============================================================================
# ASOSIY FUNKSIYA
# =============================================================================

async def create_admin(
    email: str,
    username: str,
    password: str,
    full_name: str,
) -> None:
    """
    Admin foydalanuvchini yaratish.

    Args:
        email:     Admin email manzili
        username:  Login uchun foydalanuvchi nomi
        password:  Parol (kamida 8 belgi)
        full_name: To'liq ismi (ko'rsatish uchun)

    Raises:
        SystemExit: Email yoki username allaqachon mavjud bo'lsa
    """
    print("=" * 60)
    print("  🐮 TAURUS VISION — ADMIN YARATISH")
    print("=" * 60)

    if len(password) < 8:
        print("❌ Xato: Parol kamida 8 belgi bo'lishi kerak.")
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        # Email tekshiruvi
        existing_email = await db.scalar(
            select(User).where(User.email == email)
        )
        if existing_email:
            print(f"⚠️  Bu email allaqachon mavjud: {email}")
            print("   Mavjud foydalanuvchi bilan login qiling yoki boshqa email ishlating.")
            sys.exit(1)

        # Username tekshiruvi
        existing_username = await db.scalar(
            select(User).where(User.username == username)
        )
        if existing_username:
            print(f"⚠️  Bu username allaqachon band: {username}")
            print("   Boshqa username ishlating.")
            sys.exit(1)

        # Admin yaratish
        admin_user = User(
            email=email,
            username=username,
            full_name=full_name,
            hashed_password=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )

        db.add(admin_user)
        await db.commit()
        await db.refresh(admin_user)

    # Muvaffaqiyat xabari
    print("\n✅ Admin foydalanuvchi muvaffaqiyatli yaratildi!\n")
    print("  📋 Login ma'lumotlari:")
    print(f"     Email:    {email}")
    print(f"     Username: {username}")
    print(f"     Parol:    {password}")
    print(f"     Rol:      ADMIN")
    print(f"     ID:       {admin_user.id}")
    print()
    print("  🌐 Tizimga kirish:")
    print("     http://localhost:5173  — Frontend")
    print("     http://localhost:8000/docs  — Swagger UI")
    print()
    print("  ⚠️  MUHIM: Parolni xavfsiz joyda saqlang!")
    print("=" * 60)


# =============================================================================
# ENTRY POINT
# =============================================================================

def main() -> None:
    """Argument parser va async runner."""
    parser = argparse.ArgumentParser(
        description="Taurus Vision — Boshlang'ich admin foydalanuvchi yaratish",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Misol:
  docker exec taurus-backend python scripts/create_admin.py
  docker exec taurus-backend python scripts/create_admin.py --email farm@example.com --password Secure123!
        """,
    )
    parser.add_argument("--email",    default=DEFAULT_EMAIL,    help=f"Admin email (default: {DEFAULT_EMAIL})")
    parser.add_argument("--username", default=DEFAULT_USERNAME, help=f"Login username (default: {DEFAULT_USERNAME})")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help=f"Parol (default: {DEFAULT_PASSWORD})")
    parser.add_argument("--fullname", default=DEFAULT_FULLNAME, help=f"To'liq ism (default: {DEFAULT_FULLNAME})")

    args = parser.parse_args()

    asyncio.run(create_admin(
        email=args.email,
        username=args.username,
        password=args.password,
        full_name=args.fullname,
    ))


if __name__ == "__main__":
    main()
