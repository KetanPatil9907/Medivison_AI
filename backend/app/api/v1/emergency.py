"""Emergency assistance: hotlines, nearby emergency-capable hospitals, first-aid
protocols and SOS escalation (timeline record + nearest facility + contacts).

IMPORTANT: platform guidance never replaces calling local emergency services.
In a real emergency, call your local emergency number first.
"""

import logging
from math import asin, cos, radians, sin, sqrt
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import require_patient
from app.core.database import get_db
from app.core.exceptions import AppException, ValidationException
from app.models import Clinic, DiagnosticLab, EmergencyContact, Hospital, Pharmacy, User
from app.schemas.common import ApiResponse
from app.services.timeline_service import add_timeline_event, log_json

router = APIRouter(prefix="/emergency", tags=["emergency"])

logger = logging.getLogger("medivision.api.emergency")

EMERGENCY_DISCLAIMER = (
    "This information is a directory and safety aid only. In an actual emergency, "
    "call your local emergency number (e.g. 112/108/911) immediately. Do not wait "
    "for online guidance before seeking urgent care."
)

EMERGENCY_HOTLINES = [
    {"country": "India", "label": "National Emergency Helpline", "number": "112", "type": "universal"},
    {"country": "India", "label": "Ambulance (Emergency)", "number": "108", "type": "ambulance"},
    {"country": "India", "label": "Fire", "number": "101", "type": "fire"},
    {"country": "India", "label": "Police", "number": "100", "type": "police"},
    {"country": "India", "label": "Women Helpline", "number": "1091", "type": "helpline"},
    {"country": "India", "label": "Child Helpline", "number": "1098", "type": "helpline"},
    {"country": "India", "label": "Mental Health (Tele-MANAS)", "number": "14416", "type": "mental_health"},
    {"country": "USA", "label": "Emergency", "number": "911", "type": "universal"},
    {"country": "EU/UK", "label": "Emergency", "number": "112", "type": "universal"},
    {"country": "International", "label": "India Consular / NRI Helpline", "number": "1800-111-777", "type": "helpline"},
]

