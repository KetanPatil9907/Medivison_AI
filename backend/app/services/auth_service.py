from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ConflictException, UnauthorizedException
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.models.user import User, UserRole, UserStatus
from app.schemas.auth import RegisterPatientRequest, RegisterDoctorRequest


def _raise_if_email_taken(db: Session, email: str) -> None:
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise ConflictException("An account with this email already exists", code="email_taken")


def register_patient(db: Session, payload: RegisterPatientRequest) -> User:
    _raise_if_email_taken(db, payload.email)

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.PATIENT,
        status=UserStatus.ACTIVE,
        phone=payload.phone,
        preferred_language=payload.preferred_language or "en",
    )
    db.add(user)
    db.flush()

    from app.models.patient import PatientProfile
    profile = PatientProfile(
        user_id=user.id,
        age=payload.age,
        gender=payload.gender,
        blood_group=payload.blood_group,
        height_cm=payload.height_cm,
        weight_kg=payload.weight_kg,
        allergies=payload.allergies,
        chronic_conditions=payload.chronic_conditions,
        emergency_contact_name=payload.emergency_contact_name,
        emergency_contact_phone=payload.emergency_contact_phone,
        emergency_contact_relation=payload.emergency_contact_relation,
    )
    db.add(profile)
    db.flush()

    from app.models.analytics import HealthTimeline
    db.add(HealthTimeline(
        patient_id=user.id,
        event_type="health_event",
        title="Profile created",
        description="Patient account and health profile created.",
        event_date=datetime.now(timezone.utc).date(),
    ))

    db.commit()
    db.refresh(user)
    return user


def register_doctor(db: Session, payload: RegisterDoctorRequest) -> User:
    _raise_if_email_taken(db, payload.email)

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.DOCTOR,
        status=UserStatus.PENDING,
        phone=payload.phone,
        preferred_language=payload.preferred_language or "en",
    )
    db.add(user)
    db.flush()

    from app.models.user import DoctorApplication
    application = DoctorApplication(
        user_id=user.id,
        phone=payload.phone,
        specialization=payload.specialization,
        qualification=payload.qualification,
        medical_registration_number=payload.medical_registration_number,
        years_of_experience=payload.years_of_experience,
        hospital=payload.hospital,
        address=payload.address,
        consultation_type=payload.consultation_type,
        status="PENDING",
    )
    db.add(application)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        raise UnauthorizedException("Incorrect email or password", code="invalid_credentials")

    if user.status == UserStatus.PENDING:
        raise UnauthorizedException(
            "Your doctor application is pending admin approval. Please wait.",
            code="pending_approval",
        )
    if user.status == UserStatus.REJECTED:
        raise UnauthorizedException(
            "Your doctor application was rejected. Contact support for details.",
            code="rejected",
        )
    if user.status == UserStatus.SUSPENDED:
        raise UnauthorizedException("Your account is suspended.", code="suspended")
    if user.status == UserStatus.DISABLED:
        raise UnauthorizedException("Your account is disabled.", code="disabled")

    user.last_login_at = datetime.now(timezone.utc)
    user.status = UserStatus.ACTIVE if user.status == UserStatus.ACTIVE else user.status
    db.commit()
    return user


def issue_tokens(user: User) -> dict:
    access = create_access_token(user.id, user.role.value)
    refresh = create_refresh_token(user.id, user.role.value)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }