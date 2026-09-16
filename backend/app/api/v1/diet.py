"""Personalised daily diet plans.

Uses the patient's profile (or explicit inputs) to compute BMI, BMR, TDEE and
macronutrient targets plus meal suggestions. Educational guidance only - not
clinical nutrition advice.
"""

import json
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import require_patient
from app.core.database import get_db
from app.core.exceptions import AppException, NotFoundException, ValidationException
from app.models import DietPlan, User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse
from app.services import diet_engine
from app.services.timeline_service import add_timeline_event, log_json

router = APIRouter(prefix="/diet", tags=["diet"])

logger = logging.getLogger("medivision.api.diet")

DIET_DISCLAIMER = (
    "This plan is general dietary guidance and is not a substitute for advice from "
    "a qualified nutritionist or physician."
)

GOAL_PATTERN = "^(weight_loss|weight_gain|muscle_gain|maintain)$"
ACTIVITY_PATTERN = "^(sedentary|light|moderate|active|very_active)$"
PREFERENCE_PATTERN = "^(non_vegetarian|vegetarian|vegan)$"


class DietCalculatorRequest(BaseModel):
    height_cm: float = Field(gt=0, le=250)
    weight_kg: float = Field(gt=0, le=400)
    age: int = Field(ge=10, le=120)
    gender: str = Field(pattern="^(male|female)$")
    activity_level: str = Field(default="moderate", pattern=ACTIVITY_PATTERN)


class DietPlanRequest(BaseModel):
    goal: str = Field(default="maintain", pattern=GOAL_PATTERN)
    dietary_preference: str = Field(default="non_vegetarian", pattern=PREFERENCE_PATTERN)
    activity_level: Optional[str] = Field(default=None, pattern=ACTIVITY_PATTERN)
    plan_date: Optional[date] = None


def _plan_json(plan: DietPlan) -> dict:
    return {
        "id": plan.id,
        "plan_date": plan.plan_date.isoformat() if plan.plan_date else None,
        "bmi": plan.bmi,
        "bmr": plan.bmr,
        "tdee": plan.tdee,
        "calorie_target": plan.calorie_target,
        "protein_g": plan.protein_g,
        "carbs_g": plan.carbs_g,
        "fat_g": plan.fat_g,
        "water_liters": plan.water_liters,
        "goal": plan.goal,
        "dietary_preference": plan.dietary_preference,
        "breakfast": _load_json(plan.breakfast),
        "lunch": _load_json(plan.lunch),
        "dinner": _load_json(plan.dinner),
        "snacks": _load_json(plan.snacks),
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
    }


def _load_json(raw: str | None):
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except (ValueError, TypeError):
        return []


def _get_own_plan(db: Session, user: User, plan_id: int) -> DietPlan:
    plan = db.get(DietPlan, plan_id)
    if not plan or plan.patient_id != user.id:
        raise NotFoundException("Diet plan not found")
    return plan


def _profile_inputs(db: Session, user: User, payload: DietPlanRequest) -> dict:
    profile = user.patient_profile
    if not profile:
        raise ValidationException(
            "Complete your patient profile first (height, weight, age) to generate a plan",
            details={"profile_required": True},
        )
    height = profile.height_cm
    weight = profile.weight_kg
    if not height or not weight:
        raise ValidationException(
            "Height and weight are missing from your profile. First use the profile API "
            "to update them, or use the calculator endpoint for a preview.",
            details={"requires": ["height_cm", "weight_kg"]},
        )
    return {
        "gender": profile.gender or "female",
        "age": profile.age or 30,
        "height_cm": float(height),
        "weight_kg": float(weight),
        "activity_level": payload.activity_level or profile.activity_level or "moderate",
        "goal": payload.goal,
        "dietary_preference": payload.dietary_preference or profile.dietary_preference or "non_vegetarian",
    }


