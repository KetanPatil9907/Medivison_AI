"""Patient self-service endpoints. All routes are patient-scoped: every
record lookup validates ownership against the authenticated user before any
data is returned or mutated. No patient may read or modify another patient's
or another family profile's records."""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, require_patient
from app.core.database import get_db
from app.core.exceptions import NotFoundException, ValidationException
from app.models import (
    Appointment,
    EmergencyContact,
    FamilyProfile,
    HealthMetric,
    HealthScore,
    MedicalHistory,
    PatientProfile,
    User,
)
from app.schemas.common import ApiResponse
from app.services.timeline_service import add_timeline_event, log_json
from app.utils.audit import write_audit_log

router = APIRouter(prefix="/patients", tags=["patients"])

MY_METRIC_TYPES = "^(weight|bp|blood_sugar|heart_rate|sleep|activity|bmi|water_intake)$"
FAMILY_RELATIONSHIPS = "^(parent|child|elderly|spouse|other)$"
HISTORY_STATUSES = "^(active|resolved|managed)$"


def _get_or_create_profile(db: Session, user: User) -> PatientProfile:
    profile = user.patient_profile
    if profile is None:
        profile = PatientProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def _get_own_family_profile(db: Session, profile: PatientProfile, family_id: int) -> FamilyProfile:
    family = db.get(FamilyProfile, family_id)
    if not family or family.patient_profile_id != profile.id:
        raise NotFoundException("Family profile not found")
    return family


def _can_access_history(db: Session, profile: PatientProfile, history: MedicalHistory) -> bool:
    if history.patient_profile_id == profile.id and history.family_profile_id is None:
        return True
    if history.family_profile_id is not None:
        family = db.get(FamilyProfile, history.family_profile_id)
        return family is not None and family.patient_profile_id == profile.id
    return False


def _get_own_metric(db: Session, profile: PatientProfile, metric_id: int) -> HealthMetric:
    metric = db.get(HealthMetric, metric_id)
    if not metric or metric.patient_profile_id != profile.id or metric.family_profile_id is not None:
        raise NotFoundException("Health metric not found")
    return metric


def _validate_bp_metric(metric_type: str, systolic: Optional[float], diastolic: Optional[float]) -> None:
    if metric_type == "bp" and (systolic is None or diastolic is None):
        raise ValidationException(
            "Systolic and diastolic values are required for blood pressure",
            details={"metric_type": metric_type, "systolic": systolic, "diastolic": diastolic},
        )


def _resolve_age(profile: Optional[PatientProfile]) -> Optional[int]:
    if not profile:
        return None
    if profile.age is not None:
        return profile.age
    if profile.date_of_birth is None:
        return None
    today = date.today()
    dob = profile.date_of_birth
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _calc_bmi(profile: Optional[PatientProfile]) -> Optional[float]:
    if not profile or not profile.weight_kg or not profile.height_cm or profile.height_cm <= 0:
        return None
    return round(profile.weight_kg * 10000 / (profile.height_cm ** 2), 2)


