"""Patient medication tracking, intake logging and adherence."""

import json
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth.deps import require_patient
from app.core.database import get_db
from app.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from app.models import FamilyProfile, Medication, User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse
from app.services.timeline_service import add_timeline_event, log_json
from app.utils.audit import write_audit_log

router = APIRouter(prefix="/medications", tags=["medications"])

MEDICATION_STATUS_PATTERN = "^(active|completed|paused|discontinued)$"
FREQUENCY_PATTERN = "^(once_daily|twice_daily|custom)$"
TIME_RE = "^([01]\\d|2[0-3]):[0-5]\\d$"


class MedicationCreateRequest(BaseModel):
    family_profile_id: Optional[int] = None
    name: str = Field(min_length=1, max_length=200)
    dosage: str = Field(min_length=1, max_length=120)
    frequency: str = Field(pattern=FREQUENCY_PATTERN)
    frequency_detail: Optional[str] = Field(default=None, max_length=200)
    times_per_day: int = Field(default=1, ge=1, le=24)
    start_date: date
    end_date: Optional[date] = None
    reminder_enabled: bool = True
    refill_reminder_enabled: bool = False
    refill_threshold_days: Optional[int] = Field(default=3, ge=0, le=365)
    instructions: Optional[str] = None
    prescribed_by: Optional[str] = Field(default=None, max_length=150)
    status: str = Field(default="active", pattern=MEDICATION_STATUS_PATTERN)


class MedicationUpdateRequest(BaseModel):
    family_profile_id: Optional[int] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    dosage: Optional[str] = Field(default=None, min_length=1, max_length=120)
    frequency: Optional[str] = Field(default=None, pattern=FREQUENCY_PATTERN)
    frequency_detail: Optional[str] = Field(default=None, max_length=200)
    times_per_day: Optional[int] = Field(default=None, ge=1, le=24)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    reminder_enabled: Optional[bool] = None
    refill_reminder_enabled: Optional[bool] = None
    refill_threshold_days: Optional[int] = Field(default=None, ge=0, le=365)
    instructions: Optional[str] = None
    prescribed_by: Optional[str] = Field(default=None, max_length=150)


class MedicationStatusRequest(BaseModel):
    status: str = Field(pattern=MEDICATION_STATUS_PATTERN)


class IntakeLogRequest(BaseModel):
    time: Optional[str] = Field(default=None, pattern=TIME_RE)
    taken: bool
    note: Optional[str] = None


