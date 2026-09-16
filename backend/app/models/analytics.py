from datetime import date, datetime
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class HealthTimeline(BaseModel):
    __tablename__ = "health_timeline"

    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    family_profile_id: Mapped[int | None] = mapped_column(ForeignKey("family_profiles.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)  # appointment|report|test|risk_assessment|ai_analysis|consultation|prescription|metric|vaccination|health_event
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"), nullable=True)
    consultation_id: Mapped[int | None] = mapped_column(ForeignKey("consultations.id"), nullable=True)
    prescription_id: Mapped[int | None] = mapped_column(ForeignKey("prescriptions.id"), nullable=True)

    appointment = relationship("Appointment", back_populates="timeline_events")
    consultation = relationship("Consultation", back_populates="timeline_events")
    prescription = relationship("Prescription", back_populates="timeline_events")


class HealthTrend(BaseModel):
    __tablename__ = "health_trends"

    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trend_direction: Mapped[str] = mapped_column(String(20), nullable=False)  # increasing|decreasing|stable
    period: Mapped[str] = mapped_column(String(20), default="30d", nullable=False)
    slope: Mapped[float | None] = mapped_column(Float, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AnalyticsSnapshot(BaseModel):
    __tablename__ = "analytics_snapshots"

    scope: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # platform|patient|doctor
    scope_id: Mapped[int | None] = mapped_column(nullable=True)
    snapshot_type: Mapped[str] = mapped_column(String(50), nullable=False)
    data: Mapped[Text] = mapped_column(Text, nullable=False, doc="JSON payload")
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)


class AuditLog(BaseModel):
    __tablename__ = "audit_logs"

    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    before: Mapped[Text | None] = mapped_column(Text, nullable=True, doc="JSON snapshot")
    after: Mapped[Text | None] = mapped_column(Text, nullable=True, doc="JSON snapshot")
    meta: Mapped[Text | None] = mapped_column(Text, nullable=True, doc="JSON extra")
    success: Mapped[bool] = mapped_column(default=True, nullable=False)

    user = relationship("User", back_populates="audit_logs")