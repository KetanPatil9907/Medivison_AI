"""Patient medical report uploads, downloads and document management.

Files live in object storage; the medical_reports row keeps metadata only.
Patients own their reports (including those for family profiles); doctors may
download a report when they have an appointment or consultation with the
owning patient."""

import io
from datetime import date, datetime, timezone
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.deps import require_patient, require_patient_doctor
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from app.models import Appointment, Consultation, FamilyProfile, MedicalReport, User, UserRole
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse
from app.services.storage_service import storage
from app.services.timeline_service import add_timeline_event, log_json
from app.utils.audit import write_audit_log

router = APIRouter(prefix="/reports", tags=["reports"])

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB
CATEGORY_PATTERN = "^(blood_report|xray|prescription|document|scan|other)$"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf", "tif", "tiff", "dcm", "dicom"}
EXT_TO_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "pdf": "application/pdf",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "dcm": "application/dicom",
    "dicom": "application/dicom",
}
FALLBACK_MIMES = {"application/octet-stream"}


def _validate_upload(file: UploadFile) -> tuple[str, str]:
    filename = (file.filename or "").strip()
    if not filename or "." not in filename:
        raise ValidationException("Unable to determine the file extension", details={"file_name": filename})
    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationException(
            "File type not allowed",
            details={"file_name": filename, "extension": ext},
        )
    mime = EXT_TO_MIME[ext]
    content_type = (file.content_type or "").lower()
    if content_type and content_type not in ({mime} | FALLBACK_MIMES):
        raise ValidationException(
            "File content type does not match its extension",
            details={"file_name": filename, "extension": ext, "content_type": content_type},
        )
    return ext, mime


def _validate_family_profile(db: Session, user: User, family_profile_id: int | None) -> None:
    if family_profile_id is None:
        return
    family = db.get(FamilyProfile, family_profile_id)
    if not family or not user.patient_profile or family.patient_profile_id != user.patient_profile.id:
        raise NotFoundException("Family profile not found")


def _base_report_query(db: Session, user_id: int):
    query = db.query(MedicalReport).filter(MedicalReport.patient_id == user_id)
    if hasattr(MedicalReport, "is_deleted"):
        query = query.filter(MedicalReport.is_deleted.is_(False))
    return query


def _get_own_report(db: Session, user: User, report_id: int) -> MedicalReport:
    report = db.get(MedicalReport, report_id)
    if not report or report.patient_id != user.id:
        raise NotFoundException("Medical report not found")
    if hasattr(MedicalReport, "is_deleted") and report.is_deleted:
        raise NotFoundException("Medical report not found")
    return report


def _delete_report_row(db: Session, report: MedicalReport) -> None:
    if hasattr(MedicalReport, "is_deleted"):
        report.is_deleted = True
        if hasattr(MedicalReport, "deleted_at"):
            report.deleted_at = datetime.now(timezone.utc)
    else:
        db.delete(report)


def _doctor_has_access(db: Session, doctor: User, patient_id: int) -> bool:
    has_appointment = (
        db.query(Appointment.id)
        .filter(Appointment.doctor_id == doctor.id, Appointment.patient_id == patient_id)
        .first()
    )
    if has_appointment:
        return True
    has_consultation = (
        db.query(Consultation.id)
        .filter(Consultation.doctor_id == doctor.id, Consultation.patient_id == patient_id)
        .first()
    )
    return has_consultation is not None


