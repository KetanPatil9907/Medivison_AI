"""Daily diet plan engine: anthropometrics, calorie targets and meal suggestions.

Uses the Mifflin-St Jeor equation for BMR and standard activity multipliers.
Meal suggestions are curated templates meant as a starting point, not as
replacement for an accredited dietitian's advice.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("medivision.services.diet")

ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

GOAL_ADJUSTMENT = {
    "weight_loss": -500,
    "weight_gain": 300,
    "muscle_gain": 250,
    "maintain": 0,
}


def compute_anthropometrics(
    gender: str,
    age: int,
    height_cm: float,
    weight_kg: float,
    activity_level: str = "moderate",
) -> dict:
    is_male = (gender or "female").strip().lower().startswith("m")
    if not height_cm or height_cm <= 0 or not weight_kg or weight_kg <= 0:
        return {
            "bmi": None,
            "bmr": None,
            "tdee": None,
            "valid": False,
        }
    bmi = round(weight_kg / ((height_cm / 100) ** 2), 1)
    if is_male:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    bmr = round(bmr, 1)
    factor = ACTIVITY_FACTORS.get(activity_level, 1.55)
    tdee = round(bmr * factor, 1)
    return {
        "bmi": bmi,
        "bmr": bmr,
        "tdee": tdee,
        "activity_factor": factor,
        "valid": True,
    }


def daily_targets(
    tdee: float,
    goal: str = "maintain",
    weight_kg: float = 70,
    dietary_preference: str = "non_vegetarian",
) -> dict:
    adjustment = GOAL_ADJUSTMENT.get(goal, 0)
    calorie_target = max(1200.0, round(tdee + adjustment))

    protein_per_kg = 1.6 if goal == "weight_loss" else (1.8 if goal in ("muscle_gain", "weight_gain") else 1.2)
    if dietary_preference in ("vegetarian", "vegan"):
        protein_per_kg = min(protein_per_kg, 1.5)
    protein_g = round(weight_kg * protein_per_kg)

    fat_calories = calorie_target * 0.25
    fat_g = round(fat_calories / 9)

    carb_calories = max(0, calorie_target - (protein_g * 4) - fat_calories)
    carbs_g = round(carb_calories / 4)

    water_liters = round(weight_kg * 0.033, 1)
    return {
        "calorie_target": calorie_target,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
        "water_liters": water_liters,
    }


MEAL_OPTIONS: dict[str, dict[str, list[dict]]] = {
    "non_vegetarian": {
        "breakfast": [
            {"item": "2 egg omelette + whole wheat toast + tea/coffee", "calories": 380},
            {"item": "Oats porridge with milk + banana + boiled egg", "calories": 420},
            {"item": "Vegetable upma + curd + fruit", "calories": 350},
        ],
        "lunch": [
            {"item": "Rice + dal + grilled chicken + salad", "calories": 620},
            {"item": "Whole wheat roti + paneer sabzi + curd + salad", "calories": 560},
            {"item": "Brown rice + fish curry + vegetables", "calories": 590},
        ],
        "dinner": [
            {"item": "Grilled chicken + stir-fried vegetables + soup", "calories": 480},
            {"item": "Roti + egg curry + salad", "calories": 460},
            {"item": "Vegetable khichdi + curd", "calories": 440},
        ],
        "snacks": [
            {"item": "Roasted chana + green tea", "calories": 180},
            {"item": "Mixed nuts (small handful) + buttermilk", "calories": 210},
            {"item": "Fresh fruit + yogurt", "calories": 160},
        ],
    },
    "vegetarian": {
        "breakfast": [
            {"item": "Vegetable poha + curd + fruit", "calories": 360},
            {"item": "Dosa with sambar + coconut chutney", "calories": 380},
            {"item": "Oats porridge with milk + banana", "calories": 400},
        ],
        "lunch": [
            {"item": "Rice + dal + sabzi + curd + salad", "calories": 540},
            {"item": "Whole wheat roti + paneer sabzi + salad", "calories": 550},
            {"item": "Roti + soya chunk curry + salad", "calories": 520},
        ],
        "dinner": [
            {"item": "Roti + mixed vegetable curry + dal", "calories": 460},
            {"item": "Vegetable khichdi + curd", "calories": 440},
            {"item": "Paneer tikka + mint chutney + soup", "calories": 470},
        ],
        "snacks": [
            {"item": "Roasted chana + green tea", "calories": 180},
            {"item": "Mixed nuts (small handful)", "calories": 200},
            {"item": "Fresh fruit + buttermilk", "calories": 150},
        ],
    },
    "vegan": {
        "breakfast": [
            {"item": "Oats porridge with soy milk + banana + flax seeds", "calories": 390},
            {"item": "Vegetable poha + peanut chutney", "calories": 350},
            {"item": "Quinoa upma + roasted peanuts", "calories": 370},
        ],
        "lunch": [
            {"item": "Brown rice + dal + vegetables + salad", "calories": 540},
            {"item": "Roti + chana masala + salad", "calories": 560},
            {"item": "Rice + tofu curry + greens", "calories": 550},
        ],
        "dinner": [
            {"item": "Vegetable khichdi + salad", "calories": 440},
            {"item": "Roti + mixed vegetable + dal", "calories": 450},
            {"item": "Lentil soup + grilled tofu + vegetables", "calories": 460},
        ],
        "snacks": [
            {"item": "Roasted chana + green tea", "calories": 180},
            {"item": "Almonds + walnuts (small handful)", "calories": 200},
            {"item": "Fresh fruit", "calories": 120},
        ],
    },
}


def _pick_meals(preference: str, calorie_target: float) -> dict[str, list[dict]]:
    options = MEAL_OPTIONS.get(preference, MEAL_OPTIONS["non_vegetarian"])
    plan = {}
    budget = {
        "breakfast": calorie_target * 0.25,
        "lunch": calorie_target * 0.35,
        "dinner": calorie_target * 0.30,
        "snacks": calorie_target * 0.10,
    }
    for slot, items in options.items():
        selected = []
        for item in items:
            selected.append({"item": item["item"], "calories": item["calories"]})
        plan[slot] = selected
    return plan


def generate_plan(
    gender: str,
    age: int,
    height_cm: float,
    weight_kg: float,
    activity_level: str,
    goal: str = "maintain",
    dietary_preference: str = "non_vegetarian",
) -> dict:
    anthropometrics = compute_anthropometrics(gender, age, height_cm, weight_kg, activity_level)
    if not anthropometrics["valid"]:
        return {"valid": False, "error": "Height and weight are required for a diet plan."}

    targets = daily_targets(anthropometrics["tdee"], goal, weight_kg, dietary_preference)
    meals = _pick_meals(dietary_preference, targets["calorie_target"])

    return {
        "valid": True,
        "bmi": anthropometrics["bmi"],
        "bmr": anthropometrics["bmr"],
        "tdee": anthropometrics["tdee"],
        **targets,
        "meals": meals,
        "goal": goal,
        "dietary_preference": dietary_preference,
    }