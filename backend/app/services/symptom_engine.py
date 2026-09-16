"""Rule-based symptom checker engine.

This module is the deterministic, auditable fallback used when no trained ML
symptom model is available. It is a curated knowledge base, NOT a diagnosis:
outputs are candidate conditions with confidence scores and emergency flags and
must always be presented alongside a medical disclaimer to the user.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("medivision.services.symptom_engine")


class Condition(dict):
    """Convenience wrapper around a condition knowledge-base entry."""

    @property
    def name(self) -> str:
        return self.get("name", "")


CONDITION_DB: list[dict] = [
    {
        "name": "Common Cold",
        "symptoms": ["runny nose", "sneezing", "sore throat", "cough", "nasal congestion", "mild fever"],
        "base": 0.72,
        "severity": "low",
        "specialty": "General Medicine",
        "red_flags": [],
        "advice": "Rest, keep hydrated and use over-the-counter decongestants if needed. "
                  "Most colds resolve within 7-10 days.",
    },
    {
        "name": "Influenza",
        "symptoms": ["high fever", "body ache", "muscle pain", "fatigue", "headache", "dry cough", "chills"],
        "base": 0.74,
        "severity": "moderate",
        "specialty": "General Medicine",
        "red_flags": ["difficulty breathing", "chest pain", "confusion", "seizure"],
        "advice": "Rest, fluids and fever medication help. Seek urgent care if breathing becomes difficult.",
    },
    {
        "name": "COVID-like Illness",
        "symptoms": ["fever", "dry cough", "loss of taste", "loss of smell", "fatigue", "sore throat", "shortness of breath"],
        "base": 0.68,
        "severity": "moderate",
        "specialty": "General Medicine / Pulmonology",
        "red_flags": ["difficulty breathing", "bluish lips", "chest pain", "low oxygen"],
        "advice": "Consider a COVID-19 test, isolate from others and monitor oxygen saturation. "
                  "Seek urgent care on any breathing difficulty.",
    },
    {
        "name": "Migraine",
        "symptoms": ["throbbing headache", "one sided headache", "nausea", "sensitivity to light", "sensitivity to sound", "blurred vision"],
        "base": 0.76,
        "severity": "moderate",
        "specialty": "Neurology",
        "red_flags": ["worst headache of life", "sudden vision loss", "facial drooping", "weakness on one side"],
        "advice": "Rest in a quiet, dark room and keep a headache diary. A sudden 'worst ever' headache "
                  "needs urgent evaluation.",
    },
    {
        "name": "Tension Headache",
        "symptoms": ["headache", "tightness around head", "neck pain", "stress", "pressure sensation"],
        "base": 0.62,
        "severity": "low",
        "specialty": "Neurology / General Medicine",
        "red_flags": [],
        "advice": "Often linked to stress and poor posture. Gentle stretching, hydration and breaks help.",
    },
    {
        "name": "Acute Gastroenteritis",
        "symptoms": ["diarrhea", "abdominal cramps", "vomiting", "nausea", "watery stool", "dehydration"],
        "base": 0.78,
        "severity": "moderate",
        "specialty": "Gastroenterology",
        "red_flags": ["blood in stool", "severe dehydration", "fainting", "high fever"],
        "advice": "Oral rehydration solution in frequent sips, bland diet and rest. Seek care for blood in stool.",
    },
    {
        "name": "Food Poisoning",
        "symptoms": ["nausea", "vomiting", "diarrhea", "abdominal pain", "fever", "recent suspicious food"],
        "base": 0.7,
        "severity": "moderate",
        "specialty": "Gastroenterology",
        "red_flags": ["bloody diarrhea", "trouble keeping fluids", "fainting"],
        "advice": "Hydrate well with ORS. Avoid dairy and heavy meals until symptoms settle.",
    },
    {
        "name": "Urinary Tract Infection",
        "symptoms": ["burning during urination", "frequent urination", "pelvic pain", "cloudy urine", "blood in urine", "lower abdomen discomfort"],
        "base": 0.8,
        "severity": "moderate",
        "specialty": "Urology / General Medicine",
        "red_flags": ["high fever with chills", "flank pain", "vomiting"],
        "advice": "Drink plenty of water and see a doctor; untreated UTIs can spread to the kidneys.",
    },
    {
        "name": "Kidney Stone",
        "symptoms": ["severe flank pain", "pain in lower back", "painful urination", "blood in urine", "nausea", "restlessness from pain"],
        "base": 0.82,
        "severity": "high",
        "specialty": "Urology",
        "red_flags": ["unbearable pain", "fever", "inability to urinate"],
        "advice": "Severe pain with fever needs urgent evaluation. Hydration helps prevent recurrence.",
    },
    {
        "name": "Appendicitis",
        "symptoms": ["localized right lower abdomen pain", "pain migrating to lower right", "loss of appetite", "nausea", "vomiting", "fever"],
        "base": 0.8,
        "severity": "emergency",
        "specialty": "General Surgery",
        "red_flags": ["right lower abdomen pain", "increasing pain", "fever"],
        "advice": "Sudden right-lower abdominal pain with fever requires IMMEDIATE medical attention.",
    },
    {
        "name": "Gastroesophageal Reflux Disease",
        "symptoms": ["heartburn", "acid reflux", "regurgitation", "chest burning after meals", "sour taste in mouth"],
        "base": 0.78,
        "severity": "low",
        "specialty": "Gastroenterology",
        "red_flags": ["chest pain radiating to arm", "difficulty swallowing"],
        "advice": "Smaller meals, avoid lying down right after eating. See a doctor if persistent.",
    },
    {
        "name": "Asthma Exacerbation",
        "symptoms": ["wheezing", "shortness of breath", "chest tightness", "coughing at night", "difficulty breathing"],
        "base": 0.8,
        "severity": "high",
        "specialty": "Pulmonology",
        "red_flags": ["difficulty breathing", "bluish lips", "gasping for air", "chest retractions"],
        "advice": "Use your reliever inhaler promptly. Severe breathing difficulty is an emergency.",
    },
    {
        "name": "Pneumonia",
        "symptoms": ["high fever", "productive cough", "chest pain on breathing", "shortness of breath", "fatigue", "chills"],
        "base": 0.76,
        "severity": "high",
        "specialty": "Pulmonology",
        "red_flags": ["difficulty breathing", "bluish lips", "confusion", "low oxygen"],
        "advice": "Fever with productive cough and breathing difficulty warrants early medical review.",
    },
    {
        "name": "Allergic Reaction",
        "symptoms": ["rash", "itching", "hives", "sneezing", "watery eyes", "swelling"],
        "base": 0.7,
        "severity": "moderate",
        "specialty": "Dermatology / Allergy",
        "red_flags": ["swelling of lips or tongue", "difficulty breathing", "wheezing", "dizziness"],
        "advice": "Antihistamines help mild reactions. Swelling of the face or throat is an emergency.",
    },
    {
        "name": "Dengue",
        "symptoms": ["sudden high fever", "severe headache", "pain behind eyes", "joint pain", "rash", "nausea", "bleeding gums"],
        "base": 0.78,
        "severity": "high",
        "specialty": "Infectious Disease / General Medicine",
        "red_flags": ["bleeding gums", "blood in vomit", "severe abdominal pain", "cold clammy skin"],
        "advice": "Monitor platelet counts and hydration. Bleeding or severe pain requires hospital care.",
    },
    {
        "name": "Malaria",
        "symptoms": ["high fever with chills", "sweating", "headache", "body ache", "cycles of fever"],
        "base": 0.72,
        "severity": "high",
        "specialty": "Infectious Disease / General Medicine",
        "red_flags": ["confusion", "seizure", "dark urine", "drowsiness"],
        "advice": "Fever with chills in a malaria-prone area warrants a blood test promptly.",
    },
    {
        "name": "Anemia",
        "symptoms": ["fatigue", "pale skin", "dizziness", "shortness of breath on exertion", "cold hands", "rapid heartbeat"],
        "base": 0.66,
        "severity": "moderate",
        "specialty": "General Medicine / Hematology",
        "red_flags": ["chest pain", "fainting"],
        "advice": "A simple blood count can confirm. Iron-rich diet helps but confirm with your doctor first.",
    },
    {
        "name": "Hypertension",
        "symptoms": ["headache", "dizziness", "blurred vision", "chest palpitations", "high blood pressure reading"],
        "base": 0.6,
        "severity": "moderate",
        "specialty": "Cardiology / General Medicine",
        "red_flags": ["severe headache", "chest pain", "sudden vision loss", "numbness"],
        "advice": "Repeatedly high readings need formal evaluation. Very high readings with symptoms are urgent.",
    },
    {
        "name": "Type 2 Diabetes",
        "symptoms": ["excessive thirst", "frequent urination", "unexplained weight loss", "fatigue", "blurred vision", "slow healing wounds"],
        "base": 0.68,
        "severity": "moderate",
        "specialty": "Endocrinology / General Medicine",
        "red_flags": ["confusion", "fruity breath", "rapid breathing"],
        "advice": "A fasting glucose / HbA1c test gives a clear picture. Unmanaged high sugar can be urgent.",
    },
    {
        "name": "Sinusitis",
        "symptoms": ["facial pain", "sinus pressure", "nasal congestion", "yellow nasal discharge", "headache", "reduced smell"],
        "base": 0.72,
        "severity": "low",
        "specialty": "ENT",
        "red_flags": ["swelling around eye", "high fever", "double vision"],
        "advice": "Steam inhalation, fluids and rest. Persistent symptoms beyond 10 days need review.",
    },
    {
        "name": "Conjunctivitis",
        "symptoms": ["red eyes", "itchy eyes", "watery eyes", "eye discharge", "sticky eyelids", "gritty eyes"],
        "base": 0.76,
        "severity": "low",
        "specialty": "Ophthalmology",
        "red_flags": ["eye pain", "sudden vision loss", "sensitivity to light"],
        "advice": "Highly contagious - wash hands frequently and avoid touching eyes. Consult if painful.",
    },
    {
        "name": "Otitis Media",
        "symptoms": ["ear pain", "hearing dullness", "fever", "ear discharge", "fussiness"],
        "base": 0.68,
        "severity": "moderate",
        "specialty": "ENT",
        "red_flags": ["swelling behind ear", "severe pain", "dizziness"],
        "advice": "Ear infections can need antibiotics; see a doctor rather than using home drops blindly.",
    },
    {
        "name": "Hypothyroidism",
        "symptoms": ["weight gain", "fatigue", "cold intolerance", "dry skin", "hair loss", "constipation", "depression"],
        "base": 0.6,
        "severity": "moderate",
        "specialty": "Endocrinology",
        "red_flags": [],
        "advice": "A TSH blood test is the standard first step. Symptoms can overlap with other conditions.",
    },
    {
        "name": "Vertigo / Inner Ear Disorder",
        "symptoms": ["spinning sensation", "dizziness", "imbalance", "nausea", "ringing in ears"],
        "base": 0.7,
        "severity": "moderate",
        "specialty": "ENT / Neurology",
        "red_flags": ["facial drooping", "slurred speech", "weakness", "severe headache"],
        "advice": "Sudden vertigo with neurological symptoms needs urgent evaluation for stroke.",
    },
    {
        "name": "Mental Health Stress Reaction",
        "symptoms": ["anxiety", "difficulty sleeping", "irritability", "low mood", "loss of interest", "racing thoughts", "panic"],
        "base": 0.55,
        "severity": "low",
        "specialty": "Psychiatry / Counselling",
        "red_flags": ["self harm thoughts", "thoughts of hurting others", "severe panic with chest pain"],
        "advice": "Your wellbeing matters. If you have thoughts of harming yourself, seek help immediately "
                  "through an emergency line or local crisis service.",
    },
]

SYMPTOM_TO_CONDITIONS: dict[str, list[str]] = {}
for _cond in CONDITION_DB:
    for _symptom in _cond["symptoms"]:
        SYMPTOM_TO_CONDITIONS.setdefault(_symptom.lower(), []).append(_cond["name"])


def normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())


def build_catalog() -> list[str]:
    catalog = sorted({normalize(s) for c in CONDITION_DB for s in c["symptoms"]})
    return catalog


def _condition_by_name(name: str) -> dict:
    for cond in CONDITION_DB:
        if cond["name"] == name:
            return cond
    return {}


def analyze_symptoms(
    symptoms: list[str],
    duration_days: int | None = None,
    symptoms_text: str | None = None,
) -> dict:
    """Return candidate conditions ranked by confidence for the given symptoms."""
    normalized = [normalize(s) for s in symptoms if s and s.strip()]
    normalized = [s for s in normalized if s in SYMPTOM_TO_CONDITIONS]

    matched_conditions: dict[str, dict] = {}
    for symptom in normalized:
        for name in SYMPTOM_TO_CONDITIONS[symptom]:
            match = matched_conditions.setdefault(name, {"matched": set()})
            match["matched"].add(symptom)

    results = []
    for name, state in matched_conditions.items():
        cond = _condition_by_name(name)
        matched = state["matched"]
        if not cond:
            continue
        keyword_count = len(cond["symptoms"])
        coverage = min(1.0, len(matched) / max(1, min(3, keyword_count)))
        confidence = round(min(0.97, cond["base"] * (0.55 + 0.45 * coverage)), 2)

        red_flags_hit = set(normalize(r) for r in cond["red_flags"]) & normalized
        is_emergency = bool(red_flags_hit) or cond["severity"] == "emergency"
        severity = "emergency" if is_emergency else cond["severity"]

        advice = cond["advice"]
        if red_flags_hit:
            advice = "RED FLAG PRESENT: " + " | ".join(sorted(red_flags_hit)) + ". " + advice

        if duration_days is not None and duration_days >= 14 and cond["severity"] in ("low", "moderate"):
            advice += " Symptoms lasting two weeks or longer should be reviewed by a doctor."

        results.append(
            {
                "condition_name": name,
                "confidence": confidence,
                "severity": severity,
                "recommended_specialty": cond["specialty"],
                "emergency_flag": is_emergency,
                "advice": advice,
                "model": "rule_based",
                "matched_symptoms": sorted(matched),
            }
        )

    results.sort(key=lambda r: (r["emergency_flag"], r["confidence"]), reverse=True)
    top_results = results[:5]
    any_emergency = any(r["emergency_flag"] for r in top_results)
    suggested_specialty = top_results[0]["recommended_specialty"] if top_results else "General Medicine"

    duration_note = None
    if duration_days is not None:
        if duration_days <= 2:
            duration_note = "Acute onset"
        elif duration_days <= 14:
            duration_note = "Sub-acute duration"
        else:
            duration_note = "Chronic duration - a comprehensive review is advised"

    return {
        "results": top_results,
        "emergency_flag": any_emergency,
        "suggested_specialty": suggested_specialty,
        "normalized_symptoms": normalized,
        "duration_note": duration_note,
        "recognized_count": len(normalized),
        "unrecognized_count": len([normalize(s) for s in symptoms if s and s.strip()]) - len(normalized),
        "mode": "rule_based",
    }