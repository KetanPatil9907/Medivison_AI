"""Risk prediction endpoints for chronic conditions.

DISCLAIMER: Results are screening heuristics (rule-based in fallback mode). They
are NOT diagnoses and do not replace assessment by a healthcare professional.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import require_patient
from app.core.database import get_db
from app.core.exceptions import AppException, NotFoundException
from app.core.config import settings
from app.models import AIExplanation, RiskAssessment, User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse
from app.services import risk_engine
from app.services.timeline_service import add_timeline_event, log_json
from app.utils.audit import write_audit_log

router = APIRouter(prefix="/risk", tags=["risk"])

logger = logging.getLogger("medivision.api.risk")

RISK_DISCLAIMER = (
    "This risk estimate is a screening heuristic and is not a clinical diagnosis. "
    "Please discuss your results with a qualified healthcare professional."
)


class RiskPredictRequest(BaseModel):
    condition_type: str = Field(description="diabetes|hypertension|heart_disease|ckd")
    inputs: dict = Field(default_factory=dict, description="Age, gender, bmi, lab values, lifestyle factors")


def _assessment_json(assessment: RiskAssessment, explanation: str | None = None) -> dict:
    return {
        "id": assessment.id,
        "condition_type": assessment.condition_type,
        "risk_level": assessment.risk_level,
        "risk_percentage": assessment.risk_percentage,
        "factors": _load_json(assessment.factors),
        "explanation": explanation or assessment.explanation,
        "recommendations": _load_json(assessment.recommendations),
        "input_data": _load_json(assessment.input_data),
        "model_name": assessment.model_name,
        "is_demo": assessment.is_demo,
        "created_at": assessment.created_at.isoformat() if assessment.created_at else None,
    }


def _load_json(raw: str | None):
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return value if isinstance(value, (list, dict)) else []
    except (ValueError, TypeError):
        return []


def _get_own_assessment(db: Session, user: User, assessment_id: int) -> RiskAssessment:
    assessment = db.get(RiskAssessment, assessment_id)
    if not assessment or assessment.patient_id != user.id:
        raise NotFoundException("Risk assessment not found")
    return assessment


@router.get("/supported", response_model=ApiResponse[dict])
async def supported_conditions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        return ApiResponse(
            data={
                "conditions": risk_engine.supported_conditions(),
                "engine_mode": "rule_based" if settings.ai_fallback_mode else "model",
                "disclaimer": RISK_DISCLAIMER,
            },
            message="Supported risk conditions retrieved",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to load supported risk conditions", exc_info=True)
        raise AppException("Failed to load supported conditions. Please try again.", code="risk_error")


@router.post("/predict", response_model=ApiResponse[dict])
async def predict_risk(
    payload: RiskPredictRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        analysis = risk_engine.analyze_risk(payload.condition_type, payload.inputs)

        assessment = RiskAssessment(
            patient_id=current_user.id,
            condition_type=analysis["condition_type"],
            risk_level=analysis["risk_level"],
            risk_percentage=analysis["risk_percentage"],
            factors=log_json(analysis["factors"]),
            explanation=analysis["explanation"],
            recommendations=log_json(analysis["recommendations"]),
            input_data=log_json(payload.inputs or {}),
            model_name=analysis["model_name"],
            is_demo=analysis["is_demo"],
        )
        db.add(assessment)
        db.flush()

        db.add(
            AIExplanation(
                risk_assessment_id=assessment.id,
                explanation_type="factors",
                content=log_json(
                    {
                        "factors": analysis["factors"],
                        "explanation": analysis["explanation"],
                    }
                ),
            )
        )
        db.flush()

        add_timeline_event(
            db,
            current_user.id,
            "risk_assessment",
            f"Risk assessment: {analysis['condition_label']}",
            description=f"Estimated {analysis['risk_level']} risk ({analysis['risk_percentage']:.0f}%)",
            severity=analysis["risk_level"],
            metadata_json=log_json(
                {
                    "assessment_id": assessment.id,
                    "condition_type": analysis["condition_type"],
                    "risk_percentage": analysis["risk_percentage"],
                    "risk_level": analysis["risk_level"],
                    "model_name": analysis["model_name"],
                }
            ),
        )

        db.commit()
        db.refresh(assessment)

        write_audit_log(
            db, current_user, "risk.predict",
            resource_type="risk_assessment", resource_id=str(assessment.id),
            after={
                "condition_type": analysis["condition_type"],
                "risk_percentage": analysis["risk_percentage"],
                "risk_level": analysis["risk_level"],
                "model_name": analysis["model_name"],
            },
        )
        data = _assessment_json(assessment)
        data["disclaimer"] = RISK_DISCLAIMER
        return ApiResponse(
            data=data,
            message=f"Risk assessment for {analysis['condition_label']} completed",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error(
            "Risk prediction failed",
            extra={"user_id": current_user.id, "error": str(exc)},
            exc_info=True,
        )
        raise AppException("Risk prediction failed. Please try again.", code="risk_error")


@router.get("/my-assessments", response_model=PaginatedResponse)
async def my_assessments(
    condition_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        base = db.query(RiskAssessment).filter(RiskAssessment.patient_id == current_user.id)
        if condition_type:
            base = base.filter(RiskAssessment.condition_type == condition_type.strip().lower())
        total = base.count()
        assessments = (
            base.order_by(RiskAssessment.created_at.desc(), RiskAssessment.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return PaginatedResponse(
            data=PaginatedData(
                items=[_assessment_json(a) for a in assessments],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=(total + page_size - 1) // page_size,
            ),
            message=f"{total} risk assessments. {RISK_DISCLAIMER}",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to list risk assessments", exc_info=True)
        raise AppException("Failed to load risk assessments. Please try again.", code="risk_error")


@router.get("/assessments/{assessment_id}", response_model=ApiResponse[dict])
async def get_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        assessment = _get_own_assessment(db, current_user, assessment_id)
        explanation = (
            db.query(AIExplanation)
            .filter(
                AIExplanation.risk_assessment_id == assessment_id,
                AIExplanation.explanation_type == "factors",
            )
            .order_by(AIExplanation.created_at.desc())
            .first()
        )
        data = _assessment_json(assessment)
        data["disclaimer"] = RISK_DISCLAIMER
        return ApiResponse(data=data, message="Risk assessment retrieved")
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to load risk assessment", exc_info=True)
        raise AppException("Failed to load the risk assessment. Please try again.", code="risk_error")


@router.delete("/assessments/{assessment_id}", response_model=ApiResponse[dict])
async def delete_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        assessment = _get_own_assessment(db, current_user, assessment_id)
        db.delete(assessment)
        db.commit()
        return ApiResponse(message="Risk assessment deleted")
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to delete risk assessment", exc_info=True)
        raise AppException("Failed to delete the risk assessment. Please try again.", code="risk_error")