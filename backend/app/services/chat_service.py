"""AI chatbot service with a rule-based fallback and optional LLM integration.

The chat assistant is a health-education copilot, NOT a diagnosis tool. When an
OpenAI-compatible LLM is configured it is used with strict safety instructions;
otherwise a curated rule engine answers common questions and redirects to the
right module.
"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger("medivision.services.chat")

DISCLAIMER = (
    "MediVision AI assistant provides general health information only and is not a "
    "diagnosis or substitute for professional medical care. In an emergency, "
    "call your local emergency number immediately."
)

EMERGENCY_KEYWORDS = [
    "emergency", "chest pain", "can't breathe", "cant breathe", "difficulty breathing",
    "shortness of breath", "heart attack", "stroke", "unconscious", "seizure",
    "self harm", "suicide", "suicidal", "bleeding heavily", "severe allergic",
    "swelling of face", "swelling of tongue", "worst headache",
]

INTENT_KEYWORDS = {
    "symptom": ["symptom", "checker", "what is wrong", "not feeling well", "sick", "fever", "cough"],
    "appointment": ["appointment", "book", "doctor visit", "consult", "schedule"],
    "medication": ["medication", "medicine", "dosage", "refill", "adherence", "pill", "tablet"],
    "diet": ["diet", "food", "eat", "nutrition", "calorie", "meal", "vegan", "vegetarian"],
    "exercise": ["exercise", "workout", "fitness", "gym", "training", "activity"],
    "risk": ["risk", "diabetes", "hypertension", "blood pressure", "heart disease", "kidney", "predict"],
    "vision": ["x-ray", "xray", "mri", "scan", "image", "radiology", "skin lesion", "upload photo", "analyze photo"],
    "wellness": ["stress", "mood", "sleep", "anxiety", "meditation", "mental", "breathing"],
    "healthcare": ["hospital", "clinic", "pharmacy", "lab", "nearby", "emergency numbers", "hotline", "ambulance"],
    "timeline": ["timeline", "history", "records", "report"],
    "hello": ["hello", "hi", "hey", "namaste", "good morning"],
}

REPLIES = {
    "symptom": (
        "Use the Symptom Checker to log your symptoms and get a triage-style list of "
        "likely conditions with severity flags. It is a screening aid, not a diagnosis. "
        "Head to 'Symptom Checker' in your dashboard."
    ),
    "appointment": (
        "You can book and manage appointments from the 'Appointments' section - pick a "
        "doctor, choose a free slot, and confirm. For follow-ups you can reschedule from "
        "the same place."
    ),
    "medication": (
        "Your medications are managed under 'Medications': log intakes daily, enable "
        "reminders, and track your adherence percentage there."
    ),
    "diet": (
        "The Diet Planner builds a personalised daily meal plan from your profile - "
        "calorie target, proteins and meal options tailored to your goal and preference. "
        "Check 'Diet Plan' in the dashboard."
    ),
    "exercise": (
        "The Exercise Planner generates a weekly, day-wise routine matched to your "
        "fitness level and goal, with safety filtering for common restrictions."
    ),
    "risk": (
        "You can run a risk assessment for diabetes, hypertension, heart disease and "
        "kidney disease under 'Risk Prediction'. Results include contributing factors "
        "and lifestyle recommendations."
    ),
    "vision": (
        "You can analyse medical images (MRI, chest X-ray, skin, eye, blood smear) under "
        "'Vision Analysis'. Upload an image to get a model prediction with confidence. "
        "Results are assistive only."
    ),
    "wellness": (
        "Your Wellness section helps track mood, stress and meditation. Small consistent "
        "check-ins build self-awareness. Reach out to a professional for persistent concerns."
    ),
    "healthcare": (
        "Use 'Nearby Services' to find hospitals, clinics, pharmacies and labs near you, "
        "including live bed capacity for emergency hospitals."
    ),
    "timeline": (
        "Your Health Timeline groups reports, consultations, prescriptions and AI activity "
        "by date - a single place to review everything."
    ),
    "hello": (
        "Hello! I'm the MediVision AI assistant. I can guide you through symptom checking, "
        "appointments, medications, diet, exercise, risk prediction, imaging analysis, and "
        "finding nearby care. What would you like help with?"
    ),
    "default": (
        "I can help with symptoms, appointments, medications, diet, exercise, risk "
        "prediction, imaging analysis, wellness and finding nearby care. Could you "
        "rephrase your question, or pick one of the quick topics below?"
    ),
}

QUICK_REPLIES = [
    "How do I use the symptom checker?",
    "Book a doctor's appointment",
    "My medications and adherence",
    "Get a diet plan for today",
    "Weekly exercise plan for me",
    "Predict my risk of diabetes",
    "Analyze a chest X-ray",
    "Find a nearby hospital",
    "Help with stress and sleep",
]


def _detect_intent(message: str) -> str:
    lowered = message.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return intent
    return "default"


def _is_emergency(message: str) -> bool:
    lowered = message.lower()
    return any(keyword in lowered for keyword in EMERGENCY_KEYWORDS)


def rule_respond(message: str, context: dict | None = None) -> dict:
    if _is_emergency(message):
        reply = (
            "This sounds like it could be an emergency. Please call your local emergency "
            "number or go to the nearest emergency department immediately. Do not wait. "
            "If someone is unconscious, not breathing, or having severe chest pain, "
            "call for emergency services right away."
        )
        source = "rules"
        return {
            "reply": reply,
            "source": source,
            "model": "rule_engine_v1",
            "is_emergency": True,
            "quick_replies": QUICK_REPLIES,
            "disclaimer": DISCLAIMER,
        }
    intent = _detect_intent(message)
    return {
        "reply": REPLIES.get(intent, REPLIES["default"]),
        "source": "rules",
        "model": "rule_engine_v1",
        "intent": intent,
        "is_emergency": False,
        "quick_replies": QUICK_REPLIES,
        "disclaimer": DISCLAIMER,
    }


def llm_respond(message: str, context: dict | None = None) -> dict:
    try:
        from openai import OpenAI
    except Exception as exc:
        logger.warning("OpenAI client unavailable: %s", exc)
        return rule_respond(message, context)

    if not settings.llm_api_key:
        return rule_respond(message, context)

    try:
        client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url or None,
            timeout=settings.llm_timeout_seconds,
        )
        system_prompt = (
            "You are MediVision's health-education assistant. Answer only with general "
            "health education. Never diagnose, never prescribe. If the user describes "
            "an emergency, tell them to call the emergency number immediately. Keep "
            "answers concise (under 120 words), empathetic and in plain language."
        )
        user_payload = message
        if context:
            user_payload += "\n\nContext: " + (str(context)[:2000])
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_payload},
            ],
            max_tokens=400,
        )
        reply = response.choices[0].message.content.strip()
        if not reply:
            return rule_respond(message, context)
        return {
            "reply": reply,
            "source": "llm",
            "model": settings.llm_model,
            "is_emergency": _is_emergency(message),
            "quick_replies": QUICK_REPLIES,
            "disclaimer": DISCLAIMER,
        }
    except Exception as exc:
        logger.warning("LLM chat failed, falling back to rules: %s", exc)
        return rule_respond(message, context)


def respond(message: str, context: dict | None = None) -> dict:
    text = (message or "").strip()
    if not text:
        from app.core.exceptions import ValidationException
        raise ValidationException("Message cannot be empty")
    if settings.llm_api_key and settings.llm_provider == "openai":
        return llm_respond(message, context)
    return rule_respond(message, context)