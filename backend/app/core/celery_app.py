from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "medivision",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.services.notifications.tasks.send_email_task": {"queue": "notifications"},
        "app.services.reminders.tasks.send_medication_reminders": {"queue": "reminders"},
    },
)

celery_app.autodiscover_tasks(["app.services"])

from app.services.reminders import tasks as reminders_tasks  # noqa: E402  (ensure registration)
from app.services.notifications import tasks as notif_tasks  # noqa: E402