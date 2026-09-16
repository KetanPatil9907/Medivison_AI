import enum
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, SoftDeleteMixin, utcnow


class UserRole(str, enum.Enum):
    PATIENT = "PATIENT"
    DOCTOR = "DOCTOR"
    ADMIN = "ADMIN"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"      # doctor waiting for approval
    SUSPENDED = "SUSPENDED"
    REJECTED = "REJECTED"
    DISABLED = "DISABLED"


class User(BaseModel, SoftDeleteMixin):
    __tablename__ = "users"

    full_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False, index=True)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), nullable=False, default=UserStatus.ACTIVE, index=True
    )
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    profile_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relations
    patient_profile = relationship("PatientProfile", back_populates="user", uselist=False)
    doctor_profile = relationship("DoctorProfile", back_populates="user", uselist=False)
    doctor_application = relationship(
        "DoctorApplication",
        back_populates="user",
        uselist=False,
        foreign_keys="DoctorApplication.user_id",
    )
    audit_logs = relationship("AuditLog", back_populates="user")


class DoctorApplication(BaseModel):
    __tablename__ = "doctor_applications"
    __table_args__ = ({"comment": "Doctor registration/approval workflow"},)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    specialization: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    qualification: Mapped[str] = mapped_column(String(300), nullable=False)
    medical_registration_number: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    years_of_experience: Mapped[int] = mapped_column(nullable=False, default=0)
    hospital: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    consultation_type: Mapped[str] = mapped_column(String(50), nullable=False, default="in_person")  # in_person|online|both
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False, index=True, doc="PENDING|APPROVED|REJECTED|SUSPENDED")
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    documents: Mapped[str | None] = mapped_column(Text, nullable=True, doc="JSON list of document keys")

    user = relationship(
        "User",
        back_populates="doctor_application",
        foreign_keys="DoctorApplication.user_id",
    )


class DoctorProfile(BaseModel):
    __tablename__ = "doctor_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True, index=True)
    specialization: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    qualification: Mapped[str] = mapped_column(String(300), nullable=False)
    medical_registration_number: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    years_of_experience: Mapped[int] = mapped_column(nullable=False, default=0)
    hospital: Mapped[str] = mapped_column(String(200), nullable=False)
    clinic_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    consultation_type: Mapped[str] = mapped_column(String(50), default="in_person", nullable=False)
    languages: Mapped[str] = mapped_column(String(200), default="English", nullable=False, doc="comma separated")
    rating: Mapped[float] = mapped_column(default=0.0, nullable=False)
    rating_count: Mapped[int] = mapped_column(default=0, nullable=False)
    consultation_fee: Mapped[float | None] = mapped_column(nullable=True)
    online_consultation_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="doctor_profile")

    qualifications = relationship("DoctorQualification", back_populates="doctor_profile", cascade="all, delete-orphan")
    availability = relationship("DoctorAvailability", back_populates="doctor_profile", cascade="all, delete-orphan")
    specialties = relationship("DoctorSpecialty", back_populates="doctor_profile", cascade="all, delete-orphan")


class DoctorQualification(BaseModel):
    __tablename__ = "doctor_qualifications"

    doctor_profile_id: Mapped[int] = mapped_column(ForeignKey("doctor_profiles.id"), nullable=False, index=True)
    degree: Mapped[str] = mapped_column(String(120), nullable=False)
    institution: Mapped[str] = mapped_column(String(200), nullable=False)
    year_completed: Mapped[int | None] = mapped_column(nullable=True)

    doctor_profile = relationship("DoctorProfile", back_populates="qualifications")


class DoctorSpecialty(BaseModel):
    __tablename__ = "doctor_specialties"

    doctor_profile_id: Mapped[int] = mapped_column(ForeignKey("doctor_profiles.id"), nullable=False, index=True)
    specialty: Mapped[str] = mapped_column(String(120), nullable=False, index=True)

    doctor_profile = relationship("DoctorProfile", back_populates="specialties")


class DoctorAvailability(BaseModel):
    __tablename__ = "doctor_availability"

    doctor_profile_id: Mapped[int] = mapped_column(ForeignKey("doctor_profiles.id"), nullable=False, index=True)
    day_of_week: Mapped[int] = mapped_column(nullable=False, doc="0=Monday ... 6=Sunday")
    start_time: Mapped[str] = mapped_column(String(5), nullable=False, doc="HH:MM 24h")
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    doctor_profile = relationship("DoctorProfile", back_populates="availability")

    __table_args__ = (
        {"comment": "Weekly recurring availability with block-out slots"},
    )
