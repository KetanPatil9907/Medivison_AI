import time

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_token
from app.models.user import User, UserRole, UserStatus

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def _get_user_from_token(token: str, db: Session) -> User:
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise UnauthorizedException("Invalid or expired token")

    exp = payload.get("exp")
    if exp and int(exp) < int(time.time()):
        raise UnauthorizedException("Token has expired")

    user = db.get(User, int(payload.get("sub", 0)))
    if not user or user.is_deleted:
        raise UnauthorizedException("User not found")
    if user.status == UserStatus.SUSPENDED:
        raise ForbiddenException("Account is suspended. Contact support.")
    if user.status == UserStatus.DISABLED:
        raise UnauthorizedException("Account is disabled")
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    return _get_user_from_token(token, db)


def require_roles(*roles: UserRole):
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise ForbiddenException("You do not have permission to access this resource")
        if current_user.role == UserRole.DOCTOR and current_user.status != UserStatus.ACTIVE:
            raise ForbiddenException("Doctor account is not active")
        return current_user
    return checker


require_patient = require_roles(UserRole.PATIENT)
require_doctor = require_roles(UserRole.DOCTOR)
require_admin = require_roles(UserRole.ADMIN)
require_patient_doctor = require_roles(UserRole.PATIENT, UserRole.DOCTOR)
require_staff = require_roles(UserRole.DOCTOR, UserRole.ADMIN)


def get_client_context(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua