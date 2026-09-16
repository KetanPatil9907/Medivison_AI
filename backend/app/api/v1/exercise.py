"""Weekly exercise plan endpoints.

Guidance is generated from fitness level and goal with basic medical-restriction
safety filtering. Plans are fitness guidance, not a medical prescription; advance
to new intensity levels only when comfortable and medically cleared.
"""

import json
import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import require_patient
from app.core.database import get_db
from app.core.exceptions import AppException, NotFoundException, ValidationException
from app.models import ExercisePlan, User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse
from app.services import exercise_engine
from app.services.timeline_service import add_timeline_event, log_json

router = APIRouter(prefix="/exercise", tags=["exercise"])

logger = logging.getLogger("medivision.api.exercise")

EXERCISE_DISCLAIMER = (
    "Exercise guidance is educational and not medical advice. Stop if you feel pain, "
    "dizzy or breathless, and consult a professional before new intense routines "
    "especially with existing health conditions."
)

FITNESS_PATTERN = "^(beginner|intermediate|advanced)$"
GOAL_PATTERN = "^(general_fitness|weight_loss|muscle_gain|endurance|flexibility)$"


class ExercisePlanRequest(BaseModel):
    fitness_level: str = Field(default="beginner", pattern=FITNESS_PATTERN)
    goal: str = Field(default="general_fitness", pattern=GOAL_PATTERN)
    medical_restrictions: Optional[list[str]] = Field(default_factory=list, description="e.g. knee, back, heart")


class ProgressRequest(BaseModel):
    week: int = Field(ge=1, le=520)
    completed_sessions: int = Field(ge=0, le=7)
    notes: Optional[str] = Field(default=None, max_length=500)


def _plan_json(plan: ExercisePlan) -> dict:
    return {
        "id": plan.id,
        "plan_start": plan.plan_start.isoformat() if plan.plan_start else None,
        "fitness_level": plan.fitness_level,
        "goal": plan.goal,
        "weekly_plan": _load_list(plan.weekly_plan),
        "medical_restrictions": _load_list(plan.medical_restrictions),
        "progress": _load_dict(plan.progress),
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
    }


def _load_list(raw: str | None):
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except (ValueError, TypeError):
        return []


def _load_dict(raw: str | None):
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def _get_own_plan(db: Session, user: User, plan_id: int) -> ExercisePlan:
    plan = db.get(ExercisePlan, plan_id)
    if not plan or plan.patient_id != user.id:
        raise NotFoundException("Exercise plan not found")
    return plan


@router.post("/plan", response_model=ApiResponse[dict])
async def create_exercise_plan(
    payload: ExercisePlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        result = exercise_engine.generate_plan(
            fitness_level=payload.fitness_level,
            goal=payload.goal,
            medical_restrictions=payload.medical_restrictions,
        )
        plan = ExercisePlan(
            patient_id=current_user.id,
            plan_start=date.today(),
            fitness_level=result["fitness_level"],
            goal=result["goal"],
            weekly_plan=log_json(result["weekly_plan"]),
            medical_restrictions=log_json(result["restrictions_applied"]),
            progress="{}",
        )
        db.add(plan)
        db.flush()

        add_timeline_event(
            db,
            current_user.id,
            "health_event",
            "Weekly exercise plan generated",
            description=f"{result['goal'].replace('_', ' ')} / {result['fitness_level']} "
                        f"({result['total_minutes_per_week']} min/week)",
            event_date=date.today(),
            metadata_json=log_json(
                {
                    "plan_id": plan.id,
                    "fitness_level": result["fitness_level"],
                    "goal": result["goal"],
                    "total_minutes_per_week": result["total_minutes_per_week"],
                }
            ),
        )
        db.commit()
        db.refresh(plan)
        data = _plan_json(plan)
        data["restriction_notes"] = result["restriction_notes"]
        data["disclaimer"] = EXERCISE_DISCLAIMER
        return ApiResponse(data=data, message="Weekly exercise plan generated")
    except AppException:
        raise
    except Exception as exc:
        logger.error(
            "Exercise plan generation failed",
            extra={"user_id": current_user.id, "error": str(exc)},
            exc_info=True,
        )
        raise AppException("Failed to generate the exercise plan. Please try again.", code="exercise_error")


@router.get("/plan/current", response_model=ApiResponse[dict])
async def current_exercise_plan(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        plan = (
            db.query(ExercisePlan)
            .filter(ExercisePlan.patient_id == current_user.id)
            .order_by(ExercisePlan.created_at.desc(), ExercisePlan.id.desc())
            .first()
        )
        if not plan:
            raise NotFoundException(
                "No exercise plan yet. Generate one with POST /exercise/plan"
            )
        data = _plan_json(plan)
        data["disclaimer"] = EXERCISE_DISCLAIMER
        return ApiResponse(data=data, message="Current exercise plan retrieved")
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to load current exercise plan", exc_info=True)
        raise AppException("Failed to load the exercise plan. Please try again.", code="exercise_error")


@router.get("/plans", response_model=PaginatedResponse)
async def list_exercise_plans(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        base = db.query(ExercisePlan).filter(ExercisePlan.patient_id == current_user.id)
        total = base.count()
        plans = (
            base.order_by(ExercisePlan.created_at.desc(), ExercisePlan.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return PaginatedResponse(
            data=PaginatedData(
                items=[_plan_json(p) for p in plans],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=(total + page_size - 1) // page_size,
            ),
            message=f"{total} exercise plans. {EXERCISE_DISCLAIMER}",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to list exercise plans", exc_info=True)
        raise AppException("Failed to load exercise plans. Please try again.", code="exercise_error")


@router.get("/plans/{plan_id}", response_model=ApiResponse[dict])
async def get_exercise_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        plan = _get_own_plan(db, current_user, plan_id)
        data = _plan_json(plan)
        data["disclaimer"] = EXERCISE_DISCLAIMER
        return ApiResponse(data=data, message="Exercise plan retrieved")
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to load exercise plan", exc_info=True)
        raise AppException("Failed to load the exercise plan. Please try again.", code="exercise_error")


@router.put("/plans/{plan_id}/progress", response_model=ApiResponse[dict])
async def update_exercise_progress(
    plan_id: int,
    payload: ProgressRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        plan = _get_own_plan(db, current_user, plan_id)
        progress = _load_dict(plan.progress)
        progress[str(payload.week)] = {
            "completed_sessions": payload.completed_sessions,
            "notes": payload.notes,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        plan.progress = log_json(progress)
        db.commit()
        data = _plan_json(plan)
        data["disclaimer"] = EXERCISE_DISCLAIMER
        return ApiResponse(data=data, message="Exercise progress updated")
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to update exercise progress", exc_info=True)
        raise AppException("Failed to update progress. Please try again.", code="exercise_error")


@router.delete("/plans/{plan_id}", response_model=ApiResponse[dict])
async def delete_exercise_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        plan = _get_own_plan(db, current_user, plan_id)
        db.delete(plan)
        db.commit()
        return ApiResponse(message="Exercise plan deleted")
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to delete exercise plan", exc_info=True)
        raise AppException("Failed to delete the exercise plan. Please try again.", code="exercise_error")