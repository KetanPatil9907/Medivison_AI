"""Consultation records, prescriptions and doctor dashboard overview."""

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.auth.deps import require_doctor, require_patient_doctor
from app.core.database import get_db
from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.models import Appointment, Consultation, Prescription, User, UserRole
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse
from app.services.timeline_service import add_timeline_event, log_json
from app.utils.audit import write_audit_log

router = APIRouter(prefix="/consultations", tags=["consultations"])


class ConsultationCreateRequest(BaseModel):
    appointment_id: int = Field(ge=1)
    notes: Optional[str] = None
    diagnosis: Optional[str] = None
    clinical_impression: Optional[str] = None
    symptoms: Optional[str] = None
    vital_signs: Optional[str] = None
    recommended_tests: Optional[str] = None
    follow_up_date: Optional[date] = None
    follow_up_instructions: Optional[str] = None


class ConsultationUpdateRequest(BaseModel):
    notes: Optional[str] = None
    diagnosis: Optional[str] = None
    clinical_impression: Optional[str] = None
    symptoms: Optional[str] = None
    vital_signs: Optional[str] = None
    recommended_tests: Optional[str] = None
    follow_up_date: Optional[date] = None
    follow_up_instructions: Optional[str] = None


class PrescriptionCreateRequest(BaseModel):
    medicine_name: str = Field(min_length=1, max_length=200)
    dosage: str = Field(min_length=1, max_length=120)
    frequency: str = Field(min_length=1, max_length=120)
    duration_days: Optional[int] = Field(default=None, ge=1, le=3650)
    instructions: Optional[str] = None
    refill_count: Optional[int] = Field(default=None, ge=0, le=100)
    is_active: bool = True


def _json_ready(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _get_consultation_for_user(db: Session, consultation_id: int, user: User) -> Consultation:
    consultation = db.get(Consultation, consultation_id)
    if not consultation:
        raise NotFoundException("Consultation not found")
    if user.role == UserRole.DOCTOR:
        if consultation.doctor_id != user.id:
            raise ForbiddenException("You do not have access to this consultation")
    elif consultation.patient_id != user.id:
        raise ForbiddenException("You do not have access to this consultation")
    return consultation


def _get_doctor_consultation(db: Session, consultation_id: int, doctor: User) -> Consultation:
    consultation = db.get(Consultation, consultation_id)
    if not consultation:
        raise NotFoundException("Consultation not found")
    if consultation.doctor_id != doctor.id:
        raise ForbiddenException("You can only manage your own consultations")
    return consultation


def _load_context(
    db: Session, consultations: list[Consultation]
) -> tuple[dict[int, User], dict[int, Appointment]]:
    user_ids = set()
    appt_ids = set()
    for c in consultations:
        user_ids.add(c.doctor_id)
        user_ids.add(c.patient_id)
        appt_ids.add(c.appointment_id)

    users: dict[int, User] = {}
    if user_ids:
        rows = (
            db.query(User)
            .options(joinedload(User.doctor_profile))
            .filter(User.id.in_(user_ids))
            .all()
        )
        users = {u.id: u for u in rows}

    appointments: dict[int, Appointment] = {}
    if appt_ids:
        rows = db.query(Appointment).filter(Appointment.id.in_(appt_ids)).all()
        appointments = {a.id: a for a in rows}
    return users, appointments


def _prescription_json(prescription: Prescription) -> dict:
    return {
        "id": prescription.id,
        "consultation_id": prescription.consultation_id,
        "doctor_id": prescription.doctor_id,
        "patient_id": prescription.patient_id,
        "medicine_name": prescription.medicine_name,
        "dosage": prescription.dosage,
        "frequency": prescription.frequency,
        "duration_days": prescription.duration_days,
        "instructions": prescription.instructions,
        "refill_count": prescription.refill_count,
        "is_active": prescription.is_active,
        "created_at": prescription.created_at.isoformat() if prescription.created_at else None,
    }


def _consultation_json(
    consultation: Consultation,
    users: dict[int, User],
    appointments: dict[int, Appointment],
    include_prescriptions: bool = False,
) -> dict:
    doctor = users.get(consultation.doctor_id)
    patient = users.get(consultation.patient_id)
    appt = appointments.get(consultation.appointment_id)
    data = {
        "id": consultation.id,
        "appointment_id": consultation.appointment_id,
        "doctor_id": consultation.doctor_id,
        "patient_id": consultation.patient_id,
        "notes": consultation.notes,
        "diagnosis": consultation.diagnosis,
        "clinical_impression": consultation.clinical_impression,
        "symptoms": consultation.symptoms,
        "vital_signs": consultation.vital_signs,
        "recommended_tests": consultation.recommended_tests,
        "follow_up_date": consultation.follow_up_date.isoformat() if consultation.follow_up_date else None,
        "follow_up_instructions": consultation.follow_up_instructions,
        "status": consultation.status,
        "completed_at": consultation.completed_at.isoformat() if consultation.completed_at else None,
        "created_at": consultation.created_at.isoformat() if consultation.created_at else None,
        "updated_at": consultation.updated_at.isoformat() if consultation.updated_at else None,
        "doctor": {
            "id": doctor.id if doctor else None,
            "full_name": doctor.full_name if doctor else None,
            "specialization": doctor.doctor_profile.specialization if doctor and doctor.doctor_profile else None,
        },
        "patient": {
            "id": patient.id if patient else None,
            "full_name": patient.full_name if patient else None,
        },
        "appointment": {
            "id": appt.id if appt else None,
            "scheduled_date": appt.scheduled_date.isoformat() if appt and appt.scheduled_date else None,
            "start_time": appt.start_time if appt else None,
            "status": appt.status if appt else None,
        },
    }
    if include_prescriptions:
        data["prescriptions"] = [_prescription_json(p) for p in consultation.prescriptions]
    return data


@router.post("", response_model=ApiResponse[dict])
async def create_consultation(
    payload: ConsultationCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    appointment = db.get(Appointment, payload.appointment_id)
    if not appointment:
        raise NotFoundException("Appointment not found")
    if appointment.doctor_id != current_user.id:
        raise ForbiddenException("You can only create consultations for your own appointments")
    if appointment.status != "COMPLETED":
        raise ValidationException(
            "Consultations can only be created for completed appointments",
            details={"appointment_id": appointment.id, "appointment_status": appointment.status},
        )
    existing = db.query(Consultation).filter(Consultation.appointment_id == appointment.id).first()
    if existing:
        raise ConflictException("A consultation already exists for this appointment")

    consultation = Consultation(
        appointment_id=appointment.id,
        doctor_id=current_user.id,
        patient_id=appointment.patient_id,
        notes=payload.notes,
        diagnosis=payload.diagnosis,
        clinical_impression=payload.clinical_impression,
        symptoms=payload.symptoms,
        vital_signs=payload.vital_signs,
        recommended_tests=payload.recommended_tests,
        follow_up_date=payload.follow_up_date,
        follow_up_instructions=payload.follow_up_instructions,
        status="completed",
        completed_at=datetime.now(timezone.utc),
    )
    db.add(consultation)
    db.flush()

    add_timeline_event(
        db,
        appointment.patient_id,
        "consultation",
        "Consultation completed",
        description=(
            f"Consultation completed for the appointment on "
            f"{appointment.scheduled_date.isoformat()} with Dr. {current_user.full_name}"
        ),
        event_date=datetime.now(timezone.utc).date(),
        metadata_json=log_json({
            "appointment_id": appointment.id,
            "consultation_id": consultation.id,
            "doctor_id": current_user.id,
            "diagnosis": payload.diagnosis,
        }),
        appointment_id=appointment.id,
        consultation_id=consultation.id,
    )
    db.commit()
    db.refresh(consultation)

    write_audit_log(
        db, current_user, "consultations.create",
        resource_type="consultation", resource_id=str(consultation.id),
        request=request,
        after={
            "appointment_id": appointment.id,
            "patient_id": appointment.patient_id,
            "diagnosis": payload.diagnosis,
            "status": "completed",
        },
    )

    users, appointments = _load_context(db, [consultation])
    return ApiResponse(
        data=_consultation_json(consultation, users, appointments, include_prescriptions=True),
        message="Consultation created",
    )


@router.get("/my", response_model=PaginatedResponse)
async def my_consultations(
    status: Optional[str] = Query(None),
    patient_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient_doctor),
):
    query = db.query(Consultation)
    if current_user.role == UserRole.DOCTOR:
        query = query.filter(Consultation.doctor_id == current_user.id)
        if patient_id is not None:
            query = query.filter(Consultation.patient_id == patient_id)
    else:
        query = query.filter(Consultation.patient_id == current_user.id)

    if status:
        query = query.filter(Consultation.status == status)
    if date_from:
        query = query.filter(func.date(Consultation.completed_at) >= date_from)
    if date_to:
        query = query.filter(func.date(Consultation.completed_at) <= date_to)

    total = query.count()
    consultations = (
        query.order_by(Consultation.completed_at.desc().nullslast())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    users, appointments = _load_context(db, consultations)
    items = [_consultation_json(c, users, appointments) for c in consultations]
    return PaginatedResponse(
        data=PaginatedData(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        ),
        message="Consultations retrieved",
    )


@router.get("/doctor-overview", response_model=ApiResponse[dict])
async def doctor_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    base = db.query(Consultation).filter(Consultation.doctor_id == current_user.id)
    total = base.count()
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = base.filter(Consultation.completed_at >= today_start).count()
    distinct_patients = (
        db.query(func.count(func.distinct(Consultation.patient_id)))
        .filter(Consultation.doctor_id == current_user.id)
        .scalar()
        or 0
    )
    return ApiResponse(
        data={
            "total_consultations": total,
            "today_consultations": today_count,
            "distinct_patients": distinct_patients,
        },
        message="Consultation overview retrieved",
    )


@router.get("/{consultation_id}", response_model=ApiResponse[dict])
async def get_consultation(
    consultation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient_doctor),
):
    consultation = _get_consultation_for_user(db, consultation_id, current_user)
    users, appointments = _load_context(db, [consultation])
    return ApiResponse(
        data=_consultation_json(consultation, users, appointments, include_prescriptions=True),
        message="Consultation retrieved",
    )


@router.put("/{consultation_id}", response_model=ApiResponse[dict])
async def update_consultation(
    consultation_id: int,
    payload: ConsultationUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    consultation = _get_doctor_consultation(db, consultation_id, current_user)

    before = {
        "notes": consultation.notes,
        "diagnosis": consultation.diagnosis,
        "clinical_impression": consultation.clinical_impression,
        "symptoms": consultation.symptoms,
        "vital_signs": consultation.vital_signs,
        "recommended_tests": consultation.recommended_tests,
        "follow_up_date": consultation.follow_up_date.isoformat() if consultation.follow_up_date else None,
        "follow_up_instructions": consultation.follow_up_instructions,
    }
    updates = payload.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        setattr(consultation, field_name, value)

    db.commit()
    db.refresh(consultation)
    write_audit_log(
        db, current_user, "consultations.update",
        resource_type="consultation", resource_id=str(consultation.id),
        request=request, before=before,
        after={k: _json_ready(v) for k, v in updates.items()},
    )
    users, appointments = _load_context(db, [consultation])
    return ApiResponse(
        data=_consultation_json(consultation, users, appointments, include_prescriptions=True),
        message="Consultation updated",
    )


@router.post("/{consultation_id}/prescriptions", response_model=ApiResponse[dict])
async def add_prescription(
    consultation_id: int,
    payload: PrescriptionCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    consultation = _get_doctor_consultation(db, consultation_id, current_user)

    prescription = Prescription(
        consultation_id=consultation.id,
        doctor_id=current_user.id,
        patient_id=consultation.patient_id,
        medicine_name=payload.medicine_name,
        dosage=payload.dosage,
        frequency=payload.frequency,
        duration_days=payload.duration_days,
        instructions=payload.instructions,
        refill_count=payload.refill_count,
        is_active=payload.is_active,
    )
    db.add(prescription)
    db.flush()

    add_timeline_event(
        db,
        consultation.patient_id,
        "prescription",
        "Prescription added",
        description=f"{payload.medicine_name} ({payload.dosage}) prescribed",
        event_date=datetime.now(timezone.utc).date(),
        metadata_json=log_json({
            "consultation_id": consultation.id,
            "medicine_name": payload.medicine_name,
            "dosage": payload.dosage,
            "frequency": payload.frequency,
        }),
        consultation_id=consultation.id,
        prescription_id=prescription.id,
    )
    db.commit()
    db.refresh(prescription)

    write_audit_log(
        db, current_user, "consultations.prescription_add",
        resource_type="prescription", resource_id=str(prescription.id),
        request=request,
        after={
            "consultation_id": consultation.id,
            "medicine_name": payload.medicine_name,
            "dosage": payload.dosage,
            "frequency": payload.frequency,
        },
    )
    return ApiResponse(data=_prescription_json(prescription), message="Prescription added")


@router.get("/{consultation_id}/prescriptions", response_model=ApiResponse[list[dict]])
async def list_prescriptions(
    consultation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient_doctor),
):
    consultation = _get_consultation_for_user(db, consultation_id, current_user)
    prescriptions = (
        db.query(Prescription)
        .filter(Prescription.consultation_id == consultation.id)
        .order_by(Prescription.created_at.desc())
        .all()
    )
    return ApiResponse(
        data=[_prescription_json(p) for p in prescriptions],
        message="Prescriptions retrieved",
    )


@router.delete("/prescriptions/{prescription_id}", response_model=ApiResponse[dict])
async def delete_prescription(
    prescription_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    prescription = db.get(Prescription, prescription_id)
    if not prescription:
        raise NotFoundException("Prescription not found")
    consultation = db.get(Consultation, prescription.consultation_id)
    if not consultation or consultation.doctor_id != current_user.id:
        raise ForbiddenException("You can only remove prescriptions from your own consultations")

    before = {"medicine_name": prescription.medicine_name, "is_active": prescription.is_active}
    prescription.is_active = False
    db.commit()
    db.refresh(prescription)

    write_audit_log(
        db, current_user, "consultations.prescription_delete",
        resource_type="prescription", resource_id=str(prescription_id),
        request=request, before=before, after={"is_active": False},
    )
    return ApiResponse(data=_prescription_json(prescription), message="Prescription deactivated")