from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_analysis,
    routes_cloudtrail,
    routes_cloudwatch,
    routes_meta,
    routes_s3,
)
from app.config import get_settings
from app.core.errors import register_exception_handlers

settings = get_settings()

app = FastAPI(title="TraceMind")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(routes_meta.router)
app.include_router(routes_cloudwatch.router)
app.include_router(routes_s3.router)
app.include_router(routes_cloudtrail.router)
app.include_router(routes_analysis.router)
