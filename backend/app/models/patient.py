from datetime import date
from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.models.base import BaseModel


class PatientProfile(BaseModel):
    __tablename__ = "patient_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True, index=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String(5), nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    chronic_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    family_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str | None] = mapped_column(String(60), nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    emergency_contact_relation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    emergency_contact_alt_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    activity_level: Mapped[str | None] = mapped_column(String(30), nullable=True)  # sedentary|light|moderate|active|very_active
    dietary_preference: Mapped[str | None] = mapped_column(String(30), nullable=True)  # vegetarian|non_vegetarian|vegan
    health_goal: Mapped[str | None] = mapped_column(String(120), nullable=True)

    user = orm_relationship("User", back_populates="patient_profile")
    emergency_contacts = orm_relationship("EmergencyContact", back_populates="patient_profile", cascade="all, delete-orphan")
    family_profiles = orm_relationship("FamilyProfile", back_populates="patient_profile", cascade="all, delete-orphan")
    medical_histories = orm_relationship("MedicalHistory", back_populates="patient_profile", cascade="all, delete-orphan")
    health_metrics = orm_relationship("HealthMetric", back_populates="patient_profile", cascade="all, delete-orphan")


class EmergencyContact(BaseModel):
    __tablename__ = "emergency_contacts"

    patient_profile_id: Mapped[int] = mapped_column(ForeignKey("patient_profiles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    relation: Mapped[str] = mapped_column(String(50), nullable=False)
    is_primary: Mapped[bool] = mapped_column(default=False, nullable=False)

    patient_profile = orm_relationship("PatientProfile", back_populates="emergency_contacts")


class FamilyProfile(BaseModel):
    __tablename__ = "family_profiles"

    patient_profile_id: Mapped[int] = mapped_column(ForeignKey("patient_profiles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    relationship: Mapped[str] = mapped_column(String(50), nullable=False)  # parent|child|elderly|spouse|other
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String(5), nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    chronic_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    medical_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    medications: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient_profile = orm_relationship("PatientProfile", back_populates="family_profiles")

    # Family members keep their own isolated records (no mixing).
    medical_histories = orm_relationship("MedicalHistory", back_populates="family_profile", cascade="all, delete-orphan")
    health_metrics = orm_relationship("HealthMetric", back_populates="family_profile", cascade="all, delete-orphan")


class MedicalHistory(BaseModel):
    __tablename__ = "medical_histories"

    patient_profile_id: Mapped[int | None] = mapped_column(ForeignKey("patient_profiles.id"), nullable=True, index=True)
    family_profile_id: Mapped[int | None] = mapped_column(ForeignKey("family_profiles.id"), nullable=True, index=True)
    condition_name: Mapped[str] = mapped_column(String(200), nullable=False)
    diagnosed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)  # active|resolved|managed
    severity: Mapped[str | None] = mapped_column(String(30), nullable=True)
    treatment: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient_profile = orm_relationship("PatientProfile", back_populates="medical_histories")
    family_profile = orm_relationship("FamilyProfile", back_populates="medical_histories")


class HealthMetric(BaseModel):
    __tablename__ = "health_metrics"

    patient_profile_id: Mapped[int | None] = mapped_column(ForeignKey("patient_profiles.id"), nullable=True, index=True)
    family_profile_id: Mapped[int | None] = mapped_column(ForeignKey("family_profiles.id"), nullable=True, index=True)
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # weight|bp|blood_sugar|heart_rate|sleep|activity|bmi|water_intake|mood|stress
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    systolic: Mapped[float | None] = mapped_column(Float, nullable=True)   # for blood pressure
    diastolic: Mapped[float | None] = mapped_column(Float, nullable=True)  # for blood pressure
    source: Mapped[str | None] = mapped_column(String(40), nullable=True)  # manual|device|ai_estimated
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient_profile = orm_relationship("PatientProfile", back_populates="health_metrics")
    family_profile = orm_relationship("FamilyProfile", back_populates="health_metrics")