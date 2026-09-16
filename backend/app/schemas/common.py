from typing import Any, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    message: str | None = None


class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedResponse(ApiResponse[PaginatedData[T]]):
    pass


class ErrorResponse(BaseModel):
    success: bool = False
    error: dict[str, Any]