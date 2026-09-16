from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.api.v1 import api_router
from app.api import health
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

app = FastAPI(
    title=settings.app_name,
    description="AI-Powered Intelligent Healthcare & Diagnostic Platform",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],
)

app.include_router(health.router)
app.include_router(api_router, prefix=settings.api_v1_prefix)

register_exception_handlers(app)


@app.get("/", include_in_schema=False)
async def root():
    return {"name": settings.app_name, "version": settings.app_version, "status": "running"}