def _json_ready(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _audit_updates(updates: dict) -> dict:
    return {k: _json_ready(v) for k, v in updates.items()}


def _latest_metric(db: Session, profile_id: int, metric_type: str) -> Optional[HealthMetric]:
    return (
        db.query(HealthMetric)
        .filter(
            HealthMetric.patient_profile_id == profile_id,
            HealthMetric.metric_type == metric_type,
            HealthMetric.family_profile_id.is_(None),
        )
        .order_by(HealthMetric.recorded_date.desc(), HealthMetric.id.desc())
        .first()
    )


class UserInfoOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    profile_image_url: Optional[str] = None


class PatientProfileOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    user_id: int
    date_of_birth: Optional[date] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    family_history: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    emergency_contact_alt_phone: Optional[str] = None
    activity_level: Optional[str] = None
    dietary_preference: Optional[str] = None
    health_goal: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProfileOut(BaseModel):
    profile: PatientProfileOut
    user: UserInfoOut


class ProfileUpdateRequest(BaseModel):
    date_of_birth: Optional[date] = None
    age: Optional[int] = Field(default=None, ge=0, le=150)
    gender: Optional[str] = Field(default=None, min_length=1, max_length=20)
    blood_group: Optional[str] = Field(default=None, min_length=1, max_length=5)
    height_cm: Optional[float] = Field(default=None, ge=50, le=250)
    weight_kg: Optional[float] = Field(default=None, ge=2, le=400)
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    family_history: Optional[str] = None
    city: Optional[str] = Field(default=None, max_length=120)
    state: Optional[str] = Field(default=None, max_length=120)
    country: Optional[str] = Field(default=None, max_length=60)
    emergency_contact_name: Optional[str] = Field(default=None, max_length=150)
    emergency_contact_phone: Optional[str] = Field(default=None, max_length=20)
    emergency_contact_relation: Optional[str] = Field(default=None, max_length=50)
    emergency_contact_alt_phone: Optional[str] = Field(default=None, max_length=20)
    activity_level: Optional[str] = Field(default=None, pattern="^(sedentary|light|moderate|active|very_active)$")
    dietary_preference: Optional[str] = Field(default=None, pattern="^(vegetarian|non_vegetarian|vegan)$")
    health_goal: Optional[str] = Field(default=None, max_length=120)


class MetricOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    metric_type: str
    value: float
    unit: Optional[str] = None
    systolic: Optional[float] = None
    diastolic: Optional[float] = None
    source: Optional[str] = None
    recorded_date: date
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class MetricCreateRequest(BaseModel):
    metric_type: str = Field(pattern=MY_METRIC_TYPES)
    value: float
    unit: Optional[str] = Field(default=None, max_length=20)
    systolic: Optional[float] = None
    diastolic: Optional[float] = None
    recorded_date: date
    source: Optional[str] = Field(default="manual", pattern="^(manual|device|ai_estimated)$")
    notes: Optional[str] = None


class MetricUpdateRequest(BaseModel):
    metric_type: Optional[str] = Field(default=None, pattern=MY_METRIC_TYPES)
    value: Optional[float] = None
    unit: Optional[str] = Field(default=None, max_length=20)
    systolic: Optional[float] = None
    diastolic: Optional[float] = None
    recorded_date: Optional[date] = None
    source: Optional[str] = Field(default=None, pattern="^(manual|device|ai_estimated)$")
    notes: Optional[str] = None


class EmergencyContactOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    phone: str
    relation: str
    is_primary: bool


class EmergencyContactCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    phone: str = Field(min_length=1, max_length=20)
    relation: str = Field(min_length=1, max_length=50)
    is_primary: bool = False


class MedicalHistoryOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    patient_profile_id: Optional[int] = None
    family_profile_id: Optional[int] = None
    condition_name: str
    diagnosed_at: Optional[date] = None
    status: str
    severity: Optional[str] = None
    treatment: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MedicalHistoryCreateRequest(BaseModel):
    family_profile_id: Optional[int] = None
    condition_name: str = Field(min_length=1, max_length=200)
    diagnosed_at: Optional[date] = None
    status: str = Field(default="active", pattern=HISTORY_STATUSES)
    severity: Optional[str] = Field(default=None, max_length=30)
    treatment: Optional[str] = None
    notes: Optional[str] = None


class MedicalHistoryUpdateRequest(BaseModel):
    family_profile_id: Optional[int] = None
    condition_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    diagnosed_at: Optional[date] = None
    status: Optional[str] = Field(default=None, pattern=HISTORY_STATUSES)
    severity: Optional[str] = Field(default=None, max_length=30)
    treatment: Optional[str] = None
    notes: Optional[str] = None


class FamilyProfileOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    relationship: str
    age: Optional[int] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    created_at: Optional[datetime] = None


class FamilyProfileDetail(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    relationship: str
    age: Optional[int] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    medical_history: Optional[str] = None
    medications: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class FamilyProfileCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    relationship: str = Field(pattern=FAMILY_RELATIONSHIPS)
    age: Optional[int] = Field(default=None, ge=0, le=150)
    gender: Optional[str] = Field(default=None, max_length=20)
    blood_group: Optional[str] = Field(default=None, max_length=5)
    height_cm: Optional[float] = Field(default=None, ge=50, le=250)
    weight_kg: Optional[float] = Field(default=None, ge=2, le=400)
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    medical_history: Optional[str] = None
    medications: Optional[str] = None
    notes: Optional[str] = None


class FamilyProfileUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    relationship: Optional[str] = Field(default=None, pattern=FAMILY_RELATIONSHIPS)
    age: Optional[int] = Field(default=None, ge=0, le=150)
    gender: Optional[str] = Field(default=None, max_length=20)
    blood_group: Optional[str] = Field(default=None, max_length=5)
    height_cm: Optional[float] = Field(default=None, ge=50, le=250)
    weight_kg: Optional[float] = Field(default=None, ge=2, le=400)
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    medical_history: Optional[str] = None
    medications: Optional[str] = None
    notes: Optional[str] = None


class PatientSummaryOut(BaseModel):
    age: Optional[int] = None
    bmi: Optional[float] = None
    latest_weight: Optional[dict] = None
    latest_bp: Optional[dict] = None
    latest_blood_sugar: Optional[dict] = None
    latest_health_score: Optional[dict] = None
    upcoming_appointments: int = 0


@router.get("/me/profile", response_model=ApiResponse[ProfileOut])
async def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    profile = _get_or_create_profile(db, current_user)
    return ApiResponse(
        data={
            "profile": PatientProfileOut.model_validate(profile),
            "user": UserInfoOut.model_validate(current_user),
        },
        message="Patient profile retrieved",
    )


@router.put("/me/profile", response_model=ApiResponse[ProfileOut])
async def update_my_profile(
    payload: ProfileUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    profile = _get_or_create_profile(db, current_user)
    before = {
        "date_of_birth": profile.date_of_birth.isoformat() if profile.date_of_birth else None,
        "age": profile.age,
        "gender": profile.gender,
        "blood_group": profile.blood_group,
        "height_cm": profile.height_cm,
        "weight_kg": profile.weight_kg,
        "allergies": profile.allergies,
        "chronic_conditions": profile.chronic_conditions,
        "city": profile.city,
        "state": profile.state,
        "activity_level": profile.activity_level,
        "dietary_preference": profile.dietary_preference,
        "health_goal": profile.health_goal,
    }

    updates = payload.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        setattr(profile, field_name, value)

    db.commit()
    db.refresh(profile)

    add_timeline_event(
        db,
        current_user.id,
        "health_event",
        "Profile updated",
        description="Patient health profile was updated",
        event_date=datetime.now(timezone.utc).date(),
        metadata_json=log_json({"fields": sorted(updates.keys())}),
    )
    write_audit_log(
        db, current_user, "patients.profile_update",
        resource_type="patient_profile", resource_id=str(profile.id),
        request=request, before=before, after=_audit_updates(updates),
    )

    return ApiResponse(
        data={
            "profile": PatientProfileOut.model_validate(profile),
            "user": UserInfoOut.model_validate(current_user),
        },
        message="Profile updated successfully",
    )


@router.get("/me/health-metrics", response_model=ApiResponse[list[MetricOut]])
async def list_health_metrics(
    metric_type: Optional[str] = Query(None, pattern=MY_METRIC_TYPES),
    days: int = Query(30, ge=1, le=3650),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    profile = _get_or_create_profile(db, current_user)
    query = db.query(HealthMetric).filter(
        HealthMetric.patient_profile_id == profile.id,
        HealthMetric.family_profile_id.is_(None),
        HealthMetric.recorded_date >= date.today() - timedelta(days=days),
    )
    if metric_type:
        query = query.filter(HealthMetric.metric_type == metric_type)
    metrics = query.order_by(HealthMetric.recorded_date.desc(), HealthMetric.id.desc()).all()
    return ApiResponse(
        data=[MetricOut.model_validate(m) for m in metrics],
        message="Health metrics retrieved",
    )


@router.post("/me/health-metrics", response_model=ApiResponse[MetricOut])
async def create_health_metric(
    payload: MetricCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    _validate_bp_metric(payload.metric_type, payload.systolic, payload.diastolic)
    profile = _get_or_create_profile(db, current_user)

    metric = HealthMetric(
        patient_profile_id=profile.id,
        metric_type=payload.metric_type,
        value=payload.value,
        unit=payload.unit,
        systolic=payload.systolic,
        diastolic=payload.diastolic,
        source=payload.source or "manual",
        recorded_date=payload.recorded_date,
        notes=payload.notes,
    )
    db.add(metric)
    db.flush()

    detail = {
        "metric_type": payload.metric_type,
        "value": payload.value,
        "unit": payload.unit,
    }
    if payload.metric_type == "bp":
        detail.update(systolic=payload.systolic, diastolic=payload.diastolic)

    add_timeline_event(
        db,
        current_user.id,
        "metric",
        "Health metric recorded",
        description=f"{payload.metric_type}: {payload.value}{' ' + payload.unit if payload.unit else ''} recorded",
        event_date=payload.recorded_date,
        metadata_json=log_json(detail),
    )
    db.commit()

    write_audit_log(
        db, current_user, "patients.metric_create",
        resource_type="health_metric", resource_id=str(metric.id),
        request=request, after=detail,
    )

    return ApiResponse(data=MetricOut.model_validate(metric), message="Health metric recorded")


@router.put("/me/health-metrics/{metric_id}", response_model=ApiResponse[MetricOut])
async def update_health_metric(
    metric_id: int,
    payload: MetricUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    profile = _get_or_create_profile(db, current_user)
    metric = _get_own_metric(db, profile, metric_id)

    updates = payload.model_dump(exclude_unset=True)
    new_type = updates.get("metric_type", metric.metric_type)
    new_systolic = updates.get("systolic", metric.systolic)
    new_diastolic = updates.get("diastolic", metric.diastolic)
    _validate_bp_metric(new_type, new_systolic, new_diastolic)

    before = {
        "metric_type": metric.metric_type,
        "value": metric.value,
        "unit": metric.unit,
        "systolic": metric.systolic,
        "diastolic": metric.diastolic,
        "recorded_date": metric.recorded_date.isoformat() if metric.recorded_date else None,
        "source": metric.source,
        "notes": metric.notes,
    }
    for field_name, value in updates.items():
        setattr(metric, field_name, value)

    db.commit()
    db.refresh(metric)
    write_audit_log(
        db, current_user, "patients.metric_update",
        resource_type="health_metric", resource_id=str(metric.id),
        request=request, before=before, after=_audit_updates(updates),
    )
    return ApiResponse(data=MetricOut.model_validate(metric), message="Health metric updated")


@router.delete("/me/health-metrics/{metric_id}", response_model=ApiResponse[dict])
async def delete_health_metric(
    metric_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    profile = _get_or_create_profile(db, current_user)
    metric = _get_own_metric(db, profile, metric_id)
    before = {
        "metric_type": metric.metric_type,
        "value": metric.value,
        "recorded_date": metric.recorded_date.isoformat() if metric.recorded_date else None,
    }
    db.delete(metric)
    db.commit()
    write_audit_log(
        db, current_user, "patients.metric_delete",
        resource_type="health_metric", resource_id=str(metric_id),
        request=request, before=before,
    )
    return ApiResponse(message="Health metric deleted")


@router.get("/me/emergency-contacts", response_model=ApiResponse[list[EmergencyContactOut]])
async def list_emergency_contacts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    profile = _get_or_create_profile(db, current_user)
    contacts = (
        db.query(EmergencyContact)
        .filter(EmergencyContact.patient_profile_id == profile.id)
        .order_by(EmergencyContact.is_primary.desc(), EmergencyContact.created_at.asc())
        .all()
    )
    return ApiResponse(
        data=[EmergencyContactOut.model_validate(c) for c in contacts],
        message="Emergency contacts retrieved",
    )


@router.post("/me/emergency-contacts", response_model=ApiResponse[EmergencyContactOut])
async def create_emergency_contact(
    payload: EmergencyContactCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    profile = _get_or_create_profile(db, current_user)
    if payload.is_primary:
        db.query(EmergencyContact).filter(
            EmergencyContact.patient_profile_id == profile.id,
            EmergencyContact.is_primary.is_(True),
        ).update({EmergencyContact.is_primary: False}, synchronize_session=False)

    contact = EmergencyContact(
        patient_profile_id=profile.id,
        name=payload.name,
        phone=payload.phone,
        relation=payload.relation,
        is_primary=payload.is_primary,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    write_audit_log(
        db, current_user, "patients.emergency_contact_create",
        resource_type="emergency_contact", resource_id=str(contact.id),
        request=request,
        after={"name": contact.name, "phone": contact.phone, "relation": contact.relation, "is_primary": contact.is_primary},
    )
    return ApiResponse(data=EmergencyContactOut.model_validate(contact), message="Emergency contact added")


@router.delete("/me/emergency-contacts/{contact_id}", response_model=ApiResponse[dict])
async def delete_emergency_contact(
    contact_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    profile = _get_or_create_profile(db, current_user)
    contact = db.get(EmergencyContact, contact_id)
    if not contact or contact.patient_profile_id != profile.id:
        raise NotFoundException("Emergency contact not found")
    before = {"name": contact.name, "phone": contact.phone, "is_primary": contact.is_primary}
    db.delete(contact)
    db.commit()
    write_audit_log(
        db, current_user, "patients.emergency_contact_delete",
        resource_type="emergency_contact", resource_id=str(contact_id),
        request=request, before=before,
    )
    return ApiResponse(message="Emergency contact deleted")


@router.get("/me/medical-history", response_model=ApiResponse[list[MedicalHistoryOut]])
async def list_medical_history(
    family_profile_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    profile = _get_or_create_profile(db, current_user)
    query = db.query(MedicalHistory)
    if family_profile_id is not None:
        family = _get_own_family_profile(db, profile, family_profile_id)
        query = query.filter(MedicalHistory.family_profile_id == family.id)
    else:
        query = query.filter(
            MedicalHistory.patient_profile_id == profile.id,
            MedicalHistory.family_profile_id.is_(None),
        )
    histories = query.order_by(MedicalHistory.created_at.desc()).all()
    return ApiResponse(
        data=[MedicalHistoryOut.model_validate(h) for h in histories],
        message="Medical history retrieved",
    )


@router.post("/me/medical-history", response_model=ApiResponse[MedicalHistoryOut])
async def add_medical_history(
    payload: MedicalHistoryCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    profile = _get_or_create_profile(db, current_user)
    family_profile_id = None
    patient_profile_id = profile.id
    if payload.family_profile_id is not None:
        family = _get_own_family_profile(db, profile, payload.family_profile_id)
        family_profile_id = family.id
        patient_profile_id = None

    history = MedicalHistory(
        patient_profile_id=patient_profile_id,
        family_profile_id=family_profile_id,
        condition_name=payload.condition_name,
        diagnosed_at=payload.diagnosed_at,
        status=payload.status,
        severity=payload.severity,
        treatment=payload.treatment,
        notes=payload.notes,
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    write_audit_log(
        db, current_user, "patients.medical_history_create",
        resource_type="medical_history", resource_id=str(history.id),
        request=request,
        after={
            "condition_name": history.condition_name,
            "diagnosed_at": history.diagnosed_at.isoformat() if history.diagnosed_at else None,
            "status": history.status,
            "severity": history.severity,
            "family_profile_id": history.family_profile_id,
        },
    )
    return ApiResponse(data=MedicalHistoryOut.model_validate(history), message="Medical history added")


@router.patch("/me/medical-history/{history_id}", response_model=ApiResponse[MedicalHistoryOut])
async def update_medical_history(
    history_id: int,
    payload: MedicalHistoryUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    profile = _get_or_create_profile(db, current_user)
    history = db.get(MedicalHistory, history_id)
    if not history or not _can_access_history(db, profile, history):
        raise NotFoundException("Medical history not found")

    before = {
        "condition_name": history.condition_name,
        "diagnosed_at": history.diagnosed_at.isoformat() if history.diagnosed_at else None,
        "status": history.status,
        "severity": history.severity,
        "treatment": history.treatment,
        "notes": history.notes,
        "family_profile_id": history.family_profile_id,
    }

    updates = payload.model_dump(exclude_unset=True)
    if "family_profile_id" in updates:
        new_family_id = updates["family_profile_id"]
        if new_family_id is not None:
            family = _get_own_family_profile(db, profile, new_family_id)
            updates["family_profile_id"] = family.id
            updates["patient_profile_id"] = None
        else:
            updates["family_profile_id"] = None
            updates["patient_profile_id"] = profile.id

    for field_name, value in updates.items():
        setattr(history, field_name, value)

    db.commit()
    db.refresh(history)
    write_audit_log(
        db, current_user, "patients.medical_history_update",
        resource_type="medical_history", resource_id=str(history.id),
        request=request, before=before, after=_audit_updates(updates),
    )
    return ApiResponse(data=MedicalHistoryOut.model_validate(history), message="Medical history updated")


@router.delete("/me/medical-history/{history_id}", response_model=ApiResponse[dict])
async def delete_medical_history(
    history_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    profile = _get_or_create_profile(db, current_user)
    history = db.get(MedicalHistory, history_id)
    if not history or not _can_access_history(db, profile, history):
        raise NotFoundException("Medical history not found")
    before = {"condition_name": history.condition_name, "status": history.status}
    db.delete(history)
    db.commit()
    write_audit_log(
        db, current_user, "patients.medical_history_delete",
        resource_type="medical_history", resource_id=str(history_id),
        request=request, before=before,
    )
    return ApiResponse(message="Medical history deleted")


@router.get("/me/family-profiles", response_model=ApiResponse[list[FamilyProfileOut]])
async def list_family_profiles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    profile = _get_or_create_profile(db, current_user)
    families = (
        db.query(FamilyProfile)
        .filter(FamilyProfile.patient_profile_id == profile.id)
        .order_by(FamilyProfile.created_at.desc())
        .all()
    )
    return ApiResponse(
        data=[FamilyProfileOut.model_validate(f) for f in families],
        message="Family profiles retrieved",
    )


@router.post("/me/family-profiles", response_model=ApiResponse[FamilyProfileDetail])
async def create_family_profile(
    payload: FamilyProfileCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    profile = _get_or_create_profile(db, current_user)
    family = FamilyProfile(
        patient_profile_id=profile.id,
        name=payload.name,
        relationship=payload.relationship,
        age=payload.age,
        gender=payload.gender,
        blood_group=payload.blood_group,
        height_cm=payload.height_cm,
        weight_kg=payload.weight_kg,
        allergies=payload.allergies,
        chronic_conditions=payload.chronic_conditions,
        medical_history=payload.medical_history,
        medications=payload.medications,
        notes=payload.notes,
    )
    db.add(family)
    db.commit()
    db.refresh(family)
    write_audit_log(
        db, current_user, "patients.family_profile_create",
        resource_type="family_profile", resource_id=str(family.id),
        request=request, after={"name": family.name, "relationship": family.relationship},
    )
    return ApiResponse(data=FamilyProfileDetail.model_validate(family), message="Family profile created")


@router.get("/me/family-profiles/{family_id}", response_model=ApiResponse[FamilyProfileDetail])
async def get_family_profile(
    family_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    profile = _get_or_create_profile(db, current_user)
    family = _get_own_family_profile(db, profile, family_id)
    return ApiResponse(data=FamilyProfileDetail.model_validate(family), message="Family profile retrieved")


@router.put("/me/family-profiles/{family_id}", response_model=ApiResponse[FamilyProfileDetail])
async def update_family_profile(
    family_id: int,
    payload: FamilyProfileUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    profile = _get_or_create_profile(db, current_user)
    family = _get_own_family_profile(db, profile, family_id)

    before = {
        "name": family.name,
        "relationship": family.relationship,
        "age": family.age,
        "gender": family.gender,
        "blood_group": family.blood_group,
        "height_cm": family.height_cm,
        "weight_kg": family.weight_kg,
    }
    updates = payload.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        setattr(family, field_name, value)

    db.commit()
    db.refresh(family)
    write_audit_log(
        db, current_user, "patients.family_profile_update",
        resource_type="family_profile", resource_id=str(family.id),
        request=request, before=before, after=_audit_updates(updates),
    )
    return ApiResponse(data=FamilyProfileDetail.model_validate(family), message="Family profile updated")


@router.delete("/me/family-profiles/{family_id}", response_model=ApiResponse[dict])
async def delete_family_profile(
    family_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    profile = _get_or_create_profile(db, current_user)
    family = _get_own_family_profile(db, profile, family_id)
    before = {"name": family.name, "relationship": family.relationship}
    db.delete(family)
    db.commit()
    write_audit_log(
        db, current_user, "patients.family_profile_delete",
        resource_type="family_profile", resource_id=str(family_id),
        request=request, before=before,
    )
    return ApiResponse(message="Family profile deleted")


@router.get("/me/family-profiles/{family_id}/health-metrics", response_model=ApiResponse[list[MetricOut]])
async def list_family_health_metrics(
    family_id: int,
    metric_type: Optional[str] = Query(None, pattern=MY_METRIC_TYPES),
    days: int = Query(30, ge=1, le=3650),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    profile = _get_or_create_profile(db, current_user)
    family = _get_own_family_profile(db, profile, family_id)
    query = db.query(HealthMetric).filter(
        HealthMetric.family_profile_id == family.id,
        HealthMetric.recorded_date >= date.today() - timedelta(days=days),
    )
    if metric_type:
        query = query.filter(HealthMetric.metric_type == metric_type)
    metrics = query.order_by(HealthMetric.recorded_date.desc(), HealthMetric.id.desc()).all()
    return ApiResponse(
        data=[MetricOut.model_validate(m) for m in metrics],
        message="Family member health metrics retrieved",
    )


@router.post("/me/family-profiles/{family_id}/health-metrics", response_model=ApiResponse[MetricOut])
async def create_family_health_metric(
    family_id: int,
    payload: MetricCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    _validate_bp_metric(payload.metric_type, payload.systolic, payload.diastolic)
    profile = _get_or_create_profile(db, current_user)
    family = _get_own_family_profile(db, profile, family_id)

    metric = HealthMetric(
        family_profile_id=family.id,
        metric_type=payload.metric_type,
        value=payload.value,
        unit=payload.unit,
        systolic=payload.systolic,
        diastolic=payload.diastolic,
        source=payload.source or "manual",
        recorded_date=payload.recorded_date,
        notes=payload.notes,
    )
    db.add(metric)
    db.flush()

    add_timeline_event(
        db,
        current_user.id,
        "metric",
        "Health metric recorded",
        description=f"{payload.metric_type}: {payload.value}{' ' + payload.unit if payload.unit else ''} recorded for {family.name}",
        event_date=payload.recorded_date,
        metadata_json=log_json({
            "metric_type": payload.metric_type,
            "value": payload.value,
            "unit": payload.unit,
            "family_profile_id": family.id,
        }),
        family_profile_id=family.id,
    )
    db.commit()

    write_audit_log(
        db, current_user, "patients.family_metric_create",
        resource_type="health_metric", resource_id=str(metric.id),
        request=request,
        after={"metric_type": payload.metric_type, "value": payload.value, "family_profile_id": family.id},
    )
    return ApiResponse(data=MetricOut.model_validate(metric), message="Family member health metric recorded")


@router.get("/me/summary", response_model=ApiResponse[PatientSummaryOut])
async def get_my_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    profile = _get_or_create_profile(db, current_user)
    today = date.today()

    weight = _latest_metric(db, profile.id, "weight")
    bp = _latest_metric(db, profile.id, "bp")
    blood_sugar = _latest_metric(db, profile.id, "blood_sugar")

    score = (
        db.query(HealthScore)
        .filter(HealthScore.patient_id == current_user.id)
        .order_by(HealthScore.recorded_date.desc(), HealthScore.id.desc())
        .first()
    )
    upcoming = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == current_user.id,
            Appointment.scheduled_date >= today,
            Appointment.status.in_(["BOOKED", "CONFIRMED", "RESCHEDULED"]),
        )
        .count()
    )

    def _metric_snapshot(m: Optional[HealthMetric]) -> Optional[dict]:
        if not m:
            return None
        snap = {
            "value": m.value,
            "unit": m.unit,
            "recorded_date": m.recorded_date.isoformat(),
        }
        if m.metric_type == "bp":
            snap.update(systolic=m.systolic, diastolic=m.diastolic)
        return snap

    return ApiResponse(
        data=PatientSummaryOut(
            age=_resolve_age(profile),
            bmi=_calc_bmi(profile),
            latest_weight=_metric_snapshot(weight),
            latest_bp=_metric_snapshot(bp),
            latest_blood_sugar=_metric_snapshot(blood_sugar),
            latest_health_score={
                "score": score.score,
                "previous_score": score.previous_score,
                "recorded_date": score.recorded_date.isoformat(),
            } if score else None,
            upcoming_appointments=upcoming,
        ),
        message="Patient summary retrieved",
    )