def _json_ready(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _get_own_medication(db: Session, user: User, medication_id: int) -> Medication:
    medication = db.get(Medication, medication_id)
    if not medication or medication.patient_id != user.id:
        raise NotFoundException("Medication not found")
    return medication


def _validate_family_ownership(db: Session, user: User, family_profile_id: int | None) -> None:
    if family_profile_id is None:
        return
    family = db.get(FamilyProfile, family_profile_id)
    if not family or not user.patient_profile or family.patient_profile_id != user.patient_profile.id:
        raise NotFoundException("Family profile not found")


def _parse_intake_log(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (ValueError, TypeError):
        return []


def _compute_adherence(entries: list[dict], days: int = 7) -> Optional[float]:
    if not entries:
        return None
    cutoff = (date.today() - timedelta(days=days - 1)).isoformat()
    recent = [e for e in entries if str(e.get("date", "")) >= cutoff]
    if not recent:
        return None
    taken = sum(1 for e in recent if bool(e.get("taken", False)))
    return round(taken / len(recent) * 100, 1)


def _medication_json(medication: Medication) -> dict:
    return {
        "id": medication.id,
        "patient_id": medication.patient_id,
        "family_profile_id": medication.family_profile_id,
        "name": medication.name,
        "dosage": medication.dosage,
        "frequency": medication.frequency,
        "frequency_detail": medication.frequency_detail,
        "times_per_day": medication.times_per_day,
        "start_date": medication.start_date.isoformat() if medication.start_date else None,
        "end_date": medication.end_date.isoformat() if medication.end_date else None,
        "reminder_enabled": medication.reminder_enabled,
        "refill_reminder_enabled": medication.refill_reminder_enabled,
        "refill_threshold_days": medication.refill_threshold_days,
        "instructions": medication.instructions,
        "prescribed_by": medication.prescribed_by,
        "status": medication.status,
        "adherence_rate": medication.adherence_rate,
        "intake_log": _parse_intake_log(medication.intake_log),
        "created_at": medication.created_at.isoformat() if medication.created_at else None,
        "updated_at": medication.updated_at.isoformat() if medication.updated_at else None,
    }


@router.post("", response_model=ApiResponse[dict])
async def create_medication(
    payload: MedicationCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    _validate_family_ownership(db, current_user, payload.family_profile_id)
    if payload.end_date and payload.end_date < payload.start_date:
        raise ValidationException(
            "end_date must be on or after start_date",
            details={"start_date": _json_ready(payload.start_date), "end_date": _json_ready(payload.end_date)},
        )
    if payload.status == "completed" and payload.end_date and payload.end_date > date.today():
        raise ValidationException(
            "A medication cannot be marked completed while it is still running",
            details={"end_date": _json_ready(payload.end_date)},
        )

    medication = Medication(
        patient_id=current_user.id,
        family_profile_id=payload.family_profile_id,
        name=payload.name,
        dosage=payload.dosage,
        frequency=payload.frequency,
        frequency_detail=payload.frequency_detail,
        times_per_day=payload.times_per_day,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reminder_enabled=payload.reminder_enabled,
        refill_reminder_enabled=payload.refill_reminder_enabled,
        refill_threshold_days=payload.refill_threshold_days,
        instructions=payload.instructions,
        prescribed_by=payload.prescribed_by,
        status=payload.status,
        adherence_rate=None,
        intake_log=None,
    )
    db.add(medication)
    db.flush()

    add_timeline_event(
        db,
        current_user.id,
        "health_event",
        "Medication added",
        description=f"{payload.name} ({payload.dosage}) - {payload.frequency}",
        event_date=payload.start_date,
        metadata_json=log_json({
            "medication_id": medication.id,
            "name": payload.name,
            "dosage": payload.dosage,
            "frequency": payload.frequency,
            "status": payload.status,
            "family_profile_id": payload.family_profile_id,
        }),
        family_profile_id=payload.family_profile_id,
    )
    db.commit()
    db.refresh(medication)

    write_audit_log(
        db, current_user, "medications.create",
        resource_type="medication", resource_id=str(medication.id),
        request=request,
        after={
            "name": payload.name,
            "dosage": payload.dosage,
            "frequency": payload.frequency,
            "status": payload.status,
            "family_profile_id": payload.family_profile_id,
        },
    )
    return ApiResponse(data=_medication_json(medication), message="Medication added")


@router.get("/my", response_model=PaginatedResponse)
async def my_medications(
    status: Optional[str] = Query(None, pattern=MEDICATION_STATUS_PATTERN),
    family_profile_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    if family_profile_id is not None:
        _validate_family_ownership(db, current_user, family_profile_id)

    query = db.query(Medication).filter(Medication.patient_id == current_user.id)
    if status:
        query = query.filter(Medication.status == status)
    if family_profile_id is not None:
        query = query.filter(Medication.family_profile_id == family_profile_id)

    total = query.count()
    medications = (
        query.order_by(Medication.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedResponse(
        data=PaginatedData(
            items=[_medication_json(m) for m in medications],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        ),
        message="Medications retrieved",
    )


@router.get("/reminders/today", response_model=ApiResponse[list[dict]])
async def medications_due_today(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    today = date.today()
    medications = (
        db.query(Medication)
        .filter(
            Medication.patient_id == current_user.id,
            Medication.reminder_enabled.is_(True),
            Medication.status == "active",
            or_(Medication.end_date.is_(None), Medication.end_date >= today),
        )
        .order_by(Medication.created_at.desc())
        .all()
    )
    items = [
        {
            "id": m.id,
            "family_profile_id": m.family_profile_id,
            "name": m.name,
            "dosage": m.dosage,
            "frequency": m.frequency,
            "frequency_detail": m.frequency_detail,
            "times_per_day": m.times_per_day,
            "instructions": m.instructions,
            "refill_reminder_enabled": m.refill_reminder_enabled,
        }
        for m in medications
    ]
    return ApiResponse(data=items, message="Today's medication reminders retrieved")


@router.get("/{medication_id}", response_model=ApiResponse[dict])
async def get_medication(
    medication_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    medication = _get_own_medication(db, current_user, medication_id)
    return ApiResponse(data=_medication_json(medication), message="Medication retrieved")


@router.put("/{medication_id}", response_model=ApiResponse[dict])
async def update_medication(
    medication_id: int,
    payload: MedicationUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    medication = _get_own_medication(db, current_user, medication_id)

    updates = payload.model_dump(exclude_unset=True)
    if "family_profile_id" in updates:
        _validate_family_ownership(db, current_user, updates["family_profile_id"])

    new_start = updates.get("start_date", medication.start_date)
    new_end = updates.get("end_date", medication.end_date)
    if new_end and new_end < new_start:
        raise ValidationException(
            "end_date must be on or after start_date",
            details={"start_date": _json_ready(new_start), "end_date": _json_ready(new_end)},
        )

    before = {
        "name": medication.name,
        "dosage": medication.dosage,
        "frequency": medication.frequency,
        "start_date": _json_ready(medication.start_date),
        "end_date": _json_ready(medication.end_date),
        "status": medication.status,
        "reminder_enabled": medication.reminder_enabled,
        "family_profile_id": medication.family_profile_id,
    }
    for field_name, value in updates.items():
        setattr(medication, field_name, value)
    if medication.end_date and medication.end_date <= date.today():
        medication.status = "completed"

    db.commit()
    db.refresh(medication)
    write_audit_log(
        db, current_user, "medications.update",
        resource_type="medication", resource_id=str(medication.id),
        request=request, before=before,
        after={k: _json_ready(v) for k, v in updates.items()},
    )
    return ApiResponse(data=_medication_json(medication), message="Medication updated")


@router.patch("/{medication_id}/status", response_model=ApiResponse[dict])
async def update_medication_status(
    medication_id: int,
    payload: MedicationStatusRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    medication = _get_own_medication(db, current_user, medication_id)
    before = {"status": medication.status}
    medication.status = payload.status
    db.commit()
    db.refresh(medication)
    write_audit_log(
        db, current_user, "medications.status_update",
        resource_type="medication", resource_id=str(medication.id),
        request=request, before=before, after={"status": medication.status},
    )
    return ApiResponse(data=_medication_json(medication), message="Medication status updated")


@router.post("/{medication_id}/log", response_model=ApiResponse[dict])
async def log_intake(
    medication_id: int,
    payload: IntakeLogRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    medication = _get_own_medication(db, current_user, medication_id)
    entries = _parse_intake_log(medication.intake_log)

    entry = {
        "date": date.today().isoformat(),
        "time": payload.time or datetime.now(timezone.utc).strftime("%H:%M"),
        "taken": payload.taken,
    }
    if payload.note:
        entry["note"] = payload.note
    entries.append(entry)

    medication.intake_log = log_json(entries)
    medication.adherence_rate = _compute_adherence(entries)
    db.add(medication)
    db.flush()

    add_timeline_event(
        db,
        medication.patient_id,
        "health_event",
        "Medication intake logged",
        description=f"{medication.name}: intake {'taken' if payload.taken else 'missed'} at {entry['time']}",
        event_date=date.today(),
        metadata_json=log_json({
            "medication_id": medication.id,
            "name": medication.name,
            "taken": payload.taken,
            "time": entry["time"],
        }),
        family_profile_id=medication.family_profile_id,
    )
    db.commit()
    db.refresh(medication)

    write_audit_log(
        db, current_user, "medications.intake_log",
        resource_type="medication", resource_id=str(medication.id),
        request=request,
        after={"name": medication.name, "date": entry["date"], "time": entry["time"], "taken": payload.taken},
    )
    return ApiResponse(data=_medication_json(medication), message="Intake logged")


@router.get("/{medication_id}/adherence", response_model=ApiResponse[dict])
async def get_adherence(
    medication_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    medication = _get_own_medication(db, current_user, medication_id)
    cutoff = (date.today() - timedelta(days=13)).isoformat()
    last_14_days = [
        e for e in _parse_intake_log(medication.intake_log) if str(e.get("date", "")) >= cutoff
    ]
    return ApiResponse(
        data={
            "medication_id": medication.id,
            "name": medication.name,
            "adherence_rate": medication.adherence_rate,
            "last_14_days": last_14_days,
        },
        message="Adherence retrieved",
    )