def _report_json(report: MedicalReport) -> dict:
    return {
        "id": report.id,
        "patient_id": report.patient_id,
        "family_profile_id": report.family_profile_id,
        "title": report.title,
        "category": report.category,
        "report_date": report.report_date.isoformat() if report.report_date else None,
        "condition": report.condition,
        "notes": report.notes,
        "file_name": report.file_name,
        "file_size": report.file_size,
        "file_type": report.file_type,
        "storage_driver": report.storage_driver,
        "uploaded_by": report.uploaded_by,
        "download_url": storage.public_url(report.file_key),
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


@router.post("/upload", response_model=ApiResponse[dict])
async def upload_report(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(..., min_length=1, max_length=200),
    category: str = Form(default="other", pattern=CATEGORY_PATTERN),
    report_date: Optional[date] = Form(default=None),
    condition: Optional[str] = Form(default=None, max_length=150),
    notes: Optional[str] = Form(default=None),
    family_profile_id: Optional[int] = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    _validate_family_profile(db, current_user, family_profile_id)
    ext, mime = _validate_upload(file)

    data = await file.read()
    if len(data) == 0:
        raise ValidationException("Uploaded file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationException(
            "File exceeds the 15 MB upload limit",
            details={"file_size": len(data), "max_size_bytes": MAX_UPLOAD_BYTES},
        )

    key = storage.build_key("reports", current_user.id, file.filename or f"report.{ext}")
    storage.upload(key, io.BytesIO(data), mime, size=len(data))

    report = MedicalReport(
        patient_id=current_user.id,
        family_profile_id=family_profile_id,
        title=title,
        category=category,
        report_date=report_date,
        condition=condition,
        notes=notes,
        file_key=key,
        file_name=file.filename or key.rsplit("/", 1)[-1],
        file_size=len(data),
        file_type=mime,
        storage_driver=settings.storage_driver,
        uploaded_by="patient",
    )
    db.add(report)
    db.flush()

    add_timeline_event(
        db,
        current_user.id,
        "report",
        "Medical report uploaded",
        description=f"{title} ({category}) uploaded",
        event_date=report_date or datetime.now(timezone.utc).date(),
        metadata_json=log_json({
            "report_id": report.id,
            "title": title,
            "category": category,
            "file_name": report.file_name,
            "file_size": len(data),
            "family_profile_id": family_profile_id,
        }),
        family_profile_id=family_profile_id,
    )
    db.commit()
    db.refresh(report)

    write_audit_log(
        db, current_user, "reports.upload",
        resource_type="medical_report", resource_id=str(report.id),
        request=request,
        after={
            "title": title,
            "category": category,
            "file_name": report.file_name,
            "file_size": len(data),
            "file_type": mime,
            "family_profile_id": family_profile_id,
        },
    )
    return ApiResponse(data=_report_json(report), message="Medical report uploaded")


@router.get("/my", response_model=PaginatedResponse)
async def my_reports(
    category: Optional[str] = Query(None, pattern=CATEGORY_PATTERN),
    condition: Optional[str] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    search: Optional[str] = Query(None),
    family_profile_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    if family_profile_id is not None:
        _validate_family_profile(db, current_user, family_profile_id)

    query = _base_report_query(db, current_user.id)
    if category:
        query = query.filter(MedicalReport.category == category)
    if condition:
        query = query.filter(MedicalReport.condition.ilike(f"%{condition}%"))
    if from_date:
        query = query.filter(MedicalReport.report_date >= from_date)
    if to_date:
        query = query.filter(MedicalReport.report_date <= to_date)
    if search:
        query = query.filter(MedicalReport.title.ilike(f"%{search}%"))
    if family_profile_id is not None:
        query = query.filter(MedicalReport.family_profile_id == family_profile_id)

    total = query.count()
    reports = (
        query.order_by(MedicalReport.report_date.desc().nullslast(), MedicalReport.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedResponse(
        data=PaginatedData(
            items=[_report_json(r) for r in reports],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        ),
        message="Medical reports retrieved",
    )


@router.get("/{report_id}", response_model=ApiResponse[dict])
async def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    report = _get_own_report(db, current_user, report_id)
    return ApiResponse(data=_report_json(report), message="Medical report retrieved")


@router.delete("/{report_id}", response_model=ApiResponse[dict])
async def delete_report(
    report_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    report = _get_own_report(db, current_user, report_id)
    before = {
        "title": report.title,
        "category": report.category,
        "file_name": report.file_name,
        "file_size": report.file_size,
    }

    storage.delete(report.file_key)
    _delete_report_row(db, report)
    db.flush()

    add_timeline_event(
        db,
        current_user.id,
        "report",
        "Medical report deleted",
        description=f"{report.title} was deleted",
        event_date=datetime.now(timezone.utc).date(),
        metadata_json=log_json({"report_id": report.id, "title": report.title}),
        family_profile_id=report.family_profile_id,
    )
    db.commit()

    write_audit_log(
        db, current_user, "reports.delete",
        resource_type="medical_report", resource_id=str(report_id),
        request=request, before=before,
    )
    return ApiResponse(message="Medical report deleted")


@router.get("/{report_id}/download")
async def download_report(
    report_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient_doctor),
):
    if current_user.role == UserRole.PATIENT:
        report = _get_own_report(db, current_user, report_id)
    else:
        report = db.get(MedicalReport, report_id)
        if not report:
            raise NotFoundException("Medical report not found")
        if hasattr(MedicalReport, "is_deleted") and report.is_deleted:
            raise NotFoundException("Medical report not found")
        if not _doctor_has_access(db, current_user, report.patient_id):
            raise ForbiddenException("You do not have a clinical relationship with this patient")

    content = storage.download(report.file_key)
    write_audit_log(
        db, current_user, "reports.download",
        resource_type="medical_report", resource_id=str(report_id),
        request=request, after={"title": report.title, "file_name": report.file_name},
    )
    safe_name = "".join(c if c.isalnum() or c in ".-_ " else "_" for c in report.file_name)
    headers = {
        "Content-Disposition": (
            f"attachment; filename*=UTF-8''{quote(report.file_name)}"
            f"; filename=\"{safe_name}\""
        ),
    }
    return Response(
        content=content,
        media_type=report.file_type or "application/octet-stream",
        headers=headers,
    )