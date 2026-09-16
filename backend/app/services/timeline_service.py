from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.analytics import HealthTimeline


def add_timeline_event(
    db: Session,
    patient_id: int,
    event_type: str,
    title: str,
    description: str | None = None,
    event_date: date | None = None,
    severity: str | None = None,
    metadata_json: str | None = None,
    family_profile_id: int | None = None,
    appointment_id: int | None = None,
    consultation_id: int | None = None,
    prescription_id: int | None = None,
) -> HealthTimeline:
    event = HealthTimeline(
        patient_id=patient_id,
        family_profile_id=family_profile_id,
        event_type=event_type,
        title=title,
        description=description,
        event_date=event_date or datetime.now(timezone.utc).date(),
        severity=severity,
        metadata_json=metadata_json,
        appointment_id=appointment_id,
        consultation_id=consultation_id,
        prescription_id=prescription_id,
    )
    db.add(event)
    db.flush()
    return event


def log_json(obj: Any) -> str:
    import json
    return json.dumps(obj, default=str)