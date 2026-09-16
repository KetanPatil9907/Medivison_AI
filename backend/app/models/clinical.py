from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Appointment(BaseModel):
    __tablename__ = "appointments"

    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    family_profile_id: Mapped[int | None] = mapped_column(ForeignKey("family_profiles.id"), nullable=True, index=True, doc="book for a family member")
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False, doc="HH:MM 24h")
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    consultation_type: Mapped[str] = mapped_column(String(20), default="in_person", nullable=False)  # in_person|online|phone
    status: Mapped[str] = mapped_column(
        String(20), default="BOOKED", nullable=False, index=True,
        doc="BOOKED|CONFIRMED|COMPLETED|CANCELLED|RESCHEDULED"
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    symptoms_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    queue_position: Mapped[int | None] = mapped_column(Integer, nullable=True, doc="live queue position")
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_policy_ack: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    video_room_id: Mapped[str | None] = mapped_column(String(120), nullable=True, doc="future video consultation architecture")

    consultation = relationship("Consultation", back_populates="appointment", uselist=False)
    timeline_events = relationship("HealthTimeline", back_populates="appointment")


class Consultation(BaseModel):
    __tablename__ = "consultations"

    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"), nullable=False, unique=True, index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True, doc="clinical impression / diagnosis")
    clinical_impression: Mapped[str | None] = mapped_column(Text, nullable=True)
    symptoms: Mapped[str | None] = mapped_column(Text, nullable=True)
    vital_signs: Mapped[str | None] = mapped_column(Text, nullable=True, doc="JSON: bp, hr, temp, etc")
    recommended_tests: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    follow_up_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="completed", nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    appointment = relationship("Appointment", back_populates="consultation")
    prescriptions = relationship("Prescription", back_populates="consultation", cascade="all, delete-orphan")
    timeline_events = relationship("HealthTimeline", back_populates="consultation")


class Prescription(BaseModel):
    __tablename__ = "prescriptions"

    consultation_id: Mapped[int] = mapped_column(ForeignKey("consultations.id"), nullable=False, index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    medicine_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dosage: Mapped[str] = mapped_column(String(120), nullable=False)
    frequency: Mapped[str] = mapped_column(String(120), nullable=False)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    refill_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    consultation = relationship("Consultation", back_populates="prescriptions")
    timeline_events = relationship("HealthTimeline", back_populates="prescription")


class Medication(BaseModel):
    __tablename__ = "medications"

    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    family_profile_id: Mapped[int | None] = mapped_column(ForeignKey("family_profiles.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    dosage: Mapped[str] = mapped_column(String(120), nullable=False)
    frequency: Mapped[str] = mapped_column(String(120), nullable=False)  # once_daily|twice_daily|custom
    frequency_detail: Mapped[str | None] = mapped_column(String(200), nullable=True, doc="custom times e.g. 08:00,20:00")
    times_per_day: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    refill_reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    refill_threshold_days: Mapped[int | None] = mapped_column(Integer, default=3, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    prescribed_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, doc="active|completed|paused|discontinued")
    adherence_rate: Mapped[float | None] = mapped_column(Float, nullable=True, doc="0-100")
    intake_log: Mapped[str | None] = mapped_column(Text, nullable=True, doc="JSON array of {date,time,taken}")


class MedicalReport(BaseModel):
    __tablename__ = "medical_reports"

    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    family_profile_id: Mapped[int | None] = mapped_column(ForeignKey("family_profiles.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # blood_report|xray|prescription|document|scan|other
    report_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    condition: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_key: Mapped[str] = mapped_column(String(500), nullable=False, doc="object storage key")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=False, default=0)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    storage_driver: Mapped[str] = mapped_column(String(20), default="s3", nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(20), default="patient", nullable=False)