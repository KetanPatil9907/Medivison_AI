"""Doctor public directory and self-service profile / availability management endpoints."""

import re
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.auth.deps import require_doctor, require_patient_doctor
from app.core.database import get_db
from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.models import (
    DoctorAvailability,
    DoctorProfile,
    User,
    UserRole,
    UserStatus,
)
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse
from app.utils.audit import write_audit_log

router = APIRouter(prefix="/doctors", tags=["doctors"])

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _time_to_minutes(value: str) -> int:
    if not TIME_RE.match(value):
        raise ValidationException(
            "Invalid time, expected HH:MM in 24h format",
            details={"value": value},
        )
    hours, minutes = (int(part) for part in value.split(":"))
    return hours * 60 + minutes


def _validate_slot(day_of_week: int, start_time: str, end_time: str) -> None:
    if day_of_week < 0 or day_of_week > 6:
        raise ValidationException(
            "day_of_week must be between 0 (Monday) and 6 (Sunday)",
            details={"day_of_week": day_of_week},
        )
    start = _time_to_minutes(start_time)
    end = _time_to_minutes(end_time)
    if end <= start:
        raise ValidationException(
            "end_time must be after start_time",
            details={"start_time": start_time, "end_time": end_time},
        )


def _get_own_profile(db: Session, user: User) -> DoctorProfile:
    profile = user.doctor_profile
    if not profile:
        raise NotFoundException("Doctor profile not found")
    return profile


def _doctor_card(user: User) -> dict:
    profile = user.doctor_profile
    return {
        "id": user.id,
        "full_name": user.full_name,
        "specialization": profile.specialization,
        "qualification": profile.qualification,
        "years_of_experience": profile.years_of_experience,
        "hospital": profile.hospital,
        "address": profile.address,
        "consultation_type": profile.consultation_type,
        "rating": profile.rating,
        "rating_count": profile.rating_count,
        "languages": profile.languages,
        "consultation_fee": profile.consultation_fee,
        "online_consultation_enabled": profile.online_consultation_enabled,
        "profile_image_url": user.profile_image_url,
    }


def _doctor_self(user: User) -> dict:
    profile = user.doctor_profile
    data = _doctor_card(user)
    data.update(
        {
            "clinic_name": profile.clinic_name,
            "bio": profile.bio,
            "medical_registration_number": profile.medical_registration_number,
        }
    )
    return data


def _availability_json(slot: DoctorAvailability) -> dict:
    return {
        "id": slot.id,
        "day_of_week": slot.day_of_week,
        "start_time": slot.start_time,
        "end_time": slot.end_time,
        "is_blocked": slot.is_blocked,
    }


class ProfileUpdateRequest(BaseModel):
    specialization: Optional[str] = Field(default=None, min_length=2, max_length=120)
    qualification: Optional[str] = Field(default=None, min_length=2, max_length=300)
    medical_registration_number: Optional[str] = Field(default=None, min_length=3, max_length=100)
    years_of_experience: Optional[int] = Field(default=None, ge=0, le=70)
    hospital: Optional[str] = Field(default=None, min_length=1, max_length=200)
    clinic_name: Optional[str] = Field(default=None, max_length=200)
    address: Optional[str] = Field(default=None, min_length=2)
    consultation_type: Optional[str] = Field(default=None, pattern="^(in_person|online|both)$")
    languages: Optional[str] = Field(default=None, min_length=1, max_length=200)
    consultation_fee: Optional[float] = Field(default=None, ge=0)
    bio: Optional[str] = Field(default=None, max_length=2000)
    online_consultation_enabled: Optional[bool] = None


class AvailabilitySlotRequest(BaseModel):
    day_of_week: int
    start_time: str
    end_time: str
    is_blocked: bool = False


class AvailabilityBulkReplaceRequest(BaseModel):
    slots: list[AvailabilitySlotRequest]


class BlockRequest(BaseModel):
    day_of_week: int
    start_time: str
    end_time: str