PROTOCOLS = [
    {
        "id": "cardiac_arrest",
        "title": "Cardiac arrest / unconscious, not breathing",
        "steps": [
            "Call emergency services immediately.",
            "Start chest compressions at 100-120/min, 5-6 cm deep.",
            "If trained and AED available, use it as soon as possible.",
        ],
        "caution": "Do not stop compressions except to use an AED or rescue breaths.",
    },
    {
        "id": "choking",
        "title": "Choking (conscious adult)",
        "steps": [
            "Ask if they can speak/cough.",
            "5 back blows between the shoulder blades.",
            "5 abdominal thrusts (Heimlich), alternating.",
        ],
        "caution": "Call emergency services if the obstruction does not clear.",
    },
    {
        "id": "bleeding",
        "title": "Severe bleeding",
        "steps": [
            "Apply firm direct pressure with a clean cloth.",
            "Keep the injured area raised above the heart if possible.",
            "Do not remove soaked dressings - add more on top.",
        ],
        "caution": "Seek care immediately for heavy or uncontrolled bleeding.",
    },
    {
        "id": "stroke",
        "title": "Possible stroke (BE-FAST)",
        "steps": [
            "Note the time symptoms started.",
            "Balance: sudden loss of balance? Eyes: vision change? Face drooping? Arm weakness? Speech slurred?",
            "If any sign, call emergency services - do not drive yourself.",
        ],
        "caution": "Do not give food, drink or medication until evaluated.",
    },
    {
        "id": "seizure",
        "title": "Seizure",
        "steps": [
            "Protect the head, move furniture away.",
            "Time the seizure; place them on their side when it ends.",
            "Stay with them until fully alert.",
        ],
        "caution": "Do not restrain them or put anything in the mouth.",
    },
    {
        "id": "allergic_reaction",
        "title": "Severe allergic reaction (anaphylaxis)",
        "steps": [
            "Call emergency services immediately.",
            "Administer epinephrine auto-injector if available and trained.",
            "Lay the person down with legs raised (unless breathing is difficult).",
        ],
        "caution": "Swelling of the lips/tongue, or breathing difficulty, is an emergency.",
    },
    {
        "id": "burn",
        "title": "Burn",
        "steps": [
            "Cool with running water for at least 10 minutes.",
            "Remove rings/jewellery near the burn.",
            "Cover loosely with a clean, non-fluffy cloth.",
        ],
        "caution": "Do not apply ice, creams or burst blisters.",
    },
    {
        "id": "heat_stroke",
        "title": "Heat stroke",
        "steps": [
            "Call emergency services.",
            "Move to shade, remove excess clothing.",
            "Cool with water-soaked cloths / fan while waiting.",
        ],
        "caution": "Do not give fluids if they are unconscious.",
    },
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
    common = {
        "name": model.name,
        "address": model.address,
        "city": model.city,
        "state": model.state,
        "phone": model.phone,
        "latitude": model.latitude,
        "longitude": model.longitude,
        "opening_hours": model.opening_hours,
        "rating": model.rating,
        "is_verified": model.is_verified,
        "distance_km": round(distance_km, 1) if distance_km is not None and distance_km != float("inf") else None,
    }
    if isinstance(model, Hospital):
        common.update(
            {
                "facility_type": "hospital",
                "total_beds": model.total_beds,
                "available_beds": model.available_beds,
                "icu_beds": model.icu_beds,
                "available_icu_beds": model.available_icu_beds,
                "emergency_capacity": model.emergency_capacity,
                "has_emergency": model.has_emergency,
                "departments": model.departments,
            }
        )
    elif isinstance(model, Clinic):
        common.update({"facility_type": "clinic", "specialties": model.specialties, "doctors_count": model.doctors_count})
    elif isinstance(model, Pharmacy):
        common.update({"facility_type": "pharmacy", "has_delivery": model.has_delivery, "license_number": model.license_number})
    elif isinstance(model, DiagnosticLab):
        common.update({"facility_type": "lab", "tests_offered": model.tests_offered, "accreditation": model.accreditation})
    common["id"] = model.id
    return common


FACILITY_MODELS = {
    "hospital": Hospital,
    "clinic": Clinic,
    "pharmacy": Pharmacy,
    "lab": DiagnosticLab,
}


@router.get("/hotlines", response_model=ApiResponse[dict])
async def emergency_hotlines(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        return ApiResponse(
            data={
                "hotlines": EMERGENCY_HOTLINES,
                "universal": "112 works in most countries and routes to local services.",
                "disclaimer": EMERGENCY_DISCLAIMER,
            },
            message="Emergency hotlines retrieved",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to load hotlines", exc_info=True)
        raise AppException("Failed to load emergency contacts. Please try again.", code="emergency_error")


@router.get("/nearby", response_model=ApiResponse[dict])
async def emergency_nearby(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius_km: float = Query(25.0, ge=1, le=200),
    facility_type: Optional[str] = Query(None, pattern="^(hospital|clinic|pharmacy|lab)$"),
    emergency_only: bool = Query(True, description="Only include facilities with emergency services"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        models = [FACILITY_MODELS[facility_type]] if facility_type else [Hospital]
        results = []
        for model in models:
            query = db.query(model)
            if model is Hospital and emergency_only:
                query = query.filter(Hospital.has_emergency.is_(True))
            rows = query.all()
            for row in rows:
                distance = _haversine(lat, lng, row.latitude, row.longitude)
                if distance <= radius_km:
                    results.append((distance, _facility_json(row, distance)))
        results.sort(key=lambda pair: pair[0])
        items = [item for _, item in results]
        return ApiResponse(
            data={
                "origin": {"lat": lat, "lng": lng, "radius_km": radius_km},
                "count": len(items),
                "facilities": items[:50],
                "disclaimer": EMERGENCY_DISCLAIMER,
            },
            message=f"{len(items)} emergency-capable facilities found near you",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to search nearby facilities",
            extra={"lat": lat, "lng": lng, "error": str(exc)},
            exc_info=True,
        )
        raise AppException("Failed to find nearby facilities. Please try again.", code="emergency_error")


@router.get("/protocols", response_model=ApiResponse[dict])
async def first_aid_protocols(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        return ApiResponse(
            data={
                "protocols": PROTOCOLS,
                "disclaimer": EMERGENCY_DISCLAIMER,
            },
            message="First-aid protocols retrieved",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to load protocols", exc_info=True)
        raise AppException("Failed to load first-aid protocols. Please try again.", code="emergency_error")


class SOSRequest(BaseModel):
    note: Optional[str] = None


@router.post("/sos", response_model=ApiResponse[dict])
async def trigger_sos(
    payload: SOSRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        contacts = []
        if current_user.patient_profile:
            contacts = [
                {
                    "name": c.name,
                    "phone": c.phone,
                    "relation": c.relation,
                    "is_primary": c.is_primary,
                }
                for c in (
                    db.query(EmergencyContact)
                    .filter(EmergencyContact.patient_profile_id == current_user.patient_profile.id)
                    .order_by(EmergencyContact.is_primary.desc())
                    .all()
                )
            ]
        profile = current_user.patient_profile
        location = None
        if profile:
            if profile.city:
                location = {"city": profile.city, "state": profile.state}

        nearest = None
        if profile and profile.city:
            nearest_hospital = (
                db.query(Hospital)
                .filter(
                    Hospital.has_emergency.is_(True),
                    Hospital.city.ilike(f"%{profile.city}%"),
                )
                .order_by(Hospital.available_beds.desc().nullslast())
                .first()
            )
            if nearest_hospital:
                nearest = _facility_json(nearest_hospital, None)

        add_timeline_event(
            db,
            current_user.id,
            "health_event",
            "SOS triggered",
            description=payload.note or "Emergency assistance requested from the app",
            severity="emergency",
            metadata_json=log_json(
                {
                    "note": payload.note,
                    "location": location,
                    "via": "manual_sos",
                }
            ),
        )
        db.commit()
        return ApiResponse(
            data={
                "acknowledged": True,
                "emergency_contacts": contacts,
                "location_context": location,
                "nearest_emergency_hospital": nearest,
                "hotlines": EMERGENCY_HOTLINES[:5],
                "disclaimer": EMERGENCY_DISCLAIMER,
            },
            message="SOS recorded. In an active emergency call your local emergency number now.",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error(
            "SOS trigger failed",
            extra={"user_id": current_user.id, "error": str(exc)},
            exc_info=True,
        )
        raise AppException("Failed to record SOS. Please try again.", code="emergency_error")