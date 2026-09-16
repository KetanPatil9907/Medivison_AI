"""Appointment scheduling, slot browser, booking, self-service and doctor queue endpoints."""

import re
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.auth.deps import require_doctor, require_patient, require_patient_doctor
from app.core.database import get_db
from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.models import (
    Appointment,
    DoctorAvailability,
    FamilyProfile,
    User,
    UserRole,
    UserStatus,
)
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse
from app.services.timeline_service import add_timeline_event, log_json
from app.utils.audit import write_audit_log

router = APIRouter(prefix="/appointments", tags=["appointments"])

ACTIVE_STATUSES = ("BOOKED", "CONFIRMED", "RESCHEDULED")
SLOT_MINUTES = 30
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _parse_date(value: str) -> date:
    if not DATE_RE.match(value):
        raise ValidationException("Invalid date, expected YYYY-MM-DD", details={"value": value})
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValidationException("Invalid date, expected YYYY-MM-DD", details={"value": value})


def _time_to_minutes(value: str) -> int:
    if not TIME_RE.match(value):
        raise ValidationException("Invalid time, expected HH:MM (24h)", details={"value": value})
    hours, minutes = (int(part) for part in value.split(":"))
    return hours * 60 + minutes


def _minutes_to_time(value: int) -> str:
    if value >= 1440:
        return "24:00"
    return f"{value // 60:02d}:{value % 60:02d}"


def _overlaps(s1: int, e1: int, s2: int, e2: int) -> bool:
    return s1 < e2 and s2 < e1


def _get_bookable_doctor(db: Session, doctor_id: int) -> User:
    doctor = db.get(User, doctor_id)
    if (
        not doctor
        or doctor.role != UserRole.DOCTOR
        or doctor.status != UserStatus.ACTIVE
        or doctor.is_deleted
        or not doctor.doctor_profile
    ):
        raise NotFoundException("Doctor not found")
    return doctor


def _availability_windows(db: Session, doctor_profile_id: int, weekday: int) -> list[tuple[int, int]]:
    rows = (
        db.query(DoctorAvailability)
        .filter(
            DoctorAvailability.doctor_profile_id == doctor_profile_id,
            DoctorAvailability.day_of_week == weekday,
            DoctorAvailability.is_blocked.is_(False),
        )
        .all()
    )
    windows = []
    for row in rows:
        start = _time_to_minutes(row.start_time)
        end = _time_to_minutes(row.end_time)
        if end > start:
            windows.append((start, end))
    windows.sort()
    return windows


def _slot_in_windows(start: int, end: int, windows: list[tuple[int, int]]) -> bool:
    return any(ws <= start and end <= we for ws, we in windows)


def _doctor_bookings(db: Session, doctor_id: int, scheduled_date: date) -> list[Appointment]:
    return (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.scheduled_date == scheduled_date,
            Appointment.status.in_(ACTIVE_STATUSES),
        )
        .all()
    )


def _check_scheduling_conflicts(
    db: Session,
    doctor_id: int,
    patient_id: int,
    scheduled_date: date,
    start: int,
    end: int,
    exclude_id: int | None = None,
) -> None:
    base = [
        Appointment.scheduled_date == scheduled_date,
        Appointment.status.in_(ACTIVE_STATUSES),
    ]
    if exclude_id is not None:
        base.append(Appointment.id != exclude_id)

    doctor_conflict = (
        db.query(Appointment)
        .filter(*base, Appointment.doctor_id == doctor_id, Appointment.start_time == _minutes_to_time(start))
        .first()
    )
    if doctor_conflict:
        raise ConflictException("Doctor is already booked at this time and date")

    patient_appointments = (
        db.query(Appointment).filter(*base, Appointment.patient_id == patient_id).all()
    )
    for appt in patient_appointments:
        appt_start = _time_to_minutes(appt.start_time)
        appt_end = _time_to_minutes(appt.end_time)
        if _overlaps(appt_start, appt_end, start, end):
            raise ConflictException("You already have an overlapping appointment at this time and date")


def _validate_family_profile(db: Session, user: User, family_profile_id: int | None) -> None:
    if family_profile_id is None:
        return
    family = db.get(FamilyProfile, family_profile_id)
    if not family or not user.patient_profile or family.patient_profile_id != user.patient_profile.id:
        raise NotFoundException("Family profile not found")


def _load_users(db: Session, user_ids: list[int]) -> dict[int, User]:
    ids = {uid for uid in user_ids if uid is not None}
    if not ids:
        return {}
    users = (
        db.query(User)
        .options(joinedload(User.doctor_profile))
        .filter(User.id.in_(ids))
        .all()
    )
    return {u.id: u for u in users}


def _appointment_json(appointment: Appointment, users: dict[int, User]) -> dict:
    doctor = users.get(appointment.doctor_id)
    patient = users.get(appointment.patient_id)
    return {
        "id": appointment.id,
        "patient_id": appointment.patient_id,
        "doctor_id": appointment.doctor_id,
        "family_profile_id": appointment.family_profile_id,
        "scheduled_date": appointment.scheduled_date.isoformat() if appointment.scheduled_date else None,
        "start_time": appointment.start_time,
        "end_time": appointment.end_time,
        "duration_minutes": appointment.duration_minutes,
        "consultation_type": appointment.consultation_type,
        "status": appointment.status,
        "reason": appointment.reason,
        "symptoms_summary": appointment.symptoms_summary,
        "queue_position": appointment.queue_position,
        "checked_in_at": appointment.checked_in_at.isoformat() if appointment.checked_in_at else None,
        "cancelled_reason": appointment.cancelled_reason,
        "created_at": appointment.created_at.isoformat() if appointment.created_at else None,
        "doctor": {
            "id": doctor.id if doctor else None,
            "full_name": doctor.full_name if doctor else None,
            "specialization": doctor.doctor_profile.specialization if doctor and doctor.doctor_profile else None,
            "hospital": doctor.doctor_profile.hospital if doctor and doctor.doctor_profile else None,
        },
        "patient": {
            "id": patient.id if patient else None,
            "full_name": patient.full_name if patient else None,
            "profile_image_url": patient.profile_image_url if patient else None,
        },
    }


def _get_appointment_for_user(db: Session, appointment_id: int, user: User) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise NotFoundException("Appointment not found")
    if user.role == UserRole.DOCTOR:
        if appointment.doctor_id != user.id:
            raise ForbiddenException("You do not have access to this appointment")
    elif appointment.patient_id != user.id:
        raise ForbiddenException("You do not have access to this appointment")
    return appointment


class SlotOut(BaseModel):
    start_time: str
    end_time: str
    available: bool


class BookingRequest(BaseModel):
    doctor_id: int = Field(ge=1)
    scheduled_date: str
    start_time: str
    consultation_type: str = Field(default="in_person", pattern="^(in_person|online|phone)$")
    reason: Optional[str] = Field(default=None, max_length=2000)
    symptoms_summary: Optional[str] = Field(default=None, max_length=4000)
    family_profile_id: Optional[int] = None
    duration_minutes: int = Field(default=30, ge=10, le=240)


class CancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class RescheduleRequest(BaseModel):
    scheduled_date: str
    start_time: str


@router.get("/slots", response_model=ApiResponse[list[SlotOut]])
async def available_slots(
    doctor_id: int = Query(..., ge=1, description="Doctor user id"),
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient_doctor),
):
    doctor = _get_bookable_doctor(db, doctor_id)
    scheduled_date = _parse_date(date)
    windows = _availability_windows(db, doctor.doctor_profile.id, scheduled_date.weekday())

    bookings = _doctor_bookings(db, doctor.id, scheduled_date)
    booked = [(_time_to_minutes(b.start_time), _time_to_minutes(b.end_time)) for b in bookings]

    slots: list[SlotOut] = []
    seen: set[int] = set()
    for ws, we in windows:
        current = ws
        while current + SLOT_MINUTES <= we:
            if current not in seen:
                seen.add(current)
                slot_end = current + SLOT_MINUTES
                available = not any(_overlaps(current, slot_end, bs, be) for bs, be in booked)
                slots.append(
                    SlotOut(
                        start_time=_minutes_to_time(current),
                        end_time=_minutes_to_time(slot_end),
                        available=available,
                    )
                )
            current += SLOT_MINUTES
    slots.sort(key=lambda s: s.start_time)
    return ApiResponse(data=slots, message="Available slots retrieved")


@router.get("/my", response_model=PaginatedResponse)
async def my_appointments(
    status: Optional[str] = Query(
        None, pattern="^(BOOKED|CONFIRMED|COMPLETED|CANCELLED|RESCHEDULED)$"
    ),
    upcoming: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient_doctor),
):
    query = db.query(Appointment)
    if current_user.role == UserRole.DOCTOR:
        query = query.filter(Appointment.doctor_id == current_user.id)
    else:
        query = query.filter(Appointment.patient_id == current_user.id)

    today = datetime.now(timezone.utc).date()
    if status:
        query = query.filter(Appointment.status == status)
    if upcoming is True:
        query = query.filter(
            Appointment.scheduled_date >= today,
            Appointment.status.in_(ACTIVE_STATUSES),
        )
    elif upcoming is False:
        query = query.filter(Appointment.scheduled_date < today)

    total = query.count()
    appointments = (
        query.order_by(Appointment.scheduled_date.desc(), Appointment.start_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    users = _load_users(
        db,
        [aid for appt in appointments for aid in (appt.doctor_id, appt.patient_id)],
    )
    items = [_appointment_json(appt, users) for appt in appointments]
    return PaginatedResponse(
        data=PaginatedData(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        ),
        message="Appointments retrieved",
    )


@router.get("/doctor/today", response_model=ApiResponse[list[dict]])
async def doctor_today(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    today = datetime.now(timezone.utc).date()
    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == current_user.id,
            Appointment.scheduled_date == today,
            Appointment.status.in_(ACTIVE_STATUSES + ("COMPLETED",)),
        )
        .order_by(Appointment.start_time.asc())
        .all()
    )
    users = _load_users(db, [appt.patient_id for appt in appointments])
    items = []
    for appt in appointments:
        data = _appointment_json(appt, users)
        data.pop("doctor", None)
        items.append(data)
    return ApiResponse(data=items, message="Today's appointments retrieved")


@router.post("", response_model=ApiResponse[dict])
async def book_appointment(
    payload: BookingRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    doctor = _get_bookable_doctor(db, payload.doctor_id)
    scheduled_date = _parse_date(payload.scheduled_date)
    start = _time_to_minutes(payload.start_time)
    end = start + payload.duration_minutes
    if end > 1440:
        raise ValidationException(
            "Appointment end time exceeds midnight",
            details={"start_time": payload.start_time, "duration_minutes": payload.duration_minutes},
        )
    if scheduled_date < datetime.now(timezone.utc).date():
        raise ValidationException("Cannot book an appointment in the past")

    windows = _availability_windows(db, doctor.doctor_profile.id, scheduled_date.weekday())
    if not windows or not _slot_in_windows(start, end, windows):
        raise ConflictException("Requested slot is not within the doctor's availability")

    _check_scheduling_conflicts(db, doctor.id, current_user.id, scheduled_date, start, end)
    _validate_family_profile(db, current_user, payload.family_profile_id)

    appointment = Appointment(
        patient_id=current_user.id,
        doctor_id=doctor.id,
        family_profile_id=payload.family_profile_id,
        scheduled_date=scheduled_date,
        start_time=_minutes_to_time(start),
        end_time=_minutes_to_time(end),
        duration_minutes=payload.duration_minutes,
        consultation_type=payload.consultation_type,
        status="BOOKED",
        reason=payload.reason,
        symptoms_summary=payload.symptoms_summary,
    )
    db.add(appointment)
    db.flush()

    add_timeline_event(
        db,
        current_user.id,
        "appointment",
        "Appointment booked",
        description=(
            f"Appointment booked with Dr. {doctor.full_name} on "
            f"{scheduled_date.isoformat()} at {appointment.start_time}"
        ),
        event_date=scheduled_date,
        metadata_json=log_json(
            {
                "appointment_id": appointment.id,
                "doctor_id": doctor.id,
                "doctor_name": doctor.full_name,
                "scheduled_date": scheduled_date.isoformat(),
                "start_time": appointment.start_time,
            }
        ),
        family_profile_id=payload.family_profile_id,
        appointment_id=appointment.id,
    )
    db.commit()
    db.refresh(appointment)

    write_audit_log(
        db,
        current_user,
        "appointments.book",
        resource_type="appointment",
        resource_id=str(appointment.id),
        request=request,
        after={
            "doctor_id": doctor.id,
            "scheduled_date": scheduled_date.isoformat(),
            "start_time": appointment.start_time,
            "end_time": appointment.end_time,
            "duration_minutes": appointment.duration_minutes,
            "consultation_type": payload.consultation_type,
            "status": "BOOKED",
        },
    )
    users = _load_users(db, [appointment.doctor_id, appointment.patient_id])
    return ApiResponse(
        data=_appointment_json(appointment, users),
        message="Appointment booked successfully",
    )


@router.get("/{appointment_id}", response_model=ApiResponse[dict])
async def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient_doctor),
):
    appointment = _get_appointment_for_user(db, appointment_id, current_user)
    users = _load_users(db, [appointment.doctor_id, appointment.patient_id])
    return ApiResponse(data=_appointment_json(appointment, users), message="Appointment retrieved")


@router.patch("/{appointment_id}/cancel", response_model=ApiResponse[dict])
async def cancel_appointment(
    appointment_id: int,
    payload: CancelRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient_doctor),
):
    appointment = _get_appointment_for_user(db, appointment_id, current_user)
    if appointment.status not in ACTIVE_STATUSES:
        raise ConflictException(f"Cannot cancel an appointment with status {appointment.status}")

    before = {"status": appointment.status}
    appointment.status = "CANCELLED"
    appointment.cancelled_reason = payload.reason
    db.add(appointment)
    db.flush()

    add_timeline_event(
        db,
        appointment.patient_id,
        "appointment",
        "Appointment cancelled",
        description=(
            f"Appointment on {appointment.scheduled_date.isoformat()} "
            f"at {appointment.start_time} was cancelled"
        ),
        event_date=appointment.scheduled_date,
        metadata_json=log_json({"appointment_id": appointment.id, "reason": payload.reason}),
        appointment_id=appointment.id,
    )
    db.commit()
    db.refresh(appointment)

    write_audit_log(
        db,
        current_user,
        "appointments.cancel",
        resource_type="appointment",
        resource_id=str(appointment.id),
        request=request,
        before=before,
        after={"status": "CANCELLED", "cancelled_reason": payload.reason},
    )
    users = _load_users(db, [appointment.doctor_id, appointment.patient_id])
    return ApiResponse(data=_appointment_json(appointment, users), message="Appointment cancelled")


@router.patch("/{appointment_id}/reschedule", response_model=ApiResponse[dict])
async def reschedule_appointment(
    appointment_id: int,
    payload: RescheduleRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise NotFoundException("Appointment not found")
    if appointment.patient_id != current_user.id:
        raise ForbiddenException("You can only reschedule your own appointments")
    if appointment.status not in ACTIVE_STATUSES:
        raise ConflictException(f"Cannot reschedule an appointment with status {appointment.status}")

    scheduled_date = _parse_date(payload.scheduled_date)
    start = _time_to_minutes(payload.start_time)
    end = start + appointment.duration_minutes
    if end > 1440:
        raise ValidationException("Appointment end time exceeds midnight")
    if scheduled_date < datetime.now(timezone.utc).date():
        raise ValidationException("Cannot reschedule to a date in the past")

    doctor = _get_bookable_doctor(db, appointment.doctor_id)
    windows = _availability_windows(db, doctor.doctor_profile.id, scheduled_date.weekday())
    if not windows or not _slot_in_windows(start, end, windows):
        raise ConflictException("Requested slot is not within the doctor's availability")

    _check_scheduling_conflicts(
        db, doctor.id, current_user.id, scheduled_date, start, end, exclude_id=appointment.id
    )

    before = {
        "scheduled_date": appointment.scheduled_date.isoformat(),
        "start_time": appointment.start_time,
    }
    appointment.scheduled_date = scheduled_date
    appointment.start_time = _minutes_to_time(start)
    appointment.end_time = _minutes_to_time(end)
    appointment.status = "RESCHEDULED"
    db.add(appointment)
    db.flush()

    add_timeline_event(
        db,
        appointment.patient_id,
        "appointment",
        "Appointment rescheduled",
        description=(
            f"Appointment rescheduled to {scheduled_date.isoformat()} at {appointment.start_time}"
        ),
        event_date=scheduled_date,
        metadata_json=log_json(
            {
                "appointment_id": appointment.id,
                "scheduled_date": scheduled_date.isoformat(),
                "start_time": appointment.start_time,
            }
        ),
        appointment_id=appointment.id,
    )
    db.commit()
    db.refresh(appointment)

    write_audit_log(
        db,
        current_user,
        "appointments.reschedule",
        resource_type="appointment",
        resource_id=str(appointment.id),
        request=request,
        before=before,
        after={
            "scheduled_date": scheduled_date.isoformat(),
            "start_time": appointment.start_time,
            "end_time": appointment.end_time,
            "status": "RESCHEDULED",
        },
    )
    users = _load_users(db, [appointment.doctor_id, appointment.patient_id])
    return ApiResponse(data=_appointment_json(appointment, users), message="Appointment rescheduled")


@router.post("/{appointment_id}/confirm", response_model=ApiResponse[dict])
async def confirm_appointment(
    appointment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise NotFoundException("Appointment not found")
    if appointment.doctor_id != current_user.id:
        raise ForbiddenException("You can only confirm your own appointments")
    if appointment.status not in ACTIVE_STATUSES:
        raise ConflictException(f"Cannot confirm an appointment with status {appointment.status}")

    appointment.status = "CONFIRMED"
    db.commit()
    db.refresh(appointment)
    write_audit_log(
        db,
        current_user,
        "appointments.confirm",
        resource_type="appointment",
        resource_id=str(appointment.id),
        request=request,
        after={"status": "CONFIRMED"},
    )
    users = _load_users(db, [appointment.doctor_id, appointment.patient_id])
    return ApiResponse(data=_appointment_json(appointment, users), message="Appointment confirmed")


@router.post("/{appointment_id}/check-in", response_model=ApiResponse[dict])
async def check_in_patient(
    appointment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise NotFoundException("Appointment not found")
    if appointment.doctor_id != current_user.id:
        raise ForbiddenException("You can only check in patients for your own appointments")
    if appointment.status == "CANCELLED":
        raise ConflictException("Cannot check in a cancelled appointment")

    earlier = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == current_user.id,
            Appointment.scheduled_date == appointment.scheduled_date,
            Appointment.status != "CANCELLED",
            Appointment.start_time < appointment.start_time,
        )
        .count()
    )
    appointment.queue_position = earlier + 1
    appointment.checked_in_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(appointment)
    write_audit_log(
        db,
        current_user,
        "appointments.check_in",
        resource_type="appointment",
        resource_id=str(appointment.id),
        request=request,
        after={"queue_position": appointment.queue_position},
    )
    users = _load_users(db, [appointment.doctor_id, appointment.patient_id])
    return ApiResponse(data=_appointment_json(appointment, users), message="Patient checked in")