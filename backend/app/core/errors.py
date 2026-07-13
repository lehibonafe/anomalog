from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 500

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class LLMQuotaExceededError(AppError):
    status_code = 429


class LLMRequestError(AppError):
    status_code = 502


class NotFoundError(AppError):
    status_code = 404


class BadRequestError(AppError):
    status_code = 400


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def register_exception_handlers(app) -> None:
    app.add_exception_handler(AppError, app_error_handler)
