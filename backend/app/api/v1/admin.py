from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.auth.deps import get_current_user, require_admin
from app.core.database import get_db
from app.core.exceptions import NotFoundException
from app.models.user import (
    DoctorApplication, DoctorProfile, User, UserRole, UserStatus,
)
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse
from app.utils.audit import write_audit_log

router = APIRouter(prefix="/admin", tags=["admin"])


def _as_applicant_json(app: DoctorApplication, user: User | None) -> dict:
    return {
        "id": app.id,
        "user_id": app.user_id,
        "full_name": user.full_name if user else None,
        "email": user.email if user else None,
        "phone": app.phone,
        "specialization": app.specialization,
        "qualification": app.qualification,
        "medical_registration_number": app.medical_registration_number,
        "years_of_experience": app.years_of_experience,
        "hospital": app.hospital,
        "address": app.address,
        "consultation_type": app.consultation_type,
        "status": app.status,
        "rejection_reason": app.rejection_reason,
        "submitted_at": app.created_at.isoformat() if app.created_at else None,
        "reviewed_at": app.reviewed_at.isoformat() if app.reviewed_at else None,
        "documents": app.documents,
    }


class ReviewRequest(BaseModel):
    status: str = Field(pattern="^(APPROVED|REJECTED)$")
    rejection_reason: Optional[str] = None


class SuspendRequest(BaseModel):
    reason: Optional[str] = None


def _get_application(db: Session, application_id: int) -> DoctorApplication:
    app = db.get(DoctorApplication, application_id)
    if not app:
        raise NotFoundException("Doctor application not found")
    return app


@router.get("/doctor/applications", response_model=PaginatedResponse)
async def list_applications(
    status: Optional[str] = Query(None, pattern="^(PENDING|APPROVED|REJECTED)$"),
    specialization: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    query = db.query(DoctorApplication)
    if status:
        query = query.filter(DoctorApplication.status == status)
    if specialization:
        query = query.filter(DoctorApplication.specialization.ilike(f"%{specialization}%"))
    if search:
        query = query.join(User).filter(
            (User.full_name.ilike(f"%{search}%"))
            | (User.email.ilike(f"%{search}%"))
            | (DoctorApplication.medical_registration_number.ilike(f"%{search}%"))
        )
    total = query.count()
    apps = (
        query.order_by(DoctorApplication.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    users = {u.id: u for u in db.query(User).filter(User.id.in_([a.user_id for a in apps])).all()} if apps else {}
    items = [_as_applicant_json(a, users.get(a.user_id)) for a in apps]
    return PaginatedResponse(
        data=PaginatedData(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)
    )


@router.get("/doctor/applications/{application_id}", response_model=ApiResponse[dict])
async def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    app = _get_application(db, application_id)
    user = db.get(User, app.user_id)
    return ApiResponse(data=_as_applicant_json(app, user))


@router.post("/doctor/applications/{application_id}/review", response_model=ApiResponse[dict])
async def review_application(
    application_id: int,
    payload: ReviewRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    app = _get_application(db, application_id)
    user = db.get(User, app.user_id)
    if not user:
        raise NotFoundException("Application owner not found")

    if payload.status == "APPROVED":
        app.status = "APPROVED"
        app.rejection_reason = None
        user.status = UserStatus.ACTIVE

        existing = db.query(DoctorProfile).filter(DoctorProfile.user_id == user.id).first()
        if not existing:
            db.add(DoctorProfile(
                user_id=user.id,
                specialization=app.specialization,
                qualification=app.qualification,
                medical_registration_number=app.medical_registration_number,
                years_of_experience=app.years_of_experience,
                hospital=app.hospital,
                address=app.address,
                consultation_type=app.consultation_type,
            ))
    else:
        app.status = "REJECTED"
        app.rejection_reason = payload.rejection_reason
        user.status = UserStatus.REJECTED

    app.reviewed_by = admin.id
    app.reviewed_at = datetime.now(timezone.utc)
    db.commit()

    write_audit_log(
        db, admin, "admin.review_doctor_application",
        resource_type="doctor_application", resource_id=str(app.id),
        request=request, after={"status": payload.status},
    )
    return ApiResponse(
        data={"status": app.status, "rejection_reason": app.rejection_reason},
        message=f"Application {app.status.lower()}",
    )


@router.get("/doctors", response_model=PaginatedResponse)
async def list_doctors(
    status: Optional[str] = Query(None, pattern="^(ACTIVE|SUSPENDED|PENDING|REJECTED)$"),
    specialization: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    query = db.query(User).join(DoctorProfile, DoctorProfile.user_id == User.id)
    if status:
        query = query.filter(User.status == status)
    if specialization:
        query = query.filter(DoctorProfile.specialization.ilike(f"%{specialization}%"))
    if search:
        query = query.filter(
            (User.full_name.ilike(f"%{search}%")) | (User.email.ilike(f"%{search}%"))
        )
    total = query.count()
    doctors = (
        query.order_by(User.created_at.desc())
        .options(joinedload(User.doctor_profile))
        .offset((page - 1) * page_size).limit(page_size).all()
    )
    items = [{
        "id": d.id,
        "full_name": d.full_name,
        "email": d.email,
        "status": d.status.value,
        "specialization": d.doctor_profile.specialization,
        "qualification": d.doctor_profile.qualification,
        "years_of_experience": d.doctor_profile.years_of_experience,
        "hospital": d.doctor_profile.hospital,
        "consultation_type": d.doctor_profile.consultation_type,
        "rating": d.doctor_profile.rating,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    } for d in doctors]
    return PaginatedResponse(data=PaginatedData(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size))


@router.put("/doctors/{doctor_id}/suspend", response_model=ApiResponse[dict])
async def suspend_doctor(
    doctor_id: int,
    payload: SuspendRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    doctor = db.get(User, doctor_id)
    if not doctor or doctor.role != UserRole.DOCTOR:
        raise NotFoundException("Doctor not found")
    doctor.status = UserStatus.SUSPENDED
    db.commit()
    write_audit_log(
        db, admin, "admin.suspend_doctor", resource_type="user", resource_id=str(doctor_id),
        request=request, after={"status": "SUSPENDED", "reason": payload.reason},
    )
    return ApiResponse(message=f"Doctor {doctor.full_name} suspended")


@router.put("/doctors/{doctor_id}/reactivate", response_model=ApiResponse[dict])
async def reactivate_doctor(
    doctor_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    doctor = db.get(User, doctor_id)
    if not doctor or doctor.role != UserRole.DOCTOR:
        raise NotFoundException("Doctor not found")
    doctor.status = UserStatus.ACTIVE
    db.commit()
    write_audit_log(
        db, admin, "admin.reactivate_doctor", resource_type="user", resource_id=str(doctor_id),
        request=request, after={"status": "ACTIVE"},
    )
    return ApiResponse(message=f"Doctor {doctor.full_name} reactivated")