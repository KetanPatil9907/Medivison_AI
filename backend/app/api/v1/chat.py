"""AI assistant chat endpoints.

The assistant is a health-education copilot with an LLM integration when
configured (llm_api_key set) and an offline rule engine otherwise. It never
diagnoses; emergency language is escalated immediately.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import AppException
from app.models import User
from app.schemas.common import ApiResponse
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])

logger = logging.getLogger("medivision.api.chat")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    context: Optional[dict] = Field(default_factory=dict, description="Optional context e.g. latest risk/symptom IDs")


@router.get("/quick-replies", response_model=ApiResponse[dict])
async def quick_replies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return ApiResponse(
            data={
                "quick_replies": chat_service.QUICK_REPLIES,
                "disclaimer": chat_service.DISCLAIMER,
            },
            message="Quick replies retrieved",
        )
    except AppException:
        raise
    except Exception as exc:
        logger.error("Failed to load quick replies", exc_info=True)
        raise AppException("Failed to load quick replies. Please try again.", code="chat_error")


@router.post("", response_model=ApiResponse[dict])
async def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        response = chat_service.respond(payload.message, payload.context)
        return ApiResponse(data=response, message="Assistant reply ready")
    except AppException:
        raise
    except Exception as exc:
        logger.error(
            "Chat failed",
            extra={"user_id": current_user.id, "error": str(exc)},
            exc_info=True,
        )
        raise AppException("Failed to get a reply. Please try again.", code="chat_error")