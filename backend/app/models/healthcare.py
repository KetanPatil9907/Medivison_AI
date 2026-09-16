from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class HealthcareFacility(BaseModel):
    """Base class for hospitals, clinics, pharmacies, diagnostic labs."""
    __abstract__ = True

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str] = mapped_column(String(60), default="India", nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    opening_hours: Mapped[str | None] = mapped_column(String(200), nullable=True)
    website: Mapped[str | None] = mapped_column(String(300), nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Hospital(HealthcareFacility):
    __tablename__ = "hospitals"

    total_beds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    available_beds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    icu_beds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    available_icu_beds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    emergency_capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_emergency: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    departments: Mapped[str | None] = mapped_column(Text, nullable=True, doc="JSON list")


class Clinic(HealthcareFacility):
    __tablename__ = "clinics"

    specialties: Mapped[str | None] = mapped_column(Text, nullable=True, doc="JSON list")
    doctors_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Pharmacy(HealthcareFacility):
    __tablename__ = "pharmacies"

    has_delivery: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    license_number: Mapped[str | None] = mapped_column(String(120), nullable=True)


class DiagnosticLab(HealthcareFacility):
    __tablename__ = "diagnostic_labs"

    tests_offered: Mapped[str | None] = mapped_column(Text, nullable=True, doc="JSON list")
    accreditation: Mapped[str | None] = mapped_column(String(120), nullable=True)


class HealthcareService(BaseModel):
    __tablename__ = "healthcare_services"

    facility_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # hospital|clinic|pharmacy|lab
    facility_id: Mapped[int] = mapped_column(nullable=False, index=True)
    service_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)