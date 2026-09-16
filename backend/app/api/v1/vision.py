"""Computer vision analysis endpoints (medical image understanding).

DISCLAIMER: model outputs are assistive screening predictions only and are not a
diagnosis. In demo/fallback mode (no model weights) results are labelled clearly
as rule-based.
"""

import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.auth.deps import require_patient
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AppException, NotFoundException, ValidationException
from app.models import AIExplanation, ImageAnalysis, User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse
from app.services import vision_service
from app.services.storage_service import storage
from app.services.timeline_service import add_timeline_event, log_json
from app.utils.audit import write_audit_log

router = APIRouter(prefix="/vision", tags=["vision"])

logger = logging.getLogger("medivision.api.vision")

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
MIME_BY_EXT = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}
MODALITY_CHOICES = "|".join(sorted(vision_service.MODALITIES))

VISION_DISCLAIMER = (
    "Image analysis results are screening predictions and are not a clinical "
    "diagnosis. A qualified radiologist or specialist should confirm any finding."
)


def _validate_image_upload(file: UploadFile) -> tuple[str, str]:
    filename = (file.filename or "").strip()
    if not filename or "." not in filename:
        raise ValidationException("Unable to determine the file extension")
    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationException(
            "Only PNG/JPG/JPEG images are accepted",
            details={"file_name": filename, "extension": ext},
        )
    mime = MIME_BY_EXT[ext]
    content_type = (file.content_type or "").lower()
    if content_type and content_type != mime and content_type != "application/octet-stream":
        raise ValidationException(
            "File content type does not match its extension",
            details={"file_name": filename, "content_type": content_type},
        )
    return ext, mime


def _analysis_json(analysis: ImageAnalysis, explanation: AIExplanation | None = None) -> dict:
    return {
        "id": analysis.id,
        "modality": analysis.modality,
        "prediction_label": analysis.prediction_label,
        "confidence": analysis.confidence,
        "class_probabilities": _load_json(analysis.class_probabilities),
        "model_name": analysis.model_name,
        "is_demo": analysis.is_demo,
        "status": analysis.status,
        "error_message": analysis.error_message,
        "image_url": storage.public_url(analysis.image_key),
        "grad_cam_url": storage.public_url(analysis.grad_cam_key) if analysis.grad_cam_key else None,
        "explanation": explanation.content if explanation else analysis.error_message,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
    }


def _load_json(raw: str | None):
    if not raw:
        return {}
    import json
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def _get_own_analysis(db: Session, user: User, analysis_id: int) -> ImageAnalysis:
    analysis = db.get(ImageAnalysis, analysis_id)
    if not analysis or analysis.patient_id != user.id:
        raise NotFoundException("Image analysis not found")
    return analysis


@router.post("/analyze", response_model=ApiResponse[dict])
async def analyze_image_upload(
    request: Request,
    file: UploadFile = File(...),
    modality: str = Form(..., description=f"One of: {', '.join(sorted(vision_service.MODALITIES))}"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    ext, mime = _validate_image_upload(file)
    key = modality.strip().lower()
    if key not in vision_service.MODALITIES:
        raise ValidationException(
            f"Unsupported modality '{modality}'",
            details={"supported": sorted(vision_service.MODALITIES)},
        )

    data = await file.read()
    if len(data) == 0:
        raise ValidationException("Uploaded image is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationException(
            "Image exceeds the 15 MB upload limit",
            details={"file_size": len(data)},
        )

    try:
        result = vision_service.analyze_image(key, data)
    except ValidationException:
        raise
    except Exception as exc:
        logger.error("Vision analysis failed", exc_info=True)
        raise AppException("Image analysis failed. Please try again.", code="vision_error")

    original_name = file.filename or f"image.{ext}"
    image_key = storage.build_key("ai", current_user.id, original_name)
    storage.upload(image_key, io.BytesIO(data), mime, size=len(data))

    grad_cam_key = None
    saliency = vision_service.build_saliency(data)
    if saliency is not None:
        grad_cam_key = f"{image_key.rsplit('.', 1)[0]}_saliency.png"
        storage.upload(grad_cam_key, io.BytesIO(saliency), "image/png", size=len(saliency))

    analysis = ImageAnalysis(
        patient_id=current_user.id,
        modality=result["modality"],
        prediction_label=result["prediction_label"],
        confidence=result["confidence"],
        class_probabilities=log_json(result["class_probabilities"]),
        model_name=result["model_name"],
        image_key=image_key,
        grad_cam_key=grad_cam_key,
        status=result.get("status", "completed"),
        is_demo=result["is_demo"],
        error_message=result.get("explanation"),
    )
    db.add(analysis)
    db.flush()

    db.add(
        AIExplanation(
            image_analysis_id=analysis.id,
            explanation_type="grad_cam",
            content=result.get("explanation", ""),
            visual_key=grad_cam_key,
        )
    )
    db.flush()

    add_timeline_event(
        db,
        current_user.id,
        "ai_analysis",
        "Image analysis: " + result["modality"].replace("_", " "),
        description=f"Predicted {result['prediction_label']} with "
                    f"{result['confidence'] * 100:.1f}% confidence",
        severity=None,
        metadata_json=log_json(
            {
                "analysis_id": analysis.id,
                "modality": result["modality"],
                "prediction_label": result["prediction_label"],
                "confidence": result["confidence"],
                "model_name": result["model_name"],
            }
        ),
    )

    db.commit()
    db.refresh(analysis)

    write_audit_log(
        db, current_user, "vision.analyze",
        resource_type="image_analysis", resource_id=str(analysis.id),
        request=request,
        after={
            "modality": result["modality"],
            "prediction_label": result["prediction_label"],
            "confidence": result["confidence"],
            "model_name": result["model_name"],
            "is_demo": result["is_demo"],
        },
    )
    data_json = _analysis_json(analysis)
    data_json["disclaimer"] = VISION_DISCLAIMER
    return ApiResponse(data=data_json, message="Image analysis completed")


@router.get("/my-analyses", response_model=PaginatedResponse)
async def my_analyses(
    modality: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        base = db.query(ImageAnalysis).filter(ImageAnalysis.patient_id == current_user.id)
        if modality:
            key = modality.strip().lower()
            if key not in vision_service.MODALITIES:
                raise ValidationException(
                    f"Unsupported modality '{modality}'",
                    details={"supported": sorted(vision_service.MODALITIES)},
                )
            base = base.filter(ImageAnalysis.modality == key)
        total = base.count()
        analyses = (
            base.order_by(ImageAnalysis.created_at.desc(), ImageAnalysis.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return PaginatedResponse(
            data=PaginatedData(
                items=[_analysis_json(a) for a in analyses],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=(total + page_size - 1) // page_size,
            ),
            message=f"{total} image analyses. {VISION_DISCLAIMER}",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to list image analyses", exc_info=True)
        raise AppException("Failed to load image analyses. Please try again.", code="vision_error")


@router.get("/analyses/{analysis_id}", response_model=ApiResponse[dict])
async def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    try:
        analysis = _get_own_analysis(db, current_user, analysis_id)
        explanation = (
            db.query(AIExplanation)
            .filter(AIExplanation.image_analysis_id == analysis_id)
            .order_by(AIExplanation.created_at.desc())
            .first()
        )
        data = _analysis_json(analysis, explanation)
        data["disclaimer"] = VISION_DISCLAIMER
        return ApiResponse(data=data, message="Image analysis retrieved")
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to load image analysis", exc_info=True)
        raise AppException("Failed to load the image analysis. Please try again.", code="vision_error")