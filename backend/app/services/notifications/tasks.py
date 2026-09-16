from app.core.celery_app import celery_app


@celery_app.task(name="app.services.notifications.send_email_task")
def send_email_task(subject: str, recipient: str, html_body: str) -> dict:
    # Placeholder transport wrapper. Swap the body for SMTP/SES provider.
    return {"queued": True, "recipient": recipient, "subject": subject}