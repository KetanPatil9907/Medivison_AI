"""Celery scheduled tasks for medication reminders and notifications."""
from datetime import datetime, timezone

from app.core.celery_app import celery_app
from app.models.clinical import Medication
from app.models.wellness import PreventiveReminder


@celery_app.task(name="app.services.reminders.medication_daily_check")
def medication_daily_check() -> dict:
    from app.core.database import SessionLocal
    today = datetime.now(timezone.utc).date()
    active = []
    db = SessionLocal()
    try:
        meds = (
            db.query(Medication)
            .filter(Medication.status == "active", Medication.reminder_enabled.is_(True))
            .all()
        )
        result = {"checked": len(meds), "due": []}
        for m in meds:
            if m.end_date and m.end_date < today:
                m.status = "completed"
            else:
                result["due"].append({"medication_id": m.id, "name": m.name})
        db.commit()
        return result
    finally:
        db.close()


@celery_app.task(name="app.services.reminders.send_medication_reminders")
def send_medication_reminders() -> dict:
    return {"status": "ok", "mode": "in_app_notifications"}


@celery_app.task(name="app.services.reminders.preventive_reminder_check")
def preventive_reminder_check() -> dict:
    from app.core.database import SessionLocal
    today = datetime.now(timezone.utc).date()
    db = SessionLocal()
    try:
        overdue = (
            db.query(PreventiveReminder)
            .filter(PreventiveReminder.status == "pending", PreventiveReminder.due_date < today)
            .all()
        )
        for r in overdue:
            r.status = "overdue"
        db.commit()
        return {"overdue_marked": len(overdue)}
    finally:
        db.close()