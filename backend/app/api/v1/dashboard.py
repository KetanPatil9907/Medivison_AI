"""Role-aware dashboard endpoint for the MediVision AI platform.

GET /dashboard returns a role-specific aggregate view:
- PATIENT: health score, overview card counts, next appointment, recent timeline,
  latest AI insights and 30-day trend punchcards for Recharts.
- DOCTOR: today's schedule, practice stats, upcoming appointments, recent activity.
- ADMIN: platform stats, pending applications, user growth, appointment trends
  and AI usage over the last 14-30 days.
"""

import logging
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import AppException
from app.models import (
    Appointment,
    Consultation,
    DoctorApplication,
    HealthMetric,
    HealthScore,
    HealthTimeline,
    ImageAnalysis,
    Medication,
    MedicalReport,
    PreventiveReminder,
    RiskAssessment,
    SymptomSession,
    User,
    UserRole,
    UserStatus,
)
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

logger = logging.getLogger("medivision.api.dashboard")

ACTIVE_STATUSES = ("BOOKED", "CONFIRMED", "RESCHEDULED")
TREND_METRICS = ("weight", "heart_rate", "blood_sugar")


def _load_users(db: Session, user_ids: list[int]) -> dict[int, User]:
    ids = {uid for uid in user_ids if uid is not None}
    if not ids:
        return {}
    users = db.query(User).filter(User.id.in_(ids)).all()
    return {u.id: u for u in users}


def _latest_metric(db: Session, profile_id: int | None, metric_type: str) -> HealthMetric | None:
    if profile_id is None:
        return None
    return (
        db.query(HealthMetric)
        .filter(
            HealthMetric.patient_profile_id == profile_id,
            HealthMetric.family_profile_id.is_(None),
            HealthMetric.metric_type == metric_type,
        )
        .order_by(HealthMetric.recorded_date.desc(), HealthMetric.id.desc())
        .first()
    )


def _metric_series(db: Session, profile_id: int | None, metric_type: str, cutoff: date) -> list[dict]:
    if profile_id is None:
        return []
    rows = (
        db.query(HealthMetric)
        .filter(
            HealthMetric.patient_profile_id == profile_id,
            HealthMetric.family_profile_id.is_(None),
            HealthMetric.metric_type == metric_type,
            HealthMetric.recorded_date >= cutoff,
        )
        .order_by(HealthMetric.recorded_date.desc(), HealthMetric.id.desc())
        .limit(30)
        .all()
    )
    return [{"date": m.recorded_date.isoformat(), "value": m.value} for m in reversed(rows)]


def _patient_payload(db: Session, user: User) -> dict:
    today = date.today()
    profile = user.patient_profile
    profile_id = profile.id if profile else None

    score = (
        db.query(HealthScore)
        .filter(HealthScore.patient_id == user.id)
        .order_by(HealthScore.recorded_date.desc(), HealthScore.id.desc())
        .first()
    )

    upcoming_count = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == user.id,
            Appointment.scheduled_date >= today,
            Appointment.status.in_(ACTIVE_STATUSES),
        )
        .count()
    )
    completed_count = (
        db.query(Appointment)
        .filter(Appointment.patient_id == user.id, Appointment.status == "COMPLETED")
        .count()
    )
    medications_count = (
        db.query(Medication)
        .filter(Medication.patient_id == user.id, Medication.status == "active")
        .count()
    )
    reminders_count = (
        db.query(PreventiveReminder)
        .filter(
            PreventiveReminder.patient_id == user.id,
            PreventiveReminder.status == "pending",
            PreventiveReminder.due_date >= today,
        )
        .count()
    )
    latest_weight = _latest_metric(db, profile_id, "weight")

    next_appointment = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == user.id,
            Appointment.scheduled_date >= today,
            Appointment.status.in_(ACTIVE_STATUSES),
        )
        .order_by(Appointment.scheduled_date.asc(), Appointment.start_time.asc())
        .first()
    )
    doctor = db.get(User, next_appointment.doctor_id) if next_appointment else None

    timeline = (
        db.query(HealthTimeline)
        .filter(HealthTimeline.patient_id == user.id, HealthTimeline.family_profile_id.is_(None))
        .order_by(HealthTimeline.event_date.desc(), HealthTimeline.id.desc())
        .limit(5)
        .all()
    )

    risk = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.patient_id == user.id)
        .order_by(RiskAssessment.created_at.desc(), RiskAssessment.id.desc())
        .first()
    )
    image = (
        db.query(ImageAnalysis)
        .filter(ImageAnalysis.patient_id == user.id)
        .order_by(ImageAnalysis.created_at.desc(), ImageAnalysis.id.desc())
        .first()
    )

    cutoff = today - timedelta(days=30)
    trends = {mt: _metric_series(db, profile_id, mt, cutoff) for mt in TREND_METRICS}

    return {
        "role": "PATIENT",
        "welcome": user.full_name,
        "health_score": {
            "score": score.score if score else None,
            "previous_score": score.previous_score if score else None,
            "recorded_date": score.recorded_date.isoformat() if score else None,
        },
        "overview_cards": {
            "upcoming_appointments": upcoming_count,
            "completed_appointments": completed_count,
            "active_medications": medications_count,
            "upcoming_reminders": reminders_count,
            "latest_weight": {
                "value": latest_weight.value,
                "unit": latest_weight.unit,
                "recorded_date": latest_weight.recorded_date.isoformat(),
            }
            if latest_weight
            else None,
        },
        "upcoming_appointment": {
            "date": next_appointment.scheduled_date.isoformat(),
            "start_time": next_appointment.start_time,
            "doctor_full_name": doctor.full_name if doctor else None,
            "specialization": doctor.doctor_profile.specialization if doctor and doctor.doctor_profile else None,
            "status": next_appointment.status,
            "hospital": doctor.doctor_profile.hospital if doctor and doctor.doctor_profile else None,
        }
        if next_appointment
        else None,
        "recent_timeline": [
            {
                "type": t.event_type,
                "title": t.title,
                "event_date": t.event_date.isoformat(),
                "severity": t.severity,
            }
            for t in timeline
        ],
        "ai_insights": {
            "risk_assessment": {
                "condition_type": risk.condition_type,
                "risk_level": risk.risk_level,
                "risk_percentage": risk.risk_percentage,
                "recorded_date": risk.created_at.isoformat() if risk.created_at else None,
            }
            if risk
            else None,
            "image_analysis": {
                "modality": image.modality,
                "prediction_label": image.prediction_label,
                "confidence": image.confidence,
                "recorded_date": image.created_at.isoformat() if image.created_at else None,
            }
            if image
            else None,
        },
        "trends": trends,
    }


def _doctor_payload(db: Session, user: User) -> dict:
    today = date.today()

    today_appts = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == user.id,
            Appointment.scheduled_date == today,
            Appointment.status != "CANCELLED",
        )
        .order_by(Appointment.start_time.asc())
        .all()
    )
    users = _load_users(db, [a.patient_id for a in today_appts])

    total_patients = (
        db.query(Appointment.patient_id).filter(Appointment.doctor_id == user.id).distinct().count()
    )
    completed_consultations = (
        db.query(Consultation)
        .filter(Consultation.doctor_id == user.id, Consultation.status == "completed")
        .count()
    )
    upcoming_count = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == user.id,
            Appointment.scheduled_date >= today,
            Appointment.status.in_(ACTIVE_STATUSES),
        )
        .count()
    )
    pending_requests = (
        db.query(Appointment)
        .filter(Appointment.doctor_id == user.id, Appointment.status == "BOOKED")
        .count()
    )

    next_appts = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == user.id,
            Appointment.scheduled_date >= today,
            Appointment.status.in_(ACTIVE_STATUSES),
        )
        .order_by(Appointment.scheduled_date.asc(), Appointment.start_time.asc())
        .limit(5)
        .all()
    )
    next_patients = _load_users(db, [a.patient_id for a in next_appts])

    recent = (
        db.query(Consultation)
        .filter(Consultation.doctor_id == user.id)
        .order_by(Consultation.created_at.desc(), Consultation.id.desc())
        .limit(10)
        .all()
    )
    recent_patients = _load_users(db, [c.patient_id for c in recent])

    def _patient_name(mapping: dict[int, User], patient_id: int) -> str | None:
        row = mapping.get(patient_id)
        return row.full_name if row else None

    return {
        "role": "DOCTOR",
        "today_schedule": [
            {
                "id": a.id,
                "start_time": a.start_time,
                "end_time": a.end_time,
                "patient_full_name": _patient_name(users, a.patient_id),
                "status": a.status,
                "queue_position": a.queue_position,
            }
            for a in today_appts
        ],
        "stats": {
            "total_patients": total_patients,
            "completed_consultations": completed_consultations,
            "upcoming": upcoming_count,
            "pending_requests": pending_requests,
        },
        "upcoming_appointments": [
            {
                "id": a.id,
                "scheduled_date": a.scheduled_date.isoformat(),
                "start_time": a.start_time,
                "end_time": a.end_time,
                "patient_full_name": _patient_name(next_patients, a.patient_id),
                "status": a.status,
                "consultation_type": a.consultation_type,
            }
            for a in next_appts
        ],
        "recent_activity": [
            {
                "id": c.id,
                "title": f"Consultation with {_patient_name(recent_patients, c.patient_id) or 'patient'}",
                "description": c.diagnosis or c.clinical_impression or c.notes,
                "patient_full_name": _patient_name(recent_patients, c.patient_id),
                "completed_at": c.completed_at.isoformat()
                if c.completed_at
                else (c.created_at.isoformat() if c.created_at else None),
            }
            for c in recent
        ],
    }


def _day_range(days: int) -> list[date]:
    today = date.today()
    start = today - timedelta(days=days - 1)
    return [start + timedelta(days=i) for i in range(days)]


def _to_utc_date(value: datetime | None) -> date | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).date()


def _counts_by_day(db: Session, model, start_dt: datetime) -> dict[date, int]:
    rows = db.query(model.created_at).filter(model.created_at >= start_dt).all()
    buckets: Counter = Counter()
    for (created_at,) in rows:
        day = _to_utc_date(created_at)
        if day is not None:
            buckets[day] += 1
    return dict(buckets)


def _cumulative_counts(dates: list[date], day_range: list[date]) -> list[int]:
    counts = []
    index = 0
    for day in day_range:
        while index < len(dates) and dates[index] <= day:
            index += 1
        counts.append(index)
    return counts


def _admin_payload(db: Session, user: User) -> dict:
    today = date.today()

    total_patients = (
        db.query(User).filter(User.role == UserRole.PATIENT, User.is_deleted.is_(False)).count()
    )
    total_doctors = (
        db.query(User).filter(User.role == UserRole.DOCTOR, User.is_deleted.is_(False)).count()
    )
    pending_applications = db.query(DoctorApplication).filter(DoctorApplication.status == "PENDING").count()
    approved_doctors = (
        db.query(User)
        .filter(
            User.role == UserRole.DOCTOR,
            User.status == UserStatus.ACTIVE,
            User.is_deleted.is_(False),
        )
        .count()
    )
    today_appointments = db.query(Appointment).filter(Appointment.scheduled_date == today).count()
    total_appointments = db.query(Appointment).count()
    total_ai_analyses = db.query(ImageAnalysis).count() + db.query(RiskAssessment).count()
    total_reports = db.query(MedicalReport).count()

    applications = (
        db.query(DoctorApplication)
        .filter(DoctorApplication.status == "PENDING")
        .order_by(DoctorApplication.created_at.desc())
        .limit(5)
        .all()
    )
    app_users = _load_users(db, [a.user_id for a in applications])

    growth_days = _day_range(30)
    member_rows = (
        db.query(User.role, User.created_at)
        .filter(
            User.is_deleted.is_(False),
            User.role.in_([UserRole.PATIENT, UserRole.DOCTOR]),
        )
        .all()
    )
    patient_dates: list[date] = []
    doctor_dates: list[date] = []
    for member_role, created_at in member_rows:
        day = _to_utc_date(created_at)
        if day is None:
            continue
        if member_role == UserRole.PATIENT:
            patient_dates.append(day)
        elif member_role == UserRole.DOCTOR:
            doctor_dates.append(day)
    patient_dates.sort()
    doctor_dates.sort()
    patient_cumulative = _cumulative_counts(patient_dates, growth_days)
    doctor_cumulative = _cumulative_counts(doctor_dates, growth_days)
    user_growth = [
        {"date": d.isoformat(), "patients": p, "doctors": doc}
        for d, p, doc in zip(growth_days, patient_cumulative, doctor_cumulative)
    ]

    trend_days = _day_range(14)
    appt_rows = (
        db.query(Appointment.scheduled_date, func.count(Appointment.id))
        .filter(Appointment.scheduled_date >= trend_days[0])
        .group_by(Appointment.scheduled_date)
        .all()
    )
    appt_counts = {scheduled_date: count for scheduled_date, count in appt_rows}
    appointment_trends = [
        {"date": d.isoformat(), "count": appt_counts.get(d, 0)} for d in trend_days
    ]

    start_dt = datetime(trend_days[0].year, trend_days[0].month, trend_days[0].day, tzinfo=timezone.utc)
    symptom_checks = _counts_by_day(db, SymptomSession, start_dt)
    risk_assessments = _counts_by_day(db, RiskAssessment, start_dt)
    image_analyses = _counts_by_day(db, ImageAnalysis, start_dt)
    ai_usage = [
        {
            "date": d.isoformat(),
            "symptom_checks": symptom_checks.get(d, 0),
            "risk_assessments": risk_assessments.get(d, 0),
            "image_analyses": image_analyses.get(d, 0),
        }
        for d in trend_days
    ]

    return {
        "role": "ADMIN",
        "stats": {
            "total_patients": total_patients,
            "total_doctors": total_doctors,
            "pending_applications": pending_applications,
            "approved_doctors": approved_doctors,
            "today_appointments": today_appointments,
            "total_appointments": total_appointments,
            "total_ai_analyses": total_ai_analyses,
            "total_reports": total_reports,
        },
        "pending_applications": [
            {
                "id": a.id,
                "user_id": a.user_id,
                "full_name": app_users.get(a.user_id).full_name if app_users.get(a.user_id) else None,
                "specialization": a.specialization,
                "submitted_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in applications
        ],
        "user_growth": user_growth,
        "appointment_trends": appointment_trends,
        "ai_usage": ai_usage,
    }


@router.get("", response_model=ApiResponse[dict])
async def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        if current_user.role == UserRole.PATIENT:
            data = _patient_payload(db, current_user)
            message = "Patient dashboard loaded"
        elif current_user.role == UserRole.DOCTOR:
            data = _doctor_payload(db, current_user)
            message = "Doctor dashboard loaded"
        elif current_user.role == UserRole.ADMIN:
            data = _admin_payload(db, current_user)
            message = "Admin dashboard loaded"
        else:
            raise AppException(
                f"Dashboard is not available for role {current_user.role.value}",
                status_code=403,
                code="unsupported_role",
            )
        return ApiResponse(data=data, message=message)
    except AppException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to build dashboard",
            extra={
                "role": current_user.role.value if current_user.role else None,
                "user_id": current_user.id,
                "error": str(exc),
            },
            exc_info=True,
        )
        raise AppException("Failed to load dashboard. Please try again.", code="dashboard_error")