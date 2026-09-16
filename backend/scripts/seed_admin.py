"""Idempotent bootstrap script: create the platform admin user.

Usage:
    python scripts/seed_admin.py                 # uses settings.admin_*
    ADMIN_EMAIL=x ADMIN_PASSWORD=y python scripts/seed_admin.py

Credentials come from the ADMIN_* environment variables (or the values in
app.core.config.Settings.admin_*) and are never logged. Re-running the script
is safe: an existing admin account is left untouched.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import User, UserRole, UserStatus  # noqa: E402


def main() -> int:
    email = settings.admin_email.strip().lower()
    full_name = settings.admin_full_name.strip()
    password = settings.admin_initial_password

    if not email or not password:
        print("error: ADMIN_EMAIL / admin_email and admin_initial_password must be set")
        return 1

    db = SessionLocal()
    try:
        existing = db.execute(
            select(User).where(User.email == email, User.is_deleted.is_(False))
        ).scalar_one_or_none()
        if existing is not None:
            if existing.role != UserRole.ADMIN:
                print(f"warn: {email} exists but role is {existing.role.value}; not modified")
                return 2
            print(f"ok: admin already exists ({email}); nothing to do")
            return 0

        any_admin = db.execute(
            select(User).where(User.role == UserRole.ADMIN, User.is_deleted.is_(False))
        ).scalar_one_or_none()
        if any_admin is not None:
            print(
                f"warn: an admin already exists ({any_admin.email}); "
                f"refusing to create a second one"
            )
            return 2

        user = User(
            full_name=full_name,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"created admin user: id={user.id} email={email}")
        print("hint: change the password after first login via /auth/change-password")
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI script, surface and abort
        db.rollback()
        print(f"error: failed to seed admin: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())