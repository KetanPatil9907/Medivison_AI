from datetime import date
from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class DietPlan(BaseModel):
    __tablename__ = "diet_plans"

    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    bmi: Mapped[float | None] = mapped_column(Float, nullable=True)
    bmr: Mapped[float | None] = mapped_column(Float, nullable=True)
    tdee: Mapped[float | None] = mapped_column(Float, nullable=True)
    calorie_target: Mapped[float | None] = mapped_column(Float, nullable=True)
    protein_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    carbs_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    fat_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    water_liters: Mapped[float | None] = mapped_column(Float, nullable=True)
    breakfast: Mapped[Text | None] = mapped_column(Text, nullable=True, doc="JSON meals + options")
    lunch: Mapped[Text | None] = mapped_column(Text, nullable=True)
    dinner: Mapped[Text | None] = mapped_column(Text, nullable=True)
    snacks: Mapped[Text | None] = mapped_column(Text, nullable=True)
    goal: Mapped[str | None] = mapped_column(String(50), nullable=True)  # weight_loss|weight_gain|maintain|muscle_gain
    dietary_preference: Mapped[str | None] = mapped_column(String(30), nullable=True)


class ExercisePlan(BaseModel):
    __tablename__ = "exercise_plans"

    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    plan_start: Mapped[date] = mapped_column(Date, nullable=False)
    fitness_level: Mapped[str] = mapped_column(String(30), default="beginner", nullable=False)
    goal: Mapped[str] = mapped_column(String(50), default="general_fitness", nullable=False)
    weekly_plan: Mapped[Text | None] = mapped_column(Text, nullable=True, doc="JSON: day -> schedule")
    medical_restrictions: Mapped[Text | None] = mapped_column(Text, nullable=True)
    progress: Mapped[Text | None] = mapped_column(Text, nullable=True, doc="JSON: week -> completed sessions")


class PreventiveReminder(BaseModel):
    __tablename__ = "preventive_reminders"

    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    reminder_type: Mapped[str] = mapped_column(String(40), nullable=False)  # vaccination|checkup|screening|lifestyle
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    frequency_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending|done|overdue|dismissed
    details: Mapped[Text | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="rule_engine", nullable=False)


class MentalWellnessEntry(BaseModel):
    __tablename__ = "mental_wellness"

    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)  # mood_journal|stress_tracking|meditation
    mood_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-10
    stress_level: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-10
    journal_text: Mapped[Text | None] = mapped_column(Text, nullable=True)
    breathing_session: Mapped[Text | None] = mapped_column(Text, nullable=True, doc="JSON session meta")
    meditation_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)


class HealthScore(BaseModel):
    __tablename__ = "health_scores"

    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, doc="0-100")
    previous_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    factors_improving: Mapped[Text | None] = mapped_column(Text, nullable=True, doc="JSON list")
    factors_reducing: Mapped[Text | None] = mapped_column(Text, nullable=True, doc="JSON list")
    breakdown: Mapped[Text | None] = mapped_column(Text, nullable=True, doc="JSON: sleep/exercise/bmi/bp/water/activity")
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)