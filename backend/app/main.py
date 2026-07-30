from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    routes_analysis,
    routes_cloudtrail,
    routes_cloudwatch,
    routes_meta,
)
from app.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.rate_limiter import InboundRateLimiter

settings = get_settings()
inbound_rate_limiter = InboundRateLimiter(settings.inbound_rate_limit_per_minute)

app = FastAPI(title="TraceMind")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def enforce_inbound_rate_limit(request: Request, call_next):
    client_key = request.client.host if request.client else "unknown"
    if not await inbound_rate_limiter.allow(client_key):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Slow down and try again shortly."},
        )
    return await call_next(request)


register_exception_handlers(app)

app.include_router(routes_meta.router)
app.include_router(routes_cloudwatch.router)
app.include_router(routes_cloudtrail.router)
app.include_router(routes_analysis.router)
