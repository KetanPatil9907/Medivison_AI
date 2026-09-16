"""Mental wellness endpoints: mood logging, breathing exercises, meditation,
daily/weekly trend insights and a history summary.

CRITICAL SAFETY: Wellness content is for general wellbeing and self-care tracking
only. It is not a clinical diagnosis or medical advice and never replaces care by
a qualified healthcare professional. Every wellness payload carries a disclaimer.
"""

import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import require_patient
from app.core.database import get_db
from app.core.exceptions import AppException, ValidationException
from app.models import MentalWellnessEntry, User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse
from app.services.timeline_service import add_timeline_event, log_json

router = APIRouter(prefix="/wellness", tags=["wellness"])

logger = logging.getLogger("medivision.api.wellness")

WELLNESS_DISCLAIMER = (
    "Wellness tracking is for general wellbeing and self-care only. It is not a "
    "clinical diagnosis or medical advice. Please consult a qualified healthcare "
    "professional for any medical concerns."
)


class MoodLogRequest(BaseModel):
    mood_score: int = Field(ge=1, le=10)
    stress_level: Optional[int] = Field(default=None, ge=1, le=10)
    journal_text: Optional[str] = Field(default=None, max_length=5000)
    recorded_date: Optional[date] = None


class BreathingRequest(BaseModel):
    duration_minutes: int = Field(ge=1, le=120)


class MeditationRequest(BaseModel):
    minutes: int = Field(ge=1, le=600)
    notes: Optional[str] = Field(default=None, max_length=5000)


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValidationException("Invalid date, expected YYYY-MM-DD", details={"value": value})


