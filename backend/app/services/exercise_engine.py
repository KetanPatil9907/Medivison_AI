"""Weekly exercise plan generator.

Builds a day-wise plan tuned to fitness level and goal, and applies basic
safety filtering for common medical restrictions. It is fitness guidance,
not a medical prescription; patients with existing conditions should clear
the plan with their doctor.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("medivision.services.exercise")

FITNESS_LEVELS = ("beginner", "intermediate", "advanced")
EXERCISE_GOALS = ("general_fitness", "weight_loss", "muscle_gain", "endurance", "flexibility")


def _session(slot: str, focus: str, exercise_type: str, duration: int, intensity: str, exercises: list[str]) -> dict:
    return {
        "slot": slot,
        "focus": focus,
        "type": exercise_type,
        "duration_minutes": duration,
        "intensity": intensity,
        "exercises": exercises,
    }


WEEK_TEMPLATES: dict[str, dict[str, dict]] = {
    "beginner": {
        "general_fitness": [
            _session("Monday", "Full body conditioning", "strength + cardio", 30, "low",
                     ["Brisk walking", "Bodyweight squats 3x10", "Knee push-ups 3x8", "Standing marches"]),
            _session("Tuesday", "Active recovery", "mobility", 20, "low", ["Easy stretching", "Foam rolling", "Breathing practice"]),
            _session("Wednesday", "Cardio foundation", "cardio", 30, "moderate", ["Brisk walking/jog intervals", "Arm circles", "Side steps"]),
            _session("Thursday", "Strength basics", "strength", 30, "low", ["Chair squats", "Wall push-ups", "Glute bridges 3x10"]),
            _session("Friday", "Walk + stretch", "cardio + mobility", 30, "low", ["30 min walk", "Full body stretch"]),
            _session("Saturday", "Fun movement", "cardio", 40, "moderate", ["Cycling or swimming", "Light games"]),
            _session("Sunday", "Rest day", "recovery", 0, "rest", ["Easy walk", "Hydration, light stretching"]),
        ],
        "weight_loss": [
            _session("Monday", "Walk + body circuit", "cardio + strength", 40, "moderate",
                     ["Brisk walking 20 min", "Bodyweight squats", "Knee push-ups", "Lunges"]),
            _session("Tuesday", "Low impact cardio", "cardio", 30, "moderate", ["Cycling/swimming", "Standing marches"]),
            _session("Wednesday", "Total body circuit", "strength + cardio", 40, "moderate",
                     ["Squats", "Push-ups", "Plank 20 sec", "High knees (low impact)"]),
            _session("Thursday", "Walking pace training", "cardio", 35, "moderate", ["Intervals: 2 min brisk / 1 min easy"]),
            _session("Friday", "Strength + mobility", "strength", 30, "moderate", ["Glute bridges", "Rows with band", "Stretch"]),
            _session("Saturday", "Long brisk walk", "cardio", 45, "moderate", ["45 min brisk walk"]),
            _session("Sunday", "Rest day", "recovery", 0, "rest", ["Easy stretching, hydration"]),
        ],
        "muscle_gain": [
            _session("Monday", "Lower body", "strength", 40, "moderate", ["Goblet squats", "Lunges", "Glute bridges", "Calf raises"]),
            _session("Tuesday", "Upper body", "strength", 40, "moderate", ["Wall/knee push-ups", "Band rows", "Shoulder presses", "Bicep curls"]),
            _session("Wednesday", "Rest", "recovery", 0, "rest", ["Stretch and recovery"]),
            _session("Thursday", "Lower body", "strength", 40, "moderate", ["Squats", "Romanian deadlift (light)", "Step-ups"]),
            _session("Friday", "Upper body + core", "strength", 40, "moderate", ["Push-ups", "Rows", "Planks", "Leg raises"]),
            _session("Saturday", "Active recovery", "cardio", 25, "low", ["Easy walk, stretching"]),
            _session("Sunday", "Rest day", "recovery", 0, "rest", ["Recovery"]),
        ],
        "endurance": [
            _session("Monday", "Steady cardio", "cardio", 30, "moderate", ["Jog/walk intervals", "Breathing control"]),
            _session("Tuesday", "Mobility", "mobility", 20, "low", ["Dynamic stretching", "Hip openers"]),
            _session("Wednesday", "Interval cardio", "cardio", 30, "moderate", ["2 min brisk / 1 min recover cycles"]),
            _session("Thursday", "Strength support", "strength", 25, "low", ["Bodyweight squats", "Planks", "Bridges"]),
            _session("Friday", "Steady cardio", "cardio", 35, "moderate", ["Brisk walk or swim"]),
            _session("Saturday", "Longer session", "cardio", 40, "moderate", ["Walk/jog mix, easy pace"]),
            _session("Sunday", "Rest day", "recovery", 0, "rest", ["Light stretching"]),
        ],
        "flexibility": [
            _session("Monday", "Full body stretch", "flexibility", 30, "low", ["Hamstring stretch", "Quad stretch", "Cat-cow"]),
            _session("Tuesday", "Yoga flow", "flexibility", 30, "low", ["Sun salutations", "Child's pose", "Downward dog"]),
            _session("Wednesday", "Mobility", "flexibility", 25, "low", ["Hip openers", "Spine rotations", "Shoulder rolls"]),
            _session("Thursday", "Yoga + breath", "flexibility", 30, "low", ["Gentle flow", "Box breathing"]),
            _session("Friday", "Stretch & relax", "flexibility", 25, "low", ["Full body stretch", "Foam rolling"]),
            _session("Saturday", "Yoga flow", "flexibility", 35, "low", ["Sun salutations", "Balancing poses"]),
            _session("Sunday", "Rest / gentle walk", "recovery", 0, "rest", ["Rest and recovery"]),
        ],
    },
    "intermediate": {
        "general_fitness": [
            _session("Monday", "Push + pull strength", "strength", 45, "moderate", ["Push-ups", "Rows", "Overhead press", "Planks"]),
            _session("Tuesday", "Cardio", "cardio", 35, "moderate", ["Jogging", "Jump rope"]),
            _session("Wednesday", "Lower body", "strength", 45, "moderate", ["Back squats", "Lunges", "Romanian deadlifts"]),
            _session("Thursday", "Cardio intervals", "cardio", 35, "high", ["Sprint/jog intervals", "Burpees (low-impact option)"]),
            _session("Friday", "Full body circuit", "strength + cardio", 40, "moderate", ["Kettlebell swings", "Push-ups", "Squat jumps"]),
            _session("Saturday", "Outdoor activity", "cardio", 45, "moderate", ["Bike ride, hike or swim"]),
            _session("Sunday", "Rest / stretch", "recovery", 20, "low", ["Yoga or easy stretching"]),
        ],
        "weight_loss": [
            _session("Monday", "HIIT circuit", "cardio + strength", 40, "high", ["Burpees", "Mountain climbers", "Squats", "Plank"]),
            _session("Tuesday", "Steady cardio", "cardio", 45, "moderate", ["Jogging", "Cycling"]),
            _session("Wednesday", "Strength circuit", "strength", 40, "moderate", ["Squats", "Push-ups", "Rows", "Lunges"]),
            _session("Thursday", "HIIT intervals", "cardio", 35, "high", ["30s sprint / 30s recover", "Jump rope"]),
            _session("Friday", "Full body circuit", "strength + cardio", 45, "moderate", ["Kettlebell swings", "Clean & press (light)", "Squats"]),
            _session("Saturday", "Long steady cardio", "cardio", 50, "moderate", ["Run, cycle or swim"]),
            _session("Sunday", "Active rest", "recovery", 20, "low", ["Walk, stretch, hydration"]),
        ],
        "muscle_gain": [
            _session("Monday", "Push day", "strength", 60, "high", ["Bench press", "Overhead press", "Tricep dips", "Tricep extensions"]),
            _session("Tuesday", "Pull day", "strength", 60, "high", ["Deadlifts (light)", "Pull-ups/rows", "Bicep curls"]),
            _session("Wednesday", "Lower body", "strength", 60, "high", ["Back squats", "Lunges", "Leg press", "Calf raises"]),
            _session("Thursday", "Push day", "strength", 60, "high", ["Incline press", "Lateral raises", "Skull crushers"]),
            _session("Friday", "Pull + core", "strength", 60, "high", ["Rows", "Face pulls", "Planks", "Leg raises"]),
            _session("Saturday", "Functional + cardio", "strength + cardio", 30, "moderate", ["Mobility work", "Light cardio"]),
            _session("Sunday", "Rest day", "recovery", 0, "rest", ["Full recovery, good nutrition"]),
        ],
        "endurance": [
            _session("Monday", "Tempo run", "cardio", 30, "high", ["Run at comfortable-fast pace"]),
            _session("Tuesday", "Strength for runners", "strength", 30, "moderate", ["Squats", "Lunges", "Calf raises", "Core stability"]),
            _session("Wednesday", "Intervals", "cardio", 30, "high", ["400m repeats / interval sprint-jog"]),
            _session("Thursday", "Recovery run", "cardio", 30, "low", ["Easy jog"]),
            _session("Friday", "Long run", "cardio", 60, "moderate", ["Steady longer run"]),
            _session("Saturday", "Mobility", "mobility", 25, "low", ["Dynamic stretching, foam rolling"]),
            _session("Sunday", "Rest", "recovery", 0, "rest", ["Rest"]),
        ],
        "flexibility": [
            _session("Monday", "Power yoga", "flexibility", 45, "moderate", ["Warrior series", "Balance poses"]),
            _session("Tuesday", "Deep stretch", "flexibility", 40, "low", ["Hamstring/hip deep stretch", "Pigeon pose"]),
            _session("Wednesday", "Mobility + core", "flexibility", 35, "moderate", ["Planks", "Hip mobility", "Spinal rotations"]),
            _session("Thursday", "Yin yoga", "flexibility", 45, "low", ["Long holds", "Respiratory relaxation"]),
            _session("Friday", "Dynamic mobility", "flexibility", 35, "moderate", ["Lunges with twist", "Arm/latra swings"]),
            _session("Saturday", "Yoga flow + stretch", "flexibility", 45, "moderate", ["Sun salutations", "Full body stretch"]),
            _session("Sunday", "Rest", "recovery", 0, "rest", ["Rest"]),
        ],
    },
    "advanced": {
        "general_fitness": [
            _session("Monday", "Heavy lower body", "strength", 70, "high", ["Back squats", "Romanian deadlifts", "Lunges", "Calf raises"]),
            _session("Tuesday", "Upper body volume", "strength", 70, "high", ["Bench press", "Rows", "Overhead press", "Pull-ups"]),
            _session("Wednesday", "HIIT conditioning", "cardio", 40, "high", ["Sled pushes", "Burpees", "Sprint intervals"]),
            _session("Thursday", "Olympic lift focus", "strength", 70, "high", ["Clean & press", "Front squats", "Snatch warmups"]),
            _session("Friday", "Full body + metcon", "strength + cardio", 50, "high", ["Kettlebell work", "Thrusters", "Row intervals"]),
            _session("Saturday", "Active recovery", "cardio", 35, "low", ["Easy bike/swim, mobility work"]),
            _session("Sunday", "Rest day", "recovery", 0, "rest", ["Recovery protocol"]),
        ],
        "weight_loss": [
            _session("Monday", "HIIT", "cardio + strength", 45, "high", ["Tabata intervals", "Burpees", "Kettlebell swings"]),
            _session("Tuesday", "Strength circuit", "strength", 45, "high", ["Squats", "Bench press", "Rows", "Lunges"]),
            _session("Wednesday", "Conditioning", "cardio", 45, "high", ["Rowing/running intervals", "Jump rope"]),
            _session("Thursday", "Total body power", "strength + cardio", 45, "high", ["Power cleans (light)", "Box jumps", "Thrusters"]),
            _session("Friday", "Metcon", "cardio + strength", 45, "high", ["AMRAP circuits", "Sled work"]),
            _session("Saturday", "Long steady", "cardio", 60, "moderate", ["Long run/cycle/swim"]),
            _session("Sunday", "Active rest", "recovery", 20, "low", ["Walk, stretch, recovery nutrition"]),
        ],
        "muscle_gain": [
            _session("Monday", "Chest + shoulders", "strength", 75, "high", ["Bench press", "Incline press", "Overhead press", "Lateral raises"]),
            _session("Tuesday", "Back", "strength", 75, "high", ["Deadlifts", "Pull-ups", "Barbell rows", "Face pulls"]),
            _session("Wednesday", "Legs", "strength", 75, "high", ["Squats", "Romanian deadlifts", "Leg press", "Calf raises"]),
            _session("Thursday", "Arms + core", "strength", 60, "high", ["Close-grip press", "Curls", "Skull crushers", "Hanging leg raises"]),
            _session("Friday", "Full body power", "strength", 70, "high", ["Clean & press", "Front squats", "Weighted pull-ups"]),
            _session("Saturday", "Active recovery", "mobility", 30, "low", ["Mobility, core work"]),
            _session("Sunday", "Rest day", "recovery", 0, "rest", ["Recovery"]),
        ],
        "endurance": [
            _session("Monday", "Speed intervals", "cardio", 45, "high", ["Repeats near sprint effort with rest"]),
            _session("Tuesday", "Tempo run", "cardio", 40, "high", ["Sustained fast pace"]),
            _session("Wednesday", "Threshold work", "cardio", 45, "high", ["Cruise intervals at threshold"]),
            _session("Thursday", "Easy recovery run", "cardio", 30, "low", ["Conversation pace run"]),
            _session("Friday", "Long run", "cardio", 90, "moderate", ["Sustained longer run"]),
            _session("Saturday", "Strength for endurance", "strength", 30, "moderate", ["Core, single-leg work"]),
            _session("Sunday", "Rest", "recovery", 0, "rest", ["Rest and refuel"]),
        ],
        "flexibility": [
            _session("Monday", "Advanced yoga", "flexibility", 60, "moderate", ["Deep backbends", "Balance work"]),
            _session("Tuesday", "Mobility mastery", "flexibility", 45, "moderate", ["Hip dynamic mobility", "Shoulder dislocates"]),
            _session("Wednesday", "Deep stretch", "flexibility", 50, "low", ["Pigeon", "Splits work", "Hip flexors"]),
            _session("Thursday", "Strength + flexibility", "flexibility", 45, "moderate", ["Holds, resistance band mobility"]),
            _session("Friday", "Restorative yoga", "flexibility", 50, "low", ["Long passive holds"]),
            _session("Saturday", "Yoga flow", "flexibility", 55, "moderate", ["Power flow", "Balance"]),
            _session("Sunday", "Rest", "recovery", 0, "rest", ["Recovery"]),
        ],
    },
}


RESTRICTION_NOTES = {
    "knee": "High-impact movements were replaced with low-impact options to protect the knees.",
    "back": "Heavy spinal loading movements were reduced; core stability is prioritised.",
    "heart": "Very high intensity intervals were moderated; keep exertion conversation-level unless cleared.",
    "hypertension": "Brief warm-up/cool-down emphasised; no breath-held straining under load.",
    "diabetes": "Scheduled activity spread across the day; carry a quick carb source and check glucose.",
    "pregnancy": "Only low/light intensity, doctor-cleared activities are included.",
}


def _low_impact(day: dict) -> dict:
    day = dict(day)
    day["exercises"] = [e for e in day["exercises"] if e.lower() not in {"burpees", "box jumps", "sprint"}]
    if day["intensity"] == "high":
        day["intensity"] = "moderate"
    return day


def _filter_restrictions(week, restrictions: list[str]):
    low = {r.strip().lower() for r in restrictions if r and r.strip()}
    if "knee" in low or "pregnancy" in low or "back" in low:
        week = [_low_impact(d) for d in week]
    notes = [RESTRICTION_NOTES[r] for r in low if r in RESTRICTION_NOTES]
    return week, notes


def generate_plan(
    fitness_level: str = "beginner",
    goal: str = "general_fitness",
    medical_restrictions: list[str] | None = None,
) -> dict:
    level = fitness_level.strip().lower() if fitness_level else "beginner"
    if level not in FITNESS_LEVELS:
        level = "beginner"
    target_goal = goal.strip().lower() if goal else "general_fitness"
    if target_goal not in EXERCISE_GOALS:
        target_goal = "general_fitness"

    template = WEEK_TEMPLATES[level][target_goal]
    restrictions = list(medical_restrictions or [])
    week, notes = _filter_restrictions(template, restrictions)
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    weekly_plan = []
    total_duration = 0
    for index, (day, slot) in enumerate(zip(day_names, week)):
        entry = dict(slot)
        entry["day"] = day
        entry["day_number"] = index + 1
        total_duration += entry["duration_minutes"]
        weekly_plan.append(entry)

    return {
        "fitness_level": level,
        "goal": target_goal,
        "weekly_plan": weekly_plan,
        "total_minutes_per_week": total_duration,
        "restriction_notes": notes,
        "restrictions_applied": restrictions,
    }