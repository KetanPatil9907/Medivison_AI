from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Depends

from app.core.database import get_db
from app.schemas.common import ApiResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=ApiResponse[dict])
async def health_check(db: Session = Depends(get_db)):
    db_status = "up"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "down"
    return ApiResponse(
        data={"status": "ok", "database": db_status, "app": "MediVision AI"},
        message="Service healthy",
    )