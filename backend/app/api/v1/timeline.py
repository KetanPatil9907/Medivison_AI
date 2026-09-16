"""Patient health timeline endpoints.

GET /timeline/my   - paginated, date-grouped timeline for the authenticated patient.
GET /timeline/stats - counts of timeline events per event_type.
"""

import json
import logging
from collections import OrderedDict
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.deps import require_patient
from app.core.database import get_db
from app.core.exceptions import AppException, NotFoundException, ValidationException
from app.models import FamilyProfile, HealthTimeline, User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse

router = APIRouter(prefix="/timeline", tags=["timeline"])

logger = logging.getLogger("medivision.api.timeline")

EVENT_TYPE_PATTERN = (
    r"^(appointment|report|test|risk_assessment|ai_analysis|consultation|"
    r"prescription|metric|vaccination|health_event)$"
)


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValidationException("Invalid date, expected YYYY-MM-DD", details={"value": value})


def _maybe_json(value: str | None):
    if not value:
        return None
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return value


def _timeline_event_json(event: HealthTimeline) -> dict:
    return {
        "id": event.id,
        "event_type": event.event_type,
        "title": event.title,
        "description": event.description,
        "event_date": event.event_date.isoformat() if event.event_date else None,
        "severity": event.severity,
        "metadata_json": _maybe_json(event.metadata_json),
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def _resolve_family_filter(db: Session, user: User, family_profile_id: int | None):
    if family_profile_id is None:
        return HealthTimeline.family_profile_id.is_(None)
    family = db.get(FamilyProfile, family_profile_id)
    if not family or user.patient_profile is None or family.patient_profile_id != user.patient_profile.id:
        raise NotFoundException("Family profile not found")
    return HealthTimeline.family_profile_id == family.id


@router.get("/my", response_model=PaginatedResponse)
async def my_timeline(
    event_type: Optional[str] = Query(None, pattern=EVENT_TYPE_PATTERN),
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    family_profile_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
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

        base = [HealthTimeline.patient_id == current_user.id]
        base.append(_resolve_family_filter(db, current_user, family_profile_id))
        if event_type:
            base.append(HealthTimeline.event_type == event_type)
        if parsed_from:
            base.append(HealthTimeline.event_date >= parsed_from)
        if parsed_to:
            base.append(HealthTimeline.event_date <= parsed_to)

        total = db.query(HealthTimeline).filter(*base).count()
        events = (
            db.query(HealthTimeline)
            .filter(*base)
            .order_by(HealthTimeline.event_date.desc(), HealthTimeline.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        grouped: OrderedDict[str, list[dict]] = OrderedDict()
        for event in events:
            key = event.event_date.isoformat() if event.event_date else "unknown"
            grouped.setdefault(key, []).append(_timeline_event_json(event))
        items = [{"date": key, "events": values} for key, values in grouped.items()]

        return PaginatedResponse(
            data=PaginatedData(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=(total + page_size - 1) // page_size,
            ),
            message="Timeline retrieved",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to load patient timeline",
            extra={"user_id": current_user.id, "error": str(exc)},
            exc_info=True,
        )
        raise AppException("Failed to load timeline. Please try again.", code="timeline_error")


@router.get("/stats", response_model=ApiResponse[dict])
async def timeline_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        rows = (
            db.query(HealthTimeline.event_type, func.count(HealthTimeline.id))
            .filter(
                HealthTimeline.patient_id == current_user.id,
                HealthTimeline.family_profile_id.is_(None),
            )
            .group_by(HealthTimeline.event_type)
            .all()
        )
        stats = [{"event_type": event_type, "count": count} for event_type, count in rows]
        stats.sort(key=lambda s: s["count"], reverse=True)
        return ApiResponse(
            data={
                "total": sum(s["count"] for s in stats),
                "stats": stats,
            },
            message="Timeline stats retrieved",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to load timeline stats",
            extra={"user_id": current_user.id, "error": str(exc)},
            exc_info=True,
        )
        raise AppException("Failed to load timeline stats. Please try again.", code="timeline_error")