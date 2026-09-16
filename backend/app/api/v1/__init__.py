from fastapi import APIRouter

from app.api.v1 import (
    auth,
    admin,
    patients,
    doctors,
    appointments,
    consultations,
    reports,
    symptoms,
    risk,
    vision,
    diet,
    exercise,
    medications,
    emergency,
    wellness,
    timeline,
    analytics,
    healthcare_services,
    chat,
    dashboard,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(patients.router)
api_router.include_router(doctors.router)
api_router.include_router(appointments.router)
api_router.include_router(consultations.router)
api_router.include_router(reports.router)
api_router.include_router(symptoms.router)
api_router.include_router(risk.router)
api_router.include_router(vision.router)
api_router.include_router(diet.router)
api_router.include_router(exercise.router)
api_router.include_router(medications.router)
api_router.include_router(emergency.router)
api_router.include_router(wellness.router)
api_router.include_router(timeline.router)
api_router.include_router(analytics.router)
api_router.include_router(healthcare_services.router)
api_router.include_router(chat.router)
api_router.include_router(dashboard.router)