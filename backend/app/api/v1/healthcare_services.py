"""Healthcare directory: hospitals, clinics, pharmacies, labs and their services.

Read endpoints are patient-facing (with optional distance sorting). Write
endpoints are admin-only so the directory can be kept accurate and current.
"""

import json
import logging
from math import asin, cos, radians, sin, sqrt
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import require_admin, require_patient
from app.core.database import get_db
from app.core.exceptions import AppException, NotFoundException, ValidationException
from app.models import Clinic, DiagnosticLab, HealthcareService, Hospital, Pharmacy, User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse

router = APIRouter(prefix="/healthcare", tags=["healthcare-services"])

logger = logging.getLogger("medivision.api.healthcare")

FACILITY_MODELS = {
    "hospital": Hospital,
    "clinic": Clinic,
    "pharmacy": Pharmacy,
    "lab": DiagnosticLab,
}

TYPE_SPECIFIC_FIELDS = {
    "hospital": ["total_beds", "available_beds", "icu_beds", "available_icu_beds",
                 "emergency_capacity", "has_emergency", "departments"],
    "clinic": ["specialties", "doctors_count"],
    "pharmacy": ["has_delivery", "license_number"],
    "lab": ["tests_offered", "accreditation"],
}

COMMON_FIELDS = [
    "name", "address", "city", "state", "country", "phone", "email",
    "latitude", "longitude", "opening_hours", "website", "rating", "is_verified",
]


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    if lat2 is None or lng2 is None:
        return float("inf")
    radius = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * radius * asin(sqrt(a))


def _facility_json(model, distance_km: float | None = None) -> dict:
    base = {
        "id": model.id,
        "name": model.name,
        "address": model.address,
        "city": model.city,
        "state": model.state,
        "country": model.country,
        "phone": model.phone,
        "email": model.email,
        "latitude": model.latitude,
        "longitude": model.longitude,
        "opening_hours": model.opening_hours,
        "website": model.website,
        "rating": model.rating,
        "is_verified": model.is_verified,
        "distance_km": round(distance_km, 1) if distance_km is not None and distance_km != float("inf") else None,
    }
    if isinstance(model, Hospital):
        base.update({"facility_type": "hospital", **{
            "total_beds": model.total_beds,
            "available_beds": model.available_beds,
            "icu_beds": model.icu_beds,
            "available_icu_beds": model.available_icu_beds,
            "emergency_capacity": model.emergency_capacity,
            "has_emergency": model.has_emergency,
            "departments": _load_json(model.departments),
        }})
    elif isinstance(model, Clinic):
        base.update({"facility_type": "clinic", "specialties": _load_json(model.specialties),
                     "doctors_count": model.doctors_count})
    elif isinstance(model, Pharmacy):
        base.update({"facility_type": "pharmacy", "has_delivery": model.has_delivery,
                     "license_number": model.license_number})
    elif isinstance(model, DiagnosticLab):
        base.update({"facility_type": "lab", "tests_offered": _load_json(model.tests_offered),
                     "accreditation": model.accreditation})
    return base


def _service_json(service: HealthcareService) -> dict:
    return {
        "id": service.id,
        "facility_type": service.facility_type,
        "facility_id": service.facility_id,
        "service_name": service.service_name,
        "description": service.description,
        "price": service.price,
        "is_active": service.is_active,
    }


def _load_json(raw: str | None):
    if not raw:
        return None
    try:
        value = json.loads(raw)
        return value
    except (ValueError, TypeError):
        return None


def _get_facility(db: Session, facility_type: str, facility_id: int):
    model = FACILITY_MODELS.get(facility_type.strip().lower())
    if not model:
        raise ValidationException(
            f"Unknown facility type '{facility_type}'",
            details={"supported": sorted(FACILITY_MODELS)},
        )
    facility = db.get(model, facility_id)
    if not facility:
        raise NotFoundException(f"{facility_type} facility not found")
    return facility


