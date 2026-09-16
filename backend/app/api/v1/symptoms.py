"""Symptom checker endpoints.

CRITICAL SAFETY: The symptom checker is a triage-style screening aid. Outputs are
candidate conditions with confidence scores and severity flags. It is NOT a
diagnosis and never replaces care by a qualified healthcare professional. Every
result payload carries a medical disclaimer.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import require_patient
from app.core.database import get_db
from app.core.exceptions import AppException, NotFoundException, ValidationException
from app.models import SymptomResult, SymptomSession, User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse
from app.services import symptom_engine
from app.services.timeline_service import add_timeline_event, log_json
from app.utils.audit import write_audit_log

router = APIRouter(prefix="/symptoms", tags=["symptoms"])

logger = logging.getLogger("medivision.api.symptoms")

SYMPTOM_DISCLAIMER = (
    "This screening is for informational purposes only and is not a diagnosis or "
    "medical advice. Please consult a qualified healthcare professional for an "
    "accurate evaluation."
)


class SymptomCheckRequest(BaseModel):
    symptoms: list[str] = Field(min_length=1, max_length=20, description="Symptom names e.g. fever, headache")
    symptoms_text: Optional[str] = Field(default=None, max_length=2000)
    duration_days: Optional[int] = Field(default=None, ge=0, le=3650)


def _session_json(session: SymptomSession, results: list[SymptomResult] | None = None) -> dict:
    rows = results if results is not None else list(session.results)
    return {
        "id": session.id,
        "mode": session.mode,
        "status": session.status,
        "symptoms_text": session.symptoms_text,
        "duration_days": session.duration_days,
        "selected_symptoms": _load_json(session.selected_symptoms),
        "emergency_flag": any(r.emergency_flag for r in rows),
        "results": [_result_json(r) for r in rows],
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }


def _result_json(result: SymptomResult) -> dict:
    return {
        "id": result.id,
        "condition_name": result.condition_name,
        "confidence": result.confidence,
        "severity": result.severity,
        "recommended_specialty": result.recommended_specialty,
        "emergency_flag": result.emergency_flag,
        "advice": result.advice,
        "model": result.model,
    }


def _load_json(raw: str | None):
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except (ValueError, TypeError):
        return []


def _get_own_session(db: Session, user: User, session_id: int) -> SymptomSession:
    session = db.get(SymptomSession, session_id)
    if not session or session.patient_id != user.id:
        raise NotFoundException("Symptom session not found")
    return session


@router.get("/catalog", response_model=ApiResponse[dict])
async def symptom_catalog(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        catalog = symptom_engine.build_catalog()
        return ApiResponse(
            data={
                "symptoms": catalog,
                "count": len(catalog),
                "note": "Names are normalised; the checker matches these exact terms. "
                        "Use the text field to add detail in your own words.",
            },
            message="Symptom catalog retrieved",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to load symptom catalog", exc_info=True)
        raise AppException("Failed to load the symptom catalog. Please try again.", code="symptom_error")


@router.post("/check", response_model=ApiResponse[dict])
async def check_symptoms(
    payload: SymptomCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        analysis = symptom_engine.analyze_symptoms(
            symptoms=payload.symptoms,
            duration_days=payload.duration_days,
            symptoms_text=payload.symptoms_text,
        )
        if not analysis["results"]:
            raise ValidationException(
                "No known symptoms were recognised. Review the catalog and try again.",
                details={"recognized": analysis["normalized_symptoms"]},
            )

        session = SymptomSession(
            patient_id=current_user.id,
            selected_symptoms=log_json(analysis["normalized_symptoms"]),
            symptoms_text=payload.symptoms_text,
            duration_days=payload.duration_days,
            mode=analysis["mode"],
            status="completed",
        )
        db.add(session)
        db.flush()

        for result in analysis["results"]:
            db.add(
                SymptomResult(
                    session_id=session.id,
                    condition_name=result["condition_name"],
                    confidence=result["confidence"],
                    severity=result["severity"],
                    recommended_specialty=result["recommended_specialty"],
                    emergency_flag=result["emergency_flag"],
                    advice=result["advice"],
                    model="rule_based",
                )
            )
        db.flush()

        add_timeline_event(
            db,
            current_user.id,
            "ai_analysis",
            "Symptom check completed",
            description=f"Screening matched {len(analysis['results'])} condition(s); "
                        f"top: {analysis['results'][0]['condition_name']}",
            severity="emergency" if analysis["emergency_flag"] else (analysis["results"][0]["severity"] if analysis["results"] else None),
            metadata_json=log_json(
                {
                    "session_id": session.id,
                    "symptom_count": len(analysis["normalized_symptoms"]),
                    "emergency_flag": analysis["emergency_flag"],
                    "suggested_specialty": analysis["suggested_specialty"],
                    "mode": analysis["mode"],
                }
            ),
        )

        db.commit()
        db.refresh(session)

        write_audit_log(
            db, current_user, "symptoms.check",
            resource_type="symptom_session", resource_id=str(session.id),
            after={
                "symptoms": analysis["normalized_symptoms"],
                "duration_days": payload.duration_days,
                "emergency_flag": analysis["emergency_flag"],
                "results": [r["condition_name"] for r in analysis["results"]],
            },
        )
        data = _session_json(session)
        data["disclaimer"] = SYMPTOM_DISCLAIMER
        data["suggested_specialty"] = analysis["suggested_specialty"]
        data["duration_note"] = analysis["duration_note"]
        return ApiResponse(
            data=data,
            message="Symptom screening completed. This is not a diagnosis.",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error(
            "Symptom check failed",
            extra={"user_id": current_user.id, "error": str(exc)},
            exc_info=True,
        )
        raise AppException("Symptom screening failed. Please try again.", code="symptom_error")


@router.get("/my-sessions", response_model=PaginatedResponse)
async def my_symptom_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        base = db.query(SymptomSession).filter(SymptomSession.patient_id == current_user.id)
        total = base.count()
        sessions = (
            base.order_by(SymptomSession.created_at.desc(), SymptomSession.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return PaginatedResponse(
            data=PaginatedData(
                items=[_session_json(s) for s in sessions],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=(total + page_size - 1) // page_size,
            ),
            message=f"{total} symptom sessions. {SYMPTOM_DISCLAIMER}",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to list symptom sessions", exc_info=True)
        raise AppException("Failed to load symptom sessions. Please try again.", code="symptom_error")


@router.get("/sessions/{session_id}", response_model=ApiResponse[dict])
async def get_symptom_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        session = _get_own_session(db, current_user, session_id)
        results = (
            db.query(SymptomResult)
            .filter(SymptomResult.session_id == session_id)
            .order_by(SymptomResult.confidence.desc())
            .all()
        )
        data = _session_json(session, results)
        data["disclaimer"] = SYMPTOM_DISCLAIMER
        return ApiResponse(data=data, message="Symptom session retrieved")
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to load symptom session", exc_info=True)
        raise AppException("Failed to load the symptom session. Please try again.", code="symptom_error")


@router.delete("/sessions/{session_id}", response_model=ApiResponse[dict])
async def delete_symptom_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        session = _get_own_session(db, current_user, session_id)
        db.delete(session)
        db.commit()
        return ApiResponse(message="Symptom session deleted")
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to delete symptom session", exc_info=True)
        raise AppException("Failed to delete the symptom session. Please try again.", code="symptom_error")