@router.get("/calculator", response_model=ApiResponse[dict])
async def diet_calculator(
    height_cm: float = Query(gt=0, le=250),
    weight_kg: float = Query(gt=0, le=400),
    age: int = Query(ge=10, le=120),
    gender: str = Query(pattern="^(male|female)$"),
    activity_level: str = Query(default="moderate", pattern=ACTIVITY_PATTERN),
    goal: str = Query(default="maintain", pattern=GOAL_PATTERN),
    dietary_preference: str = Query(default="non_vegetarian", pattern=PREFERENCE_PATTERN),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        anthro = diet_engine.compute_anthropometrics(gender, age, height_cm, weight_kg, activity_level)
        targets = diet_engine.daily_targets(anthro["tdee"], goal, weight_kg, dietary_preference)
        return ApiResponse(
            data={
                **anthro,
                **targets,
                "disclaimer": DIET_DISCLAIMER,
            },
            message="Nutrition calculator output",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Diet calculator failed", exc_info=True)
        raise AppException("Could not compute nutrition targets. Please try again.", code="diet_error")


@router.post("/plan", response_model=ApiResponse[dict])
async def create_diet_plan(
    payload: DietPlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        inputs = _profile_inputs(db, current_user, payload)
        plan_data = diet_engine.generate_plan(**inputs)
        if not plan_data["valid"]:
            raise ValidationException(plan_data["error"])

        plan_date = payload.plan_date or date.today()
        existing = (
            db.query(DietPlan)
            .filter(DietPlan.patient_id == current_user.id, DietPlan.plan_date == plan_date)
            .first()
        )
        if existing:
            plan = existing
        else:
            plan = DietPlan(patient_id=current_user.id, plan_date=plan_date)
            db.add(plan)

        plan.bmi = plan_data["bmi"]
        plan.bmr = plan_data["bmr"]
        plan.tdee = plan_data["tdee"]
        plan.calorie_target = plan_data["calorie_target"]
        plan.protein_g = plan_data["protein_g"]
        plan.carbs_g = plan_data["carbs_g"]
        plan.fat_g = plan_data["fat_g"]
        plan.water_liters = plan_data["water_liters"]
        plan.breakfast = log_json(plan_data["meals"]["breakfast"])
        plan.lunch = log_json(plan_data["meals"]["lunch"])
        plan.dinner = log_json(plan_data["meals"]["dinner"])
        plan.snacks = log_json(plan_data["meals"]["snacks"])
        plan.goal = plan_data["goal"]
        plan.dietary_preference = plan_data["dietary_preference"]
        db.flush()

        add_timeline_event(
            db,
            current_user.id,
            "health_event",
            "Daily diet plan generated",
            description=f"{plan_data['calorie_target']} kcal target for {plan_date.isoformat()}",
            event_date=plan_date,
            metadata_json=log_json(
                {
                    "plan_id": plan.id,
                    "plan_date": plan_date.isoformat(),
                    "calorie_target": plan_data["calorie_target"],
                    "goal": plan_data["goal"],
                }
            ),
        )
        db.commit()
        db.refresh(plan)
        data = _plan_json(plan)
        data["disclaimer"] = DIET_DISCLAIMER
        return ApiResponse(data=data, message="Diet plan generated")
    except AppException:
        raise
    except Exception as exc:
        logger.error(
            "Diet plan generation failed",
            extra={"user_id": current_user.id, "error": str(exc)},
            exc_info=True,
        )
        raise AppException("Failed to generate the diet plan. Please try again.", code="diet_error")


@router.get("/plans", response_model=PaginatedResponse)
async def list_diet_plans(
    goal: Optional[str] = Query(None, pattern=GOAL_PATTERN),
    dietary_preference: Optional[str] = Query(None, pattern=PREFERENCE_PATTERN),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        base = db.query(DietPlan).filter(DietPlan.patient_id == current_user.id)
        if goal:
            base = base.filter(DietPlan.goal == goal)
        if dietary_preference:
            base = base.filter(DietPlan.dietary_preference == dietary_preference)
        if from_date:
            base = base.filter(DietPlan.plan_date >= from_date)
        if to_date:
            base = base.filter(DietPlan.plan_date <= to_date)
        total = base.count()
        plans = (
            base.order_by(DietPlan.plan_date.desc(), DietPlan.id.desc())
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
            message=f"{total} diet plans. {DIET_DISCLAIMER}",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to list diet plans", exc_info=True)
        raise AppException("Failed to load diet plans. Please try again.", code="diet_error")


@router.get("/plans/{plan_id}", response_model=ApiResponse[dict])
async def get_diet_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        plan = _get_own_plan(db, current_user, plan_id)
        data = _plan_json(plan)
        data["disclaimer"] = DIET_DISCLAIMER
        return ApiResponse(data=data, message="Diet plan retrieved")
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to load diet plan", exc_info=True)
        raise AppException("Failed to load the diet plan. Please try again.", code="diet_error")


@router.delete("/plans/{plan_id}", response_model=ApiResponse[dict])
async def delete_diet_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        plan = _get_own_plan(db, current_user, plan_id)
        db.delete(plan)
        db.commit()
        return ApiResponse(message="Diet plan deleted")
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to delete diet plan", exc_info=True)
        raise AppException("Failed to delete the diet plan. Please try again.", code="diet_error")