# ------------------------------------------------------------------ read (patient)
@router.get("/facilities", response_model=PaginatedResponse)
async def list_facilities(
    facility_type: Optional[str] = Query(None, pattern="^(hospital|clinic|pharmacy|lab)$"),
    city: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lng: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: Optional[float] = Query(None, ge=1, le=500),
    emergency_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        models = [FACILITY_MODELS[facility_type]] if facility_type else list(FACILITY_MODELS.values())
        results = []
        for model in models:
            query = db.query(model)
            if city:
                query = query.filter(model.city.ilike(f"%{city}%"))
            if search:
                query = query.filter(model.name.ilike(f"%{search}%"))
            if emergency_only and model is Hospital:
                query = query.filter(Hospital.has_emergency.is_(True))
            for row in query.all():
                distance = _haversine(lat, lng, row.latitude, row.longitude) if lat is not None and lng is not None else None
                if radius_km is not None and distance is not None and distance > radius_km:
                    continue
                results.append((distance if distance is not None else float("inf"), _facility_json(row, distance)))
        results.sort(key=lambda pair: pair[0])
        items = [item for _, item in results]
        total = len(items)
        start = (page - 1) * page_size
        return PaginatedResponse(
            data=PaginatedData(
                items=items[start:start + page_size],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=(total + page_size - 1) // page_size,
            ),
            message=f"{total} facilities found",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to list facilities", exc_info=True)
        raise AppException("Failed to load facilities. Please try again.", code="healthcare_error")


@router.get("/facilities/{facility_type}/{facility_id}", response_model=ApiResponse[dict])
async def get_facility_detail(
    facility_type: str,
    facility_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        facility = _get_facility(db, facility_type, facility_id)
        key = facility_type.strip().lower()
        services = (
            db.query(HealthcareService)
            .filter(
                HealthcareService.facility_type == key,
                HealthcareService.facility_id == facility.id,
                HealthcareService.is_active.is_(True),
            )
            .all()
        )
        data = _facility_json(facility)
        data["services"] = [_service_json(s) for s in services]
        return ApiResponse(data=data, message="Facility details retrieved")
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to load facility detail", exc_info=True)
        raise AppException("Failed to load facility details. Please try again.", code="healthcare_error")


@router.get("/services", response_model=PaginatedResponse)
async def list_services(
    facility_type: Optional[str] = Query(None, pattern="^(hospital|clinic|pharmacy|lab)$"),
    facility_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        query = db.query(HealthcareService).filter(HealthcareService.is_active.is_(True))
        if facility_type:
            query = query.filter(HealthcareService.facility_type == facility_type.strip().lower())
        if facility_id:
            query = query.filter(HealthcareService.facility_id == facility_id)
        if search:
            query = query.filter(HealthcareService.service_name.ilike(f"%{search}%"))
        total = query.count()
        services = (
            query.order_by(HealthcareService.facility_type, HealthcareService.service_name)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return PaginatedResponse(
            data=PaginatedData(
                items=[_service_json(s) for s in services],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=(total + page_size - 1) // page_size,
            ),
            message=f"{total} services found",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to list services", exc_info=True)
        raise AppException("Failed to load services. Please try again.", code="healthcare_error")


# ------------------------------------------------------------------- write (admin)
class FacilityCreateRequest(BaseModel):
    facility_type: str = Field(pattern="^(hospital|clinic|pharmacy|lab)$")
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1)
    city: str = Field(min_length=1, max_length=120)
    state: Optional[str] = Field(default=None, max_length=120)
    country: str = "India"
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    opening_hours: Optional[str] = Field(default=None, max_length=200)
    website: Optional[str] = Field(default=None, max_length=300)
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    is_verified: bool = False
    type_fields: dict = Field(default_factory=dict)


class FacilityUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    address: Optional[str] = None
    city: Optional[str] = Field(default=None, min_length=1, max_length=120)
    state: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    opening_hours: Optional[str] = Field(default=None, max_length=200)
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    is_verified: Optional[bool] = None
    type_fields: dict = Field(default_factory=dict)


class ServiceCreateRequest(BaseModel):
    facility_type: str = Field(pattern="^(hospital|clinic|pharmacy|lab)$")
    facility_id: int
    service_name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    price: Optional[float] = Field(default=None, ge=0)
    is_active: bool = True


def _apply_fields(facility, values: dict, allowed: list[str]) -> None:
    for key, value in values.items():
        if key in allowed:
            setattr(facility, key, value)


@router.post("/admin/facilities", response_model=ApiResponse[dict])
async def create_facility(
    payload: FacilityCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        key = payload.facility_type.strip().lower()
        model = FACILITY_MODELS[key]
        invalid = [k for k in payload.type_fields if k not in TYPE_SPECIFIC_FIELDS[key]]
        if invalid:
            raise ValidationException(
                f"Unsupported type_fields for {key}",
                details={"unknown_fields": invalid, "allowed": TYPE_SPECIFIC_FIELDS[key]},
            )
        facility = model()
        _apply_fields(facility, payload.model_dump(), COMMON_FIELDS)
        _apply_fields(facility, payload.type_fields, TYPE_SPECIFIC_FIELDS[key])
        db.add(facility)
        db.flush()
        if "departments" in payload.type_fields and isinstance(payload.type_fields["departments"], list):
            facility.departments = json.dumps(payload.type_fields["departments"])
        if "specialties" in payload.type_fields and isinstance(payload.type_fields["specialties"], list):
            facility.specialties = json.dumps(payload.type_fields["specialties"])
        if "tests_offered" in payload.type_fields and isinstance(payload.type_fields["tests_offered"], list):
            facility.tests_offered = json.dumps(payload.type_fields["tests_offered"])
        db.commit()
        db.refresh(facility)
        return ApiResponse(data=_facility_json(facility), message=f"{key} facility created")
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to create facility", exc_info=True)
        raise AppException("Failed to create the facility. Please try again.", code="healthcare_error")


@router.patch("/admin/facilities/{facility_type}/{facility_id}", response_model=ApiResponse[dict])
async def update_facility(
    facility_type: str,
    facility_id: int,
    payload: FacilityUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        key = facility_type.strip().lower()
        facility = _get_facility(db, key, facility_id)
        invalid = [k for k in payload.type_fields if k not in TYPE_SPECIFIC_FIELDS[key]]
        if invalid:
            raise ValidationException(
                f"Unsupported type_fields for {key}",
                details={"unknown_fields": invalid, "allowed": TYPE_SPECIFIC_FIELDS[key]},
            )
        data = payload.model_dump(exclude_unset=True, exclude={"type_fields"})
        _apply_fields(facility, data, COMMON_FIELDS)
        _apply_fields(facility, payload.type_fields, TYPE_SPECIFIC_FIELDS[key])
        if "departments" in payload.type_fields and isinstance(payload.type_fields["departments"], list):
            facility.departments = json.dumps(payload.type_fields["departments"])
        if "specialties" in payload.type_fields and isinstance(payload.type_fields["specialties"], list):
            facility.specialties = json.dumps(payload.type_fields["specialties"])
        if "tests_offered" in payload.type_fields and isinstance(payload.type_fields["tests_offered"], list):
            facility.tests_offered = json.dumps(payload.type_fields["tests_offered"])
        db.commit()
        db.refresh(facility)
        return ApiResponse(data=_facility_json(facility), message="Facility updated")
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to update facility", exc_info=True)
        raise AppException("Failed to update the facility. Please try again.", code="healthcare_error")


@router.delete("/admin/facilities/{facility_type}/{facility_id}", response_model=ApiResponse[dict])
async def delete_facility(
    facility_type: str,
    facility_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        key = facility_type.strip().lower()
        facility = _get_facility(db, key, facility_id)
        db.query(HealthcareService).filter(
            HealthcareService.facility_type == key,
            HealthcareService.facility_id == facility_id,
        ).delete()
        db.delete(facility)
        db.commit()
        return ApiResponse(message=f"{key} facility deleted")
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to delete facility", exc_info=True)
        raise AppException("Failed to delete the facility. Please try again.", code="healthcare_error")


@router.post("/admin/services", response_model=ApiResponse[dict])
async def create_service(
    payload: ServiceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        key = payload.facility_type.strip().lower()
        _get_facility(db, key, payload.facility_id)
        service = HealthcareService(
            facility_type=key,
            facility_id=payload.facility_id,
            service_name=payload.service_name,
            description=payload.description,
            price=payload.price,
            is_active=payload.is_active,
        )
        db.add(service)
        db.commit()
        db.refresh(service)
        return ApiResponse(data=_service_json(service), message="Service created")
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to create service", exc_info=True)
        raise AppException("Failed to create the service. Please try again.", code="healthcare_error")