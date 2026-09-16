# Database: List all 25+ tables in dependency order.
# Identity first, then healthcare, then domain tables.
from app.models.user import (
    User, DoctorApplication, DoctorProfile, DoctorQualification,
    DoctorSpecialty, DoctorAvailability,
)
from app.models.patient import (
    PatientProfile, EmergencyContact, FamilyProfile, MedicalHistory, HealthMetric,
)
from app.models.healthcare import (
    Hospital, Clinic, Pharmacy, DiagnosticLab, HealthcareService,
)
from app.models.clinical import (
    Appointment, Consultation, Prescription, Medication, MedicalReport,
)
from app.models.ai import (
    SymptomSession, SymptomResult, RiskAssessment, ImageAnalysis,
    AIPrediction, AIExplanation,
)
from app.models.wellness import (
    DietPlan, ExercisePlan, PreventiveReminder, MentalWellnessEntry, HealthScore,
)
from app.models.analytics import (
    HealthTimeline, HealthTrend, AnalyticsSnapshot, AuditLog,
)

TABLES = [
    User, DoctorApplication, DoctorProfile, DoctorQualification, DoctorSpecialty, DoctorAvailability,
    PatientProfile, EmergencyContact, FamilyProfile, MedicalHistory, HealthMetric,
    Hospital, Clinic, Pharmacy, DiagnosticLab, HealthcareService,
    Appointment, Consultation, Prescription, Medication, MedicalReport,
    SymptomSession, SymptomResult, RiskAssessment, ImageAnalysis, AIPrediction, AIExplanation,
    DietPlan, ExercisePlan, PreventiveReminder, MentalWellnessEntry, HealthScore,
    HealthTimeline, HealthTrend, AnalyticsSnapshot, AuditLog,
]

__all__ = ["TABLES"]