"""Rule-based risk assessment engine for chronic conditions.

Used when no trained ML risk model is available (settings.ai_fallback_mode).
Produces audit-friendly, explainable risk scores for diabetes, hypertension,
heart disease and chronic kidney disease. Scores are population-based heuristics,
NOT clinical diagnoses.
"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger("medivision.services.risk_engine")

SUPPORTED_CONDITIONS = {
    "diabetes": "Type 2 Diabetes",
    "hypertension": "Hypertension",
    "heart_disease": "Cardiovascular / Heart Disease",
    "ckd": "Chronic Kidney Disease",
}


def _level(percentage: float) -> str:
    if percentage < 30:
        return "low"
    if percentage < 60:
        return "moderate"
    return "high"


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _clamp01(value: float) -> float:
    return _clamp(value, 0.0, 1.0)


def _summarize(percentage: float, label: str) -> str:
    level = _level(percentage)
    return (
        f"Estimated {percentage:.0f}% likelihood of {label.lower()} based on the profile provided. "
        f"This is a screening heuristic, not a clinical diagnosis."
    )


def _diabetes_calc(data: dict) -> dict:
    age = data.get("age", 0)
    bmi = data.get("bmi")
    glucose = data.get("fasting_blood_sugar")
    hba1c = data.get("hba1c")
    family = bool(data.get("family_history"))
    smoker = bool(data.get("smoker"))
    activity = data.get("physical_activity", "moderate")
    hypertension = bool(data.get("hypertension"))

    factors: list[dict] = []
    assets = 0.0

    if age >= 45:
        a = _clamp01((age - 45) / 25)
        assets += 14 * a
        factors.append({"factor": "Age", "value": age, "weight": round(14 * a, 1), "direction": "increases"})
    if bmi is not None:
        if bmi >= 30:
            w = 18
        elif bmi >= 25:
            w = 10
        else:
            w = 0
        assets += w
        factors.append({"factor": "BMI", "value": bmi, "weight": w, "direction": "increases" if w else "neutral"})
    if glucose is not None:
        if glucose >= 200:
            w = 30
        elif glucose >= 126:
            w = 24
        elif glucose >= 100:
            w = 12
        else:
            w = 0
        assets += w
        factors.append({"factor": "Fasting blood sugar (mg/dL)", "value": glucose, "weight": w, "direction": "increases" if w else "neutral"})
    if hba1c is not None:
        if hba1c >= 6.5:
            w = 30
        elif hba1c >= 5.7:
            w = 15
        else:
            w = 0
        assets += w
        factors.append({"factor": "HbA1c (%)", "value": hba1c, "weight": w, "direction": "increases" if w else "neutral"})
    if family:
        assets += 10
        factors.append({"factor": "Family history of diabetes", "value": "yes", "weight": 10, "direction": "increases"})
    if hypertension:
        assets += 6
        factors.append({"factor": "Known hypertension", "value": "yes", "weight": 6, "direction": "increases"})
    if smoker:
        assets += 5
        factors.append({"factor": "Smoking", "value": "yes", "weight": 5, "direction": "increases"})
    if activity == "sedentary":
        assets += 6
        factors.append({"factor": "Sedentary lifestyle", "value": "yes", "weight": 6, "direction": "increases"})

    risk = round(_clamp(min(assets, 92) * 0.9 + 6), 1)
    recommendations = [
        "Get a fasting glucose and HbA1c test for a definitive screening.",
        "Maintain a BMI under 25 through diet and regular physical activity.",
        "Limit refined sugar and sugary beverages; prefer fibre-rich meals.",
        "Consult a physician to build a personalised prevention plan."
        if risk >= 60
        else "Discuss these risk factors with a clinician to build a personalised prevention plan.",
    ]
    return {
        "risk_percentage": risk,
        "risk_level": _level(risk),
        "factors": factors,
        "explanation": _summarize(risk, SUPPORTED_CONDITIONS["diabetes"]),
        "recommendations": recommendations,
        "model_name": "rule_based_diabetes_v1",
        "is_demo": True,
    }


def _hypertension_calc(data: dict) -> dict:
    age = data.get("age", 0)
    bmi = data.get("bmi")
    systolic = data.get("systolic")
    diastolic = data.get("diastolic")
    family = bool(data.get("family_history"))
    smoker = bool(data.get("smoker"))
    salt = data.get("salt_intake", "moderate")
    activity = data.get("physical_activity", "moderate")
    stress = data.get("stress_level")

    factors: list[dict] = []
    assets = 0.0

    if age >= 55:
        a = _clamp01((age - 55) / 25)
        assets += 16 * a
        factors.append({"factor": "Age", "value": age, "weight": round(16 * a, 1), "direction": "increases"})
    if bmi is not None:
        w = 14 if bmi >= 30 else (8 if bmi >= 25 else 0)
        assets += w
        factors.append({"factor": "BMI", "value": bmi, "weight": w, "direction": "increases" if w else "neutral"})
    if systolic is not None:
        w = 26 if systolic >= 160 else (18 if systolic >= 140 else (9 if systolic >= 120 else 2))
        assets += w
        factors.append({"factor": "Systolic BP (mmHg)", "value": systolic, "weight": w, "direction": "increases"})
    if diastolic is not None:
        w = 18 if diastolic >= 100 else (12 if diastolic >= 90 else (5 if diastolic >= 80 else 1))
        assets += w
        factors.append({"factor": "Diastolic BP (mmHg)", "value": diastolic, "weight": w, "direction": "increases"})
    if family:
        assets += 10
        factors.append({"factor": "Family history of hypertension", "value": "yes", "weight": 10, "direction": "increases"})
    if smoker:
        assets += 6
        factors.append({"factor": "Smoking", "value": "yes", "weight": 6, "direction": "increases"})
    if salt == "high":
        assets += 8
        factors.append({"factor": "High salt intake", "value": "yes", "weight": 8, "direction": "increases"})
    if activity == "sedentary":
        assets += 5
        factors.append({"factor": "Sedentary lifestyle", "value": "yes", "weight": 5, "direction": "increases"})
    if stress and int(stress) >= 6:
        assets += 5
        factors.append({"factor": "High self-reported stress", "value": stress, "weight": 5, "direction": "increases"})

    risk = round(_clamp(min(assets, 90) * 0.9 + 7), 1)
    recommendations = [
        "Measure blood pressure at the same time daily for a week to confirm trends.",
        "Reduce sodium to under 5g salt/day and increase potassium-rich foods.",
        "Commit to at least 30 minutes of moderate activity on most days.",
        "Limit alcohol, manage stress, and get quality sleep.",
    ]
    if risk >= 60:
        recommendations.insert(0, "See a physician promptly; elevated readings with symptoms need evaluation.")
    return {
        "risk_percentage": risk,
        "risk_level": _level(risk),
        "factors": factors,
        "explanation": _summarize(risk, SUPPORTED_CONDITIONS["hypertension"]),
        "recommendations": recommendations,
        "model_name": "rule_based_hypertension_v1",
        "is_demo": True,
    }


def _heart_disease_calc(data: dict) -> dict:
    age = data.get("age", 0)
    sex = data.get("gender", "female").lower()
    smoker = bool(data.get("smoker"))
    diabetes = bool(data.get("diabetes"))
    hypertension = bool(data.get("hypertension"))
    bmi = data.get("bmi")
    ldl = data.get("ldl_cholesterol")
    hdl = data.get("hdl_cholesterol")
    triglycerides = data.get("triglycerides")
    family = bool(data.get("family_history"))
    activity = data.get("physical_activity", "moderate")

    factors: list[dict] = []
    assets = 5.0

    male_extra = 2 if sex == "male" else 0
    assets += male_extra * 3
    if age >= 45:
        a = _clamp01((age - 45) / 25)
        assets += 15 * a
        factors.append({"factor": "Age", "value": age, "weight": round(15 * a, 1), "direction": "increases"})
    if smoker:
        assets += 14
        factors.append({"factor": "Smoking", "value": "yes", "weight": 14, "direction": "increases"})
    if diabetes:
        assets += 14
        factors.append({"factor": "Diabetes", "value": "yes", "weight": 14, "direction": "increases"})
    if hypertension:
        assets += 10
        factors.append({"factor": "Hypertension", "value": "yes", "weight": 10, "direction": "increases"})
    if bmi is not None:
        w = 10 if bmi >= 30 else (6 if bmi >= 25 else 0)
        assets += w
        factors.append({"factor": "BMI", "value": bmi, "weight": w, "direction": "increases" if w else "neutral"})
    if ldl is not None:
        w = 10 if ldl >= 160 else (6 if ldl >= 130 else 0)
        assets += w
        factors.append({"factor": "LDL cholesterol (mg/dL)", "value": ldl, "weight": w, "direction": "increases" if w else "neutral"})
    if hdl is not None:
        if hdl < 40:
            w = 8
        elif hdl < 50:
            w = 3
        else:
            w = 0
        assets += w
        factors.append({"factor": "HDL cholesterol (mg/dL)", "value": hdl, "weight": w, "direction": "increases" if w else "neutral"})
    if triglycerides is not None and triglycerides >= 150:
        assets += 6
        factors.append({"factor": "Triglycerides (mg/dL)", "value": triglycerides, "weight": 6, "direction": "increases"})
    if family:
        assets += 10
        factors.append({"factor": "Early heart disease in family", "value": "yes", "weight": 10, "direction": "increases"})
    if activity == "sedentary":
        assets += 6
        factors.append({"factor": "Sedentary lifestyle", "value": "yes", "weight": 6, "direction": "increases"})

    risk = round(_clamp(min(assets, 88) * 0.95 + 5), 1)
    recommendations = [
        "Get a fasting lipid profile and blood pressure check.",
        "Aim for a heart-healthy diet: more vegetables, whole grains, lean protein, less trans fat.",
        "Quit smoking and avoid second-hand smoke.",
        "Maintain regular moderate exercise unless advised otherwise.",
    ]
    if risk >= 60:
        recommendations.insert(0, "Chest pain, breathlessness or unusual fatigue should prompt urgent medical review.")
    return {
        "risk_percentage": risk,
        "risk_level": _level(risk),
        "factors": factors,
        "explanation": _summarize(risk, SUPPORTED_CONDITIONS["heart_disease"]),
        "recommendations": recommendations,
        "model_name": "rule_based_heart_v1",
        "is_demo": True,
    }


def _ckd_calc(data: dict) -> dict:
    age = data.get("age", 0)
    diabetes = bool(data.get("diabetes"))
    hypertension = bool(data.get("hypertension"))
    bmi = data.get("bmi")
    egfr = data.get("egfr")
    acr = data.get("albumin_creatinine_ratio")
    smoker = bool(data.get("smoker"))

    factors: list[dict] = []
    assets = 4.0

    if age >= 50:
        a = _clamp01((age - 50) / 30)
        assets += 12 * a
        factors.append({"factor": "Age", "value": age, "weight": round(12 * a, 1), "direction": "increases"})
    if diabetes:
        assets += 22
        factors.append({"factor": "Diabetes", "value": "yes", "weight": 22, "direction": "increases"})
    if hypertension:
        assets += 18
        factors.append({"factor": "Hypertension", "value": "yes", "weight": 18, "direction": "increases"})
    if bmi is not None and bmi >= 30:
        assets += 6
        factors.append({"factor": "BMI", "value": bmi, "weight": 6, "direction": "increases"})
    if egfr is not None:
        if egfr is not None and egfr < 60:
            w = 30
        elif egfr < 90:
            w = 12
        else:
            w = 0
        assets += w
        factors.append({"factor": "eGFR (mL/min/1.73m2)", "value": egfr, "weight": w, "direction": "increases" if w else "neutral"})
    if acr is not None:
        if acr >= 300:
            w = 24
        elif acr >= 30:
            w = 12
        else:
            w = 0
        assets += w
        factors.append({"factor": "Albumin-creatinine ratio (mg/g)", "value": acr, "weight": w, "direction": "increases" if w else "neutral"})
    if smoker:
        assets += 8
        factors.append({"factor": "Smoking", "value": "yes", "weight": 8, "direction": "increases"})

    risk = round(_clamp(min(assets, 88) * 0.95 + 6), 1)
    recommendations = [
        "Check kidney function with serum creatinine (eGFR) and urine albumin tests.",
        "Tight control of blood sugar and blood pressure protects kidney health.",
        "Stay well hydrated and avoid unneeded NSAID painkillers.",
        "Reduce salt and processed foods.",
    ]
    if risk >= 60:
        recommendations.insert(0, "A nephrology review is recommended given the profile.")
    return {
        "risk_percentage": risk,
        "risk_level": _level(risk),
        "factors": factors,
        "explanation": _summarize(risk, SUPPORTED_CONDITIONS["ckd"]),
        "recommendations": recommendations,
        "model_name": "rule_based_ckd_v1",
        "is_demo": True,
    }


CALCULATORS = {
    "diabetes": _diabetes_calc,
    "hypertension": _hypertension_calc,
    "heart_disease": _heart_disease_calc,
    "ckd": _ckd_calc,
}


def supported_conditions() -> dict:
    return {
        code: {
            "label": label,
            "inputs": _condition_inputs(code),
        }
        for code, label in SUPPORTED_CONDITIONS.items()
    }


def _condition_inputs(code: str) -> list[str]:
    common = ["age", "gender", "bmi", "smoker", "family_history", "physical_activity"]
    specific = {
        "diabetes": ["fasting_blood_sugar", "hba1c", "hypertension"],
        "hypertension": ["systolic", "diastolic", "salt_intake", "stress_level"],
        "heart_disease": ["diabetes", "hypertension", "ldl_cholesterol", "hdl_cholesterol", "triglycerides"],
        "ckd": ["diabetes", "hypertension", "egfr", "albumin_creatinine_ratio"],
    }
    return common + specific.get(code, [])


def analyze_risk(condition_type: str, data: dict) -> dict:
    """Run the rule-based risk analysis for the given condition type."""
    code = condition_type.strip().lower()
    if code not in CALCULATORS:
        from app.core.exceptions import ValidationException
        raise ValidationException(
            f"Unsupported condition type '{condition_type}'",
            details={"supported": list(SUPPORTED_CONDITIONS)},
        )
    result = CALCULATORS[code](data or {})
    result["condition_type"] = code
    result["condition_label"] = SUPPORTED_CONDITIONS[code]
    result["is_demo"] = True
    result["engine_mode"] = "rule_based" if settings.ai_fallback_mode else "model"
    return result