@router.get("", response_model=PaginatedResponse)
async def search_doctors(
    specialization: Optional[str] = None,
    city: Optional[str] = None,
    consultation_type: Optional[str] = Query(None, pattern="^(in_person|online|both)$"),
    language: Optional[str] = None,
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient_doctor),
):
    query = (
        db.query(User)
        .join(DoctorProfile, DoctorProfile.user_id == User.id)
        .filter(
            User.role == UserRole.DOCTOR,
            User.status == UserStatus.ACTIVE,
            User.is_deleted.is_(False),
        )
    )
    if specialization:
        query = query.filter(DoctorProfile.specialization.ilike(f"%{specialization}%"))
    if city:
        query = query.filter(DoctorProfile.address.ilike(f"%{city}%"))
    if consultation_type:
        query = query.filter(DoctorProfile.consultation_type == consultation_type)
    if language:
        query = query.filter(DoctorProfile.languages.ilike(f"%{language}%"))
    if min_rating is not None:
        query = query.filter(DoctorProfile.rating >= min_rating)

    total = query.count()
    doctors = (
        query.options(joinedload(User.doctor_profile))
        .order_by(DoctorProfile.rating.desc(), User.full_name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [_doctor_card(d) for d in doctors]
    return PaginatedResponse(
        data=PaginatedData(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        ),
        message="Doctors retrieved",
    )


@router.get("/{doctor_id}", response_model=ApiResponse[dict])
async def get_doctor_detail(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient_doctor),
):
    doctor = (
        db.query(User)
        .options(
            joinedload(User.doctor_profile).joinedload(DoctorProfile.qualifications),
            joinedload(User.doctor_profile).joinedload(DoctorProfile.specialties),
            joinedload(User.doctor_profile).joinedload(DoctorProfile.availability),
        )
        .filter(
            User.id == doctor_id,
            User.role == UserRole.DOCTOR,
            User.status == UserStatus.ACTIVE,
            User.is_deleted.is_(False),
        )
        .first()
    )
    if not doctor or not doctor.doctor_profile:
        raise NotFoundException("Doctor not found")
    profile = doctor.doctor_profile
    data = {
        **_doctor_card(doctor),
        "clinic_name": profile.clinic_name,
        "bio": profile.bio,
        "qualifications": [
            {
                "degree": q.degree,
                "institution": q.institution,
                "year_completed": q.year_completed,
            }
            for q in profile.qualifications
        ],
        "specialties": [{"specialty": s.specialty} for s in profile.specialties],
        "availability": [
            {
                "day_of_week": a.day_of_week,
                "start_time": a.start_time,
                "end_time": a.end_time,
                "is_blocked": a.is_blocked,
            }
            for a in sorted(profile.availability, key=lambda x: (x.day_of_week, x.start_time))
        ],
    }
    return ApiResponse(data=data, message="Doctor retrieved")


@router.put("/me/profile", response_model=ApiResponse[dict])
async def update_my_profile(
    payload: ProfileUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    profile = _get_own_profile(db, current_user)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise ValidationException("No fields provided to update")

    new_registration = updates.get("medical_registration_number")
    if new_registration:
        existing = (
            db.query(DoctorProfile)
            .filter(
                DoctorProfile.medical_registration_number == new_registration,
                DoctorProfile.user_id != current_user.id,
            )
            .first()
        )
        if existing:
            raise ConflictException("Medical registration number is already in use")

    before = {
        "specialization": profile.specialization,
        "qualification": profile.qualification,
        "medical_registration_number": profile.medical_registration_number,
        "years_of_experience": profile.years_of_experience,
        "hospital": profile.hospital,
        "clinic_name": profile.clinic_name,
        "address": profile.address,
        "consultation_type": profile.consultation_type,
        "languages": profile.languages,
        "consultation_fee": profile.consultation_fee,
        "bio": profile.bio,
        "online_consultation_enabled": profile.online_consultation_enabled,
    }
    for field_name, value in updates.items():
        setattr(profile, field_name, value)

    db.commit()
    db.refresh(profile)
    write_audit_log(
        db,
        current_user,
        "doctors.profile_update",
        resource_type="doctor_profile",
        resource_id=str(profile.id),
        request=request,
        before=before,
        after=updates,
    )
    return ApiResponse(data=_doctor_self(current_user), message="Doctor profile updated")


@router.get("/me/availability", response_model=ApiResponse[list[dict]])
async def get_my_availability(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    profile = _get_own_profile(db, current_user)
    slots = (
        db.query(DoctorAvailability)
        .filter(DoctorAvailability.doctor_profile_id == profile.id)
        .order_by(DoctorAvailability.day_of_week.asc(), DoctorAvailability.start_time.asc())
        .all()
    )
    return ApiResponse(
        data=[_availability_json(s) for s in slots],
        message="Availability retrieved",
    )


@router.put("/me/availability", response_model=ApiResponse[dict])
async def replace_my_availability(
    payload: AvailabilityBulkReplaceRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    profile = _get_own_profile(db, current_user)
    if not payload.slots:
        raise ValidationException("At least one availability slot is required")
    for slot in payload.slots:
        _validate_slot(slot.day_of_week, slot.start_time, slot.end_time)

    db.query(DoctorAvailability).filter(
        DoctorAvailability.doctor_profile_id == profile.id
    ).delete(synchronize_session=False)

    for slot in payload.slots:
        db.add(
            DoctorAvailability(
                doctor_profile_id=profile.id,
                day_of_week=slot.day_of_week,
                start_time=slot.start_time,
                end_time=slot.end_time,
                is_blocked=slot.is_blocked,
            )
        )
    db.commit()
    write_audit_log(
        db,
        current_user,
        "doctors.availability_update",
        resource_type="doctor_profile",
        resource_id=str(profile.id),
        request=request,
        after={"slots": [slot.model_dump() for slot in payload.slots]},
    )
    return ApiResponse(data={"updated": len(payload.slots)}, message="Availability updated")


@router.post("/me/availability/block", response_model=ApiResponse[dict])
async def block_availability(
    payload: BlockRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    profile = _get_own_profile(db, current_user)
    _validate_slot(payload.day_of_week, payload.start_time, payload.end_time)
    block = DoctorAvailability(
        doctor_profile_id=profile.id,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
        is_blocked=True,
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    write_audit_log(
        db,
        current_user,
        "doctors.availability_block",
        resource_type="doctor_profile",
        resource_id=str(profile.id),
        request=request,
        after={
            "day_of_week": block.day_of_week,
            "start_time": block.start_time,
            "end_time": block.end_time,
            "is_blocked": True,
        },
    )
    return ApiResponse(data=_availability_json(block), message="Time block added")