from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import UnauthorizedException
from app.core.security import decode_token, hash_password
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterDoctorRequest,
    RegisterPatientRequest,
    TokenResponse,
    UserPublic,
)
from app.schemas.common import ApiResponse
from app.services import auth_service
from app.utils.audit import write_audit_log

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register/patient", response_model=ApiResponse[TokenResponse])
async def register_patient(payload: RegisterPatientRequest, db: Session = Depends(get_db)):
    user = auth_service.register_patient(db, payload)
    tokens = auth_service.issue_tokens(user)
    write_audit_log(db, user, "auth.register", resource_type="user", resource_id=str(user.id))
    return ApiResponse(data={**tokens, "user": UserPublic.model_validate(user)}, message="Patient registered successfully")


@router.post("/register/doctor", response_model=ApiResponse[dict])
async def register_doctor(payload: RegisterDoctorRequest, db: Session = Depends(get_db)):
    user = auth_service.register_doctor(db, payload)
    write_audit_log(db, user, "auth.register_doctor", resource_type="user", resource_id=str(user.id))
    return ApiResponse(
        data={
            "user_id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "status": "PENDING",
            "message": "Your application has been submitted for admin review. You will be able to log in after approval.",
        },
        message="Doctor application submitted",
    )


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = auth_service.authenticate(db, payload.email, payload.password)
    tokens = auth_service.issue_tokens(user)
    write_audit_log(
        db, user, "auth.login", request=request,
        resource_type="user", resource_id=str(user.id), success=True,
    )
    return ApiResponse(data={**tokens, "user": UserPublic.model_validate(user)}, message="Login successful")


@router.post("/refresh", response_model=ApiResponse[TokenResponse])
async def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    claims = decode_token(payload.refresh_token)
    if not claims or claims.get("type") != "refresh":
        raise UnauthorizedException("Invalid refresh token")
    user = db.get(User, int(claims["sub"]))
    if not user or user.is_deleted:
        raise UnauthorizedException("User not found")
    tokens = auth_service.issue_tokens(user)
    return ApiResponse(data={**tokens, "user": UserPublic.model_validate(user)})


@router.get("/me", response_model=ApiResponse[UserPublic])
async def get_me(current_user: User = Depends(get_current_user)):
    return ApiResponse(data=UserPublic.model_validate(current_user))


@router.put("/change-password", response_model=ApiResponse[dict])
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.core.security import verify_password
    if not verify_password(payload.old_password, current_user.password_hash):
        raise UnauthorizedException("Current password is incorrect")
    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    return ApiResponse(message="Password changed successfully")