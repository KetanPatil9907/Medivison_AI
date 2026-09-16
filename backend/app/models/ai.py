from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class SymptomSession(BaseModel):
    __tablename__ = "symptom_sessions"

    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    selected_symptoms: Mapped[str] = mapped_column(Text, nullable=False, doc="JSON list of symptom names")
    symptoms_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_days: Mapped[int | None] = mapped_column(nullable=True)
    mode: Mapped[str] = mapped_column(String(20), default="ml", nullable=False, doc="ml|rule_based|unavailable")
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)

    results = relationship("SymptomResult", back_populates="session", cascade="all, delete-orphan")


class SymptomResult(BaseModel):
    __tablename__ = "symptom_results"

    session_id: Mapped[int] = mapped_column(ForeignKey("symptom_sessions.id"), nullable=False, index=True)
    condition_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, doc="0-1")
    severity: Mapped[str] = mapped_column(String(20), nullable=False, doc="low|moderate|high|emergency")
    recommended_specialty: Mapped[str | None] = mapped_column(String(120), nullable=True)
    emergency_flag: Mapped[bool] = mapped_column(default=False, nullable=False)
    advice: Mapped[Text | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(20), default="ml", nullable=False)

    session = relationship("SymptomSession", back_populates="results")


class RiskAssessment(BaseModel):
    __tablename__ = "risk_assessments"

    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    condition_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # diabetes|hypertension|heart_disease|ckd
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, doc="low|moderate|high")
    risk_percentage: Mapped[float] = mapped_column(Float, nullable=False, doc="0-100")
    factors: Mapped[Text | None] = mapped_column(Text, nullable=True, doc="JSON: contributing factors with weights")
    explanation: Mapped[Text | None] = mapped_column(Text, nullable=True)
    recommendations: Mapped[Text | None] = mapped_column(Text, nullable=True)
    input_data: Mapped[Text | None] = mapped_column(Text, nullable=True, doc="JSON snapshot of inputs")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, doc="actual model or rule-based label")
    is_demo: Mapped[bool] = mapped_column(default=False, nullable=False, doc="true when rule-based fallback")


class ImageAnalysis(BaseModel):
    __tablename__ = "image_analyses"

    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    modality: Mapped[str] = mapped_column(String(40), nullable=False, index=True)  # brain_mri|chest_xray|skin|eye|blood_smear
    prediction_label: Mapped[str] = mapped_column(String(120), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    class_probabilities: Mapped[Text | None] = mapped_column(Text, nullable=True, doc="JSON class->prob")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    image_key: Mapped[str] = mapped_column(String(500), nullable=False)
    grad_cam_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)
    is_demo: Mapped[bool] = mapped_column(default=False, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    explanations = relationship("AIExplanation", back_populates="image_analysis", cascade="all, delete-orphan")


class AIPrediction(BaseModel):
    __tablename__ = "ai_predictions"

    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    prediction_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # weight|blood_pressure|blood_sugar|health_score|trend
    target_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    predicted_value: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_interval_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_interval_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    series: Mapped[Text | None] = mapped_column(Text, nullable=True, doc="JSON forecast series for charting")
    is_demo: Mapped[bool] = mapped_column(default=False, nullable=False)


class AIExplanation(BaseModel):
    __tablename__ = "ai_explanations"

    prediction_id: Mapped[int | None] = mapped_column(ForeignKey("ai_predictions.id"), nullable=True, index=True)
    risk_assessment_id: Mapped[int | None] = mapped_column(ForeignKey("risk_assessments.id"), nullable=True, index=True)
    image_analysis_id: Mapped[int | None] = mapped_column(ForeignKey("image_analyses.id"), nullable=True, index=True)
    explanation_type: Mapped[str] = mapped_column(String(50), nullable=False)  # grad_cam|shap|feature_importance|factors
    content: Mapped[Text] = mapped_column(Text, nullable=False)
    visual_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    image_analysis = relationship("ImageAnalysis", back_populates="explanations")