def _entry_json(entry: MentalWellnessEntry) -> dict:
    return {
        "id": entry.id,
        "entry_type": entry.entry_type,
        "mood_score": entry.mood_score,
        "stress_level": entry.stress_level,
        "journal_text": entry.journal_text,
        "breathing_session": entry.breathing_session,
        "meditation_minutes": entry.meditation_minutes,
        "recorded_date": entry.recorded_date.isoformat() if entry.recorded_date else None,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


@router.post("/mood", response_model=ApiResponse[dict])
async def log_mood(
    payload: MoodLogRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        recorded_date = payload.recorded_date or date.today()
        entry = MentalWellnessEntry(
            patient_id=current_user.id,
            entry_type="mood_journal",
            mood_score=payload.mood_score,
            stress_level=payload.stress_level,
            journal_text=payload.journal_text,
            recorded_date=recorded_date,
        )
        db.add(entry)
        db.flush()

        description = f"Mood check-in recorded (mood {payload.mood_score}/10)"
        if payload.stress_level is not None:
            description += f", stress {payload.stress_level}/10"
        add_timeline_event(
            db,
            current_user.id,
            "health_event",
            "Mood check-in",
            description=description,
            event_date=recorded_date,
            metadata_json=log_json(
                {
                    "mood_score": payload.mood_score,
                    "stress_level": payload.stress_level,
                    "entry_id": entry.id,
                }
            ),
        )
        db.commit()
        db.refresh(entry)
        return ApiResponse(
            data={"wellness_entry": _entry_json(entry), "disclaimer": WELLNESS_DISCLAIMER},
            message="Mood check-in recorded",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to log mood entry",
            extra={"user_id": current_user.id, "error": str(exc)},
            exc_info=True,
        )
        raise AppException("Failed to log mood entry. Please try again.", code="wellness_error")


@router.get("/mood", response_model=PaginatedResponse)
async def list_mood(
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        parsed_from = _parse_date(from_date) if from_date else None
        parsed_to = _parse_date(to_date) if to_date else None
        if parsed_from and parsed_to and parsed_from > parsed_to:
            raise ValidationException(
                "from_date cannot be after to_date",
                details={"from_date": from_date, "to_date": to_date},
            )

        base = [
            MentalWellnessEntry.patient_id == current_user.id,
            MentalWellnessEntry.entry_type == "mood_journal",
        ]
        if parsed_from:
            base.append(MentalWellnessEntry.recorded_date >= parsed_from)
        if parsed_to:
            base.append(MentalWellnessEntry.recorded_date <= parsed_to)

        total = db.query(MentalWellnessEntry).filter(*base).count()
        entries = (
            db.query(MentalWellnessEntry)
            .filter(*base)
            .order_by(MentalWellnessEntry.recorded_date.desc(), MentalWellnessEntry.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return PaginatedResponse(
            data=PaginatedData(
                items=[_entry_json(e) for e in entries],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=(total + page_size - 1) // page_size,
            ),
            message=f"{total} mood entries retrieved. {WELLNESS_DISCLAIMER}",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to list mood entries",
            extra={"user_id": current_user.id, "error": str(exc)},
            exc_info=True,
        )
        raise AppException("Failed to load mood entries. Please try again.", code="wellness_error")


@router.post("/breathing", response_model=ApiResponse[dict])
async def log_breathing(
    payload: BreathingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        now = datetime.now(timezone.utc)
        session_payload = {
            "duration_minutes": payload.duration_minutes,
            "completed": True,
            "performed_at": now.isoformat(),
        }
        entry = MentalWellnessEntry(
            patient_id=current_user.id,
            entry_type="stress_tracking",
            breathing_session=json.dumps(session_payload),
            recorded_date=now.date(),
        )
        db.add(entry)
        db.flush()

        add_timeline_event(
            db,
            current_user.id,
            "health_event",
            "Breathing exercise completed",
            description=f"Breathing exercise of {payload.duration_minutes} minute(s) completed",
            event_date=now.date(),
            metadata_json=log_json(
                {"duration_minutes": payload.duration_minutes, "entry_id": entry.id}
            ),
        )
        db.commit()
        db.refresh(entry)
        return ApiResponse(
            data={"wellness_entry": _entry_json(entry), "disclaimer": WELLNESS_DISCLAIMER},
            message="Breathing exercise recorded",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to log breathing exercise",
            extra={"user_id": current_user.id, "error": str(exc)},
            exc_info=True,
        )
        raise AppException("Failed to log breathing exercise. Please try again.", code="wellness_error")


@router.post("/meditation", response_model=ApiResponse[dict])
async def log_meditation(
    payload: MeditationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        recorded_date = date.today()
        entry = MentalWellnessEntry(
            patient_id=current_user.id,
            entry_type="meditation",
            journal_text=payload.notes,
            meditation_minutes=payload.minutes,
            recorded_date=recorded_date,
        )
        db.add(entry)
        db.flush()

        add_timeline_event(
            db,
            current_user.id,
            "health_event",
            "Meditation session logged",
            description=f"Meditation session of {payload.minutes} minute(s) logged",
            event_date=recorded_date,
            metadata_json=log_json({"minutes": payload.minutes, "entry_id": entry.id}),
        )
        db.commit()
        db.refresh(entry)
        return ApiResponse(
            data={"wellness_entry": _entry_json(entry), "disclaimer": WELLNESS_DISCLAIMER},
            message="Meditation session logged",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to log meditation session",
            extra={"user_id": current_user.id, "error": str(exc)},
            exc_info=True,
        )
        raise AppException("Failed to log meditation session. Please try again.", code="wellness_error")


def _day_series(days: int) -> list[date]:
    today = date.today()
    start = today - timedelta(days=days - 1)
    return [start + timedelta(days=i) for i in range(days)]


def _averages(values: list[int]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _daily_trends(entries: list[MentalWellnessEntry], days: int) -> list[dict]:
    per_day: dict = defaultdict(lambda: {"moods": [], "stresses": []})
    for entry in entries:
        if entry.mood_score is not None:
            per_day[entry.recorded_date]["moods"].append(entry.mood_score)
        if entry.stress_level is not None:
            per_day[entry.recorded_date]["stresses"].append(entry.stress_level)

    result = []
    for day in _day_series(days):
        data = per_day.get(day)
        result.append(
            {
                "date": day.isoformat(),
                "mood": _averages(data["moods"]) if data else None,
                "stress": _averages(data["stresses"]) if data else None,
            }
        )
    return result


def _weekly_trends(entries: list[MentalWellnessEntry]) -> list[dict]:
    per_week: dict = defaultdict(lambda: {"moods": [], "stresses": []})
    for entry in entries:
        week_start = entry.recorded_date - timedelta(days=entry.recorded_date.weekday())
        if entry.mood_score is not None:
            per_week[week_start]["moods"].append(entry.mood_score)
        if entry.stress_level is not None:
            per_week[week_start]["stresses"].append(entry.stress_level)

    items = []
    for week_start in sorted(per_week):
        data = per_week[week_start]
        items.append(
            {
                "week_start": week_start.isoformat(),
                "week_end": (week_start + timedelta(days=6)).isoformat(),
                "mood": _averages(data["moods"]),
                "stress": _averages(data["stresses"]),
            }
        )
    return items


def _mood_streak(entries: list[MentalWellnessEntry]) -> int:
    mood_dates = {entry.recorded_date for entry in entries if entry.mood_score is not None}
    today = date.today()
    cursor = today if today in mood_dates else today - timedelta(days=1)
    streak = 0
    while cursor in mood_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _recommendation_text(daily: list[dict], streak: int) -> str:
    moods = [d["mood"] for d in daily if d["mood"] is not None]
    stresses = [d["stress"] for d in daily if d["stress"] is not None]
    avg_mood = sum(moods) / len(moods) if moods else None
    avg_stress = sum(stresses) / len(stresses) if stresses else None

    parts = []
    if avg_mood is not None and avg_mood < 5:
        parts.append(
            "Your recent mood reflections have been on the lower side. Consider gentle self-care, "
            "plenty of rest, and opening up to someone you trust."
        )
    elif avg_mood is not None:
        parts.append("Your recent mood reflections are generally favourable. Keep up what supports your wellbeing.")
    if avg_stress is not None and avg_stress >= 6:
        parts.append(
            "Your reported stress has been running a little high. Short breathing exercises, "
            "light walks, and reaching out for support are good next steps."
        )
    elif avg_stress is not None:
        parts.append("Your stress levels look manageable; a few mindful minutes each day help keep them that way.")
    if streak:
        parts.append(f"You are on a {streak}-day logging streak — small, consistent check-ins build self-awareness.")
    if not parts:
        parts.append("Start by logging a mood check-in. Small steps and gentle consistency help build awareness.")
    return " ".join(parts)


@router.get("/trends", response_model=ApiResponse[dict])
async def wellness_trends(
    days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        start_date = date.today() - timedelta(days=days - 1)
        entries = (
            db.query(MentalWellnessEntry)
            .filter(
                MentalWellnessEntry.patient_id == current_user.id,
                MentalWellnessEntry.recorded_date >= start_date,
            )
            .order_by(MentalWellnessEntry.recorded_date.asc(), MentalWellnessEntry.id.asc())
            .all()
        )
        daily = _daily_trends(entries, days)
        weekly = _weekly_trends(entries)
        streak = _mood_streak(entries)
        recommendation = _recommendation_text(daily, streak)
        return ApiResponse(
            data={
                "days": days,
                "daily": daily,
                "weekly": weekly,
                "streak": streak,
                "recommendation": recommendation,
                "disclaimer": WELLNESS_DISCLAIMER,
            },
            message="Wellness trends retrieved",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to load wellness trends",
            extra={"user_id": current_user.id, "days": days, "error": str(exc)},
            exc_info=True,
        )
        raise AppException("Failed to load wellness trends. Please try again.", code="wellness_error")


@router.get("/history", response_model=ApiResponse[dict])
async def wellness_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        entries = (
            db.query(MentalWellnessEntry)
            .filter(MentalWellnessEntry.patient_id == current_user.id)
            .all()
        )
        moods = [entry.mood_score for entry in entries if entry.mood_score is not None]
        stresses = [entry.stress_level for entry in entries if entry.stress_level is not None]
        weeks_tracked = {
            entry.recorded_date - timedelta(days=entry.recorded_date.weekday())
            for entry in entries
        }
        return ApiResponse(
            data={
                "entries_count": len(entries),
                "avg_mood": _averages(moods),
                "avg_stress": _averages(stresses),
                "weeks_tracked": len(weeks_tracked),
                "disclaimer": WELLNESS_DISCLAIMER,
            },
            message="Wellness history stats retrieved",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to load wellness history",
            extra={"user_id": current_user.id, "error": str(exc)},
            exc_info=True,
        )
        raise AppException("Failed to load wellness history. Please try again.", code="wellness_error")