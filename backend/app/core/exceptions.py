from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from starlette.requests import Request
import logging

logger = logging.getLogger("medivision.error")

class AppException(Exception):
    """Base application exception with a machine-readable code."""
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str = "app_error",
        details: dict | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details
        super().__init__(message)


class NotFoundException(AppException):
    def __init__(self, message: str, code: str = "not_found"):
        super().__init__(message, status.HTTP_404_NOT_FOUND, code)


class ConflictException(AppException):
    def __init__(self, message: str, code: str = "conflict"):
        super().__init__(message, status.HTTP_409_CONFLICT, code)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Authentication required", code: str = "unauthorized"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED, code)


class ForbiddenException(AppException):
    def __init__(self, message: str = "Insufficient permissions", code: str = "forbidden"):
        super().__init__(message, status.HTTP_403_FORBIDDEN, code)


class ValidationException(AppException):
    def __init__(self, message: str, details: dict | None = None, code: str = "validation_error"):
        super().__init__(message, status.HTTP_422_UNPROCESSABLE_ENTITY, code, details)


def register_exception_handlers(app):
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                },
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "details": jsonable_encoder(exc.errors()),
                },
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "internal_server_error",
                    "message": "An unexpected error occurred. Please try again.",
                },
            },
        )