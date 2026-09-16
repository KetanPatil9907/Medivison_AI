"""Analytics endpoints: patient insights, health score, trend detection, doctor
insights and admin platform analytics.

Scores and trend directions are computed from stored data with transparent,
explainable rules - they are wellness signals, not clinical metrics.
"""

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.deps import require_admin, require_doctor, require_patient
from app.core.database import get_db
from app.core.exceptions import AppException, NotFoundException, ValidationException
from app.models import (
    AnalyticsSnapshot,
    Appointment,
    Consultation,
    HealthMetric,
    HealthScore,
    HealthTrend,
    ImageAnalysis,
    Medication,
    PreventiveReminder,
    RiskAssessment,
    SymptomSession,
    User,
    UserRole,
)
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse
from app.services.timeline_service import log_json

router = APIRouter(prefix="/analytics", tags=["analytics"])

logger = logging.getLogger("medivision.api.analytics")

ANALYTICS_DISCLAIMER = (
    "Aggregated analytics are wellness signals computed from your data. They are "
    "not a clinical diagnosis or a substitute for professional evaluation."
)

TRACKED_METRICS = ("weight", "heart_rate", "blood_sugar", "sleep", "bp")
PERIODS = {"30d": 30, "90d": 90}


# ---------------------------------------------------------------- health score
def _latest_metric(db: Session, profile_id: int, metric_type: str) -> HealthMetric | None:
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


def _score_component(name: str, value: float, score: float, rationale: str) -> dict:
    return {
        "name": name,
        "value": value,
        "score": round(score),
        "rationale": rationale,
        "improving": score >= 75,
        "reducing": score < 60,
    }


def _bmi_score(bmi: float) -> dict:
    if bmi < 18.5:
        return _score_component("Body mass index", bmi, 55, "Below the healthy range")
    if bmi <= 24.9:
        return _score_component("Body mass index", bmi, 100, "Within the healthy range")
    if bmi <= 29.9:
        return _score_component("Body mass index", bmi, 70, "Slightly above the healthy range")
    if bmi <= 34.9:
        return _score_component("Body mass index", bmi, 45, "Above the healthy range")
    return _score_component("Body mass index", bmi, 30, "Well above the healthy range")


def _bp_score(systolic: float, diastolic: float) -> dict:
    if systolic < 120 and diastolic < 80:
        return _score_component("Blood pressure", systolic, 100, "Readings in the healthy band")
    if systolic < 130 and diastolic < 85:
        return _score_component("Blood pressure", systolic, 82, "Readings slightly above ideal")
    if systolic < 140 and diastolic < 90:
        return _score_component("Blood pressure", systolic, 68, "Readings at the upper boundary")
    if systolic < 160 and diastolic < 100:
        return _score_component("Blood pressure", systolic, 48, "Readings elevated")
    return _score_component("Blood pressure", systolic, 35, "Readings significantly elevated")


def _sugar_score(value: float) -> dict:
    if value < 100:
        return _score_component("Blood sugar (fasting)", value, 100, "In the healthy band")
    if value < 126:
        return _score_component("Blood sugar (fasting)", value, 72, "Slightly elevated")
    if value < 160:
        return _score_component("Blood sugar (fasting)", value, 55, "Elevated")
    return _score_component("Blood sugar (fasting)", value, 40, "Significantly elevated")


def _heart_rate_score(value: float) -> dict:
    if 60 <= value <= 100:
        return _score_component("Resting heart rate", value, 90, "Typical resting band")
    return _score_component("Resting heart rate", value, 60, "Outside the typical resting band")


def _sleep_score(value: float) -> dict:
    if 7 <= value <= 9:
        return _score_component("Sleep", value, 100, "Recommended duration")
    if value >= 6:
        return _score_component("Sleep", value, 78, "Marginally below recommended")
    return _score_component("Sleep", value, 50, "Below recommended duration")


def _activity_score(activity_level: str | None) -> dict:
    mapping = {"sedentary": 40, "light": 65, "moderate": 85, "active": 95, "very_active": 100}
    level = activity_level or "light"
    score = mapping.get(level, 65)
    return _score_component("Physical activity", level, score, f"Activity level: {level.replace('_', ' ')}")


def _adherence_score(db: Session, user_id: int) -> dict | None:
    meds = db.query(Medication).filter(Medication.patient_id == user_id, Medication.status == "active").all()
    with_adherence = [m.adherence_rate for m in meds if m.adherence_rate is not None]
    if not with_adherence:
        return None
    avg = sum(with_adherence) / len(with_adherence)
    return _score_component("Medication adherence", round(avg, 1), avg, "Average adherence across active medications")


def _wellness_score(db: Session, user_id: int, days: int = 14) -> dict | None:
    cutoff = date.today() - timedelta(days=days)
    from app.models import MentalWellnessEntry
    rows = (
        db.query(MentalWellnessEntry)
        .filter(
            MentalWellnessEntry.patient_id == user_id,
            MentalWellnessEntry.recorded_date >= cutoff,
        )
        .all()
    )
    moods = [r.mood_score for r in rows if r.mood_score is not None]
    stresses = [r.stress_level for r in rows if r.stress_level is not None]
    if not moods and not stresses:
        return None
    values = []
    values += [m * 10 for m in moods]
    values += [(10 - s) * 10 for s in stresses]
    avg = sum(values) / len(values)
    return _score_component("Mental wellbeing", round(avg, 1), avg, "Recent mood and stress check-ins")


def compute_health_score(db: Session, user: User) -> dict:
    profile = user.patient_profile
    profile_id = profile.id if profile else None
    components = []

    latest_weight = _latest_metric(db, profile_id, "weight")
    if latest_weight and profile and profile.height_cm:
        height_m = float(profile.height_cm) / 100
        if height_m > 0:
            components.append(_bmi_score(latest_weight.value / (height_m ** 2)))

    latest_bp = _latest_metric(db, profile_id, "bp")
    if latest_bp:
        if latest_bp.systolic is not None and latest_bp.diastolic is not None:
            components.append(_bp_score(latest_bp.systolic, latest_bp.diastolic))
        else:
            components.append(_score_component("Blood pressure", latest_bp.value, 70, "Blood pressure recorded"))

    latest_sugar = _latest_metric(db, profile_id, "blood_sugar")
    if latest_sugar:
        components.append(_sugar_score(latest_sugar.value))

    latest_hr = _latest_metric(db, profile_id, "heart_rate")
    if latest_hr:
        components.append(_heart_rate_score(latest_hr.value))

    latest_sleep = _latest_metric(db, profile_id, "sleep")
    if latest_sleep:
        components.append(_sleep_score(latest_sleep.value))

    components.append(_activity_score(profile.activity_level if profile else None))

    adherence = _adherence_score(db, user.id)
    if adherence:
        components.append(adherence)

    wellness = _wellness_score(db, user.id)
    if wellness:
        components.append(wellness)

    if not components:
        raise ValidationException(
            "Not enough data to compute a health score yet. Add health metrics, sleep, "
            "or set your activity level in your profile first."
        )

    score = round(sum(c["score"] for c in components) / len(components))
    improving = [c["name"] for c in components if c["improving"]]
    reducing = [c["name"] for c in components if c["reducing"]]
    breakdown = {
        "components": components,
        "used_metric_count": len(components),
    }
    return {
        "score": int(score),
        "factors_improving": improving,
        "factors_reducing": reducing,
        "breakdown": breakdown,
        "recorded_date": date.today(),
    }


@router.get("/health-score", response_model=ApiResponse[dict])
async def get_health_score(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        score = (
            db.query(HealthScore)
            .filter(HealthScore.patient_id == current_user.id)
            .order_by(HealthScore.recorded_date.desc(), HealthScore.id.desc())
            .first()
        )
        if not score:
            return ApiResponse(
                data={
                    "score": None,
                    "message": "No health score yet. Run POST /analytics/health-score/recompute.",
                    "disclaimer": ANALYTICS_DISCLAIMER,
                },
                message="No health score computed yet",
            )
        return ApiResponse(
            data={
                "id": score.id,
                "score": score.score,
                "previous_score": score.previous_score,
                "factors_improving": _load_list(score.factors_improving),
                "factors_reducing": _load_list(score.factors_reducing),
                "breakdown": _load_dict(score.breakdown),
                "recorded_date": score.recorded_date.isoformat(),
                "disclaimer": ANALYTICS_DISCLAIMER,
            },
            message="Health score retrieved",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to load health score", exc_info=True)
        raise AppException("Failed to load the health score. Please try again.", code="analytics_error")


@router.post("/health-score/recompute", response_model=ApiResponse[dict])
async def recompute_health_score(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        result = compute_health_score(db, current_user)
        previous = (
            db.query(HealthScore)
            .filter(HealthScore.patient_id == current_user.id)
            .order_by(HealthScore.recorded_date.desc(), HealthScore.id.desc())
            .first()
        )
        row = HealthScore(
            patient_id=current_user.id,
            score=result["score"],
            previous_score=previous.score if previous else None,
            factors_improving=log_json(result["factors_improving"]),
            factors_reducing=log_json(result["factors_reducing"]),
            breakdown=log_json(result["breakdown"]),
            recorded_date=result["recorded_date"],
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return ApiResponse(
            data={
                "id": row.id,
                "score": row.score,
                "previous_score": row.previous_score,
                "factors_improving": _load_list(row.factors_improving),
                "factors_reducing": _load_list(row.factors_reducing),
                "recorded_date": row.recorded_date.isoformat(),
                "disclaimer": ANALYTICS_DISCLAIMER,
            },
            message=f"Health score recomputed: {row.score}/100",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to recompute health score", exc_info=True)
        raise AppException("Failed to recompute the health score. Please try again.", code="analytics_error")


# ---------------------------------------------------------------- patient insights
def _metric_summary(db: Session, profile_id: int, metric_type: str, cutoff: date) -> dict:
    if profile_id is None:
        return {"metric_type": metric_type, "count": 0, "latest": None, "avg_30d": None}
    rows = (
        db.query(HealthMetric)
        .filter(
            HealthMetric.patient_profile_id == profile_id,
            HealthMetric.family_profile_id.is_(None),
            HealthMetric.metric_type == metric_type,
        )
        .order_by(HealthMetric.recorded_date.desc(), HealthMetric.id.desc())
        .all()
    )
    latest = rows[0] if rows else None
    recent = [r for r in rows if r.recorded_date >= cutoff]
    avg = round(sum(r.value for r in recent) / len(recent), 2) if recent else None
    return {
        "metric_type": metric_type,
        "count": len(rows),
        "latest": {
            "value": latest.value,
            "unit": latest.unit,
            "recorded_date": latest.recorded_date.isoformat(),
            "systolic": latest.systolic,
            "diastolic": latest.diastolic,
        }
        if latest
        else None,
        "avg_30d": avg,
    }


@router.get("/patient-insights", response_model=ApiResponse[dict])
async def patient_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        profile_id = current_user.patient_profile.id if current_user.patient_profile else None
        cutoff = date.today() - timedelta(days=30)

        summaries = [_metric_summary(db, profile_id, m, cutoff) for m in TRACKED_METRICS]

        active_meds = db.query(Medication).filter(Medication.patient_id == current_user.id, Medication.status == "active").count()
        adherence_values = [
            m.adherence_rate
            for m in db.query(Medication).filter(Medication.patient_id == current_user.id).all()
            if m.adherence_rate is not None
        ]
        adherence_avg = round(sum(adherence_values) / len(adherence_values), 1) if adherence_values else None

        pending_reminders = (
            db.query(PreventiveReminder)
            .filter(
                PreventiveReminder.patient_id == current_user.id,
                PreventiveReminder.status == "pending",
                PreventiveReminder.due_date >= date.today(),
            )
            .count()
        )
        completed_consultations = (
            db.query(Consultation)
            .filter(Consultation.patient_id == current_user.id, Consultation.status == "completed")
            .count()
        )
        ai_usage = {
            "symptom_checks": db.query(SymptomSession).filter(SymptomSession.patient_id == current_user.id).count(),
            "risk_assessments": db.query(RiskAssessment).filter(RiskAssessment.patient_id == current_user.id).count(),
            "image_analyses": db.query(ImageAnalysis).filter(ImageAnalysis.patient_id == current_user.id).count(),
        }
        latest_score = (
            db.query(HealthScore)
            .filter(HealthScore.patient_id == current_user.id)
            .order_by(HealthScore.recorded_date.desc(), HealthScore.id.desc())
            .first()
        )
        return ApiResponse(
            data={
                "metric_summaries": summaries,
                "medications": {
                    "active_count": active_meds,
                    "avg_adherence": adherence_avg,
                },
                "preventive_reminders_pending": pending_reminders,
                "completed_consultations": completed_consultations,
                "ai_usage": ai_usage,
                "health_score": latest_score.score if latest_score else None,
                "disclaimer": ANALYTICS_DISCLAIMER,
            },
            message="Patient insights retrieved",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to compute patient insights", exc_info=True)
        raise AppException("Failed to load insights. Please try again.", code="analytics_error")


# ------------------------------------------------------------------ trends
def _compute_trend(db: Session, profile_id: int, metric_type: str, days: int) -> dict:
    cutoff = date.today() - timedelta(days=days - 1)
    rows = (
        db.query(HealthMetric.recorded_date, HealthMetric.value)
        .filter(
            HealthMetric.patient_profile_id == profile_id,
            HealthMetric.family_profile_id.is_(None),
            HealthMetric.metric_type == metric_type,
            HealthMetric.recorded_date >= cutoff,
        )
        .order_by(HealthMetric.recorded_date.asc())
        .all()
    )
    if len(rows) < 2:
        return {"metric_type": metric_type, "direction": "stable", "slope": None, "points": len(rows), "period": f"{days}d"}

    xs = [float((r[0] - rows[0][0]).days) for r in rows]
    ys = [float(r[1]) for r in rows]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    slope = numerator / denominator if denominator else 0.0
    direction = "increasing" if slope > 0.05 else ("decreasing" if slope < -0.05 else "stable")
    return {
        "metric_type": metric_type,
        "direction": direction,
        "slope": round(slope, 4),
        "points": n,
        "period": f"{days}d",
    }


@router.post("/trends", response_model=ApiResponse[dict])
async def compute_trends(
    period: str = Query(default="90d", pattern="^(30d|90d)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        profile_id = current_user.patient_profile.id if current_user.patient_profile else None
        if profile_id is None:
            raise ValidationException("Complete your patient profile before computing trends.")
        days = PERIODS[period]
        computed = []
        for metric in TRACKED_METRICS:
            trend = _compute_trend(db, profile_id, metric, days)
            if trend["points"] < 2:
                computed.append({**trend, "note": "Not enough data points"})
                continue
            db.query(HealthTrend).filter(
                HealthTrend.patient_id == current_user.id,
                HealthTrend.metric_type == metric,
                HealthTrend.period == period,
            ).delete()
            db.add(
                HealthTrend(
                    patient_id=current_user.id,
                    metric_type=metric,
                    trend_direction=trend["direction"],
                    period=period,
                    slope=trend["slope"],
                    computed_at=datetime.now(timezone.utc),
                )
            )
            computed.append(trend)
        db.commit()
        return ApiResponse(
            data={
                "period": period,
                "trends": computed,
                "disclaimer": ANALYTICS_DISCLAIMER,
            },
            message="Trends computed",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to compute trends", exc_info=True)
        raise AppException("Failed to compute trends. Please try again.", code="analytics_error")


# ------------------------------------------------------------ doctor insights
@router.get("/doctor-insights", response_model=ApiResponse[dict])
async def doctor_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    try:
        today = date.today()
        total_patients = (
            db.query(Appointment.patient_id).filter(Appointment.doctor_id == current_user.id).distinct().count()
        )
        consultations_total = db.query(Consultation).filter(Consultation.doctor_id == current_user.id).count()
        status_counts = dict(
            db.query(Consultation.status, func.count(Consultation.id))
            .filter(Consultation.doctor_id == current_user.id)
            .group_by(Consultation.status)
            .all()
        )
        today_appointments = (
            db.query(Appointment)
            .filter(Appointment.doctor_id == current_user.id, Appointment.scheduled_date == today)
            .count()
        )
        upcoming = (
            db.query(Appointment)
            .filter(
                Appointment.doctor_id == current_user.id,
                Appointment.scheduled_date >= today,
                Appointment.status.in_(("BOOKED", "CONFIRMED", "RESCHEDULED")),
            )
            .count()
        )
        avg_consultations = round(consultations_total / total_patients, 1) if total_patients else 0
        return ApiResponse(
            data={
                "total_patients": total_patients,
                "consultation_status_counts": status_counts,
                "consultations_total": consultations_total,
                "today_appointments": today_appointments,
                "upcoming_appointments": upcoming,
                "avg_consultations_per_patient": avg_consultations,
                "disclaimer": ANALYTICS_DISCLAIMER,
            },
            message="Doctor insights retrieved",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to compute doctor insights", exc_info=True)
        raise AppException("Failed to load insights. Please try again.", code="analytics_error")


# ------------------------------------------------------------- platform (admin)
@router.get("/platform", response_model=ApiResponse[dict])
async def platform_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        total_patients = db.query(User).filter(User.role == UserRole.PATIENT).count()
        total_doctors = db.query(User).filter(User.role == UserRole.DOCTOR).count()
        total_appointments = db.query(Appointment).count()
        completed_consultations = db.query(Consultation).filter(Consultation.status == "completed").count()
        ai_usage = {
            "symptom_checks": db.query(SymptomSession).count(),
            "risk_assessments": db.query(RiskAssessment).count(),
            "image_analyses": db.query(ImageAnalysis).count(),
        }
        snapshot = AnalyticsSnapshot(
            scope="platform",
            snapshot_type="overview",
            data=log_json(
                {
                    "total_patients": total_patients,
                    "total_doctors": total_doctors,
                    "total_appointments": total_appointments,
                    "completed_consultations": completed_consultations,
                    "ai_usage": ai_usage,
                    "computed_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
            snapshot_date=date.today(),
        )
        db.add(snapshot)
        db.commit()
        return ApiResponse(
            data={
                "total_patients": total_patients,
                "total_doctors": total_doctors,
                "total_appointments": total_appointments,
                "completed_consultations": completed_consultations,
                "ai_usage": ai_usage,
                "snapshot_id": snapshot.id,
                "disclaimer": ANALYTICS_DISCLAIMER,
            },
            message="Platform analytics snapshot recorded",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to compute platform analytics", exc_info=True)
        raise AppException("Failed to load platform analytics. Please try again.", code="analytics_error")


@router.get("/snapshots", response_model=PaginatedResponse)
async def list_snapshots(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        base = db.query(AnalyticsSnapshot).filter(AnalyticsSnapshot.scope == "platform")
        total = base.count()
        snapshots = (
            base.order_by(AnalyticsSnapshot.snapshot_date.desc(), AnalyticsSnapshot.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return PaginatedResponse(
            data=PaginatedData(
                items=[
                    {
                        "id": s.id,
                        "snapshot_type": s.snapshot_type,
                        "snapshot_date": s.snapshot_date.isoformat(),
                        "data": _load_dict(s.data),
                    }
                    for s in snapshots
                ],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=(total + page_size - 1) // page_size,
            ),
            message=f"{total} analytics snapshots",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to list snapshots", exc_info=True)
        raise AppException("Failed to load snapshots. Please try again.", code="analytics_error")


def _load_list(raw: str | None):
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except (ValueError, TypeError):
        return []


def _load_dict(raw: str | None):
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}