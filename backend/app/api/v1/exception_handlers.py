"""
Taurus Vision — FastAPI Exception Handlers

Custom exception larni to'g'ri HTTP javoblariga aylantiradi.

MAPPING:
    EntityNotFoundError        → 404
    EntityAlreadyExistsError   → 409
    BusinessRuleViolationError → 400
    ValidationError            → 422
    AuthenticationError        → 401
    PermissionDeniedError      → 403
    DatabaseError              → 500
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    EntityNotFoundError,
    EntityAlreadyExistsError,
    BusinessRuleViolationError,
    ValidationError,
    AuthenticationError,
    PermissionDeniedError,
    DatabaseError,
)


async def entity_not_found_handler(
    request: Request,
    exc: EntityNotFoundError,
) -> JSONResponse:
    """404 Not Found."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error":   "Not Found",
            "message": exc.message,
            "details": exc.details,
        },
    )


async def entity_already_exists_handler(
    request: Request,
    exc: EntityAlreadyExistsError,
) -> JSONResponse:
    """409 Conflict."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "error":   "Conflict",
            "message": exc.message,
            "details": exc.details,
        },
    )


async def business_rule_violation_handler(
    request: Request,
    exc: BusinessRuleViolationError,
) -> JSONResponse:
    """400 Bad Request."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error":   "Bad Request",
            "message": exc.message,
            "details": exc.details,
        },
    )


async def validation_error_handler(
    request: Request,
    exc: ValidationError,
) -> JSONResponse:
    """422 Unprocessable Entity."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error":   "Validation Error",
            "message": exc.message,
            "details": exc.details,
        },
    )


async def authentication_error_handler(
    request: Request,
    exc: AuthenticationError,
) -> JSONResponse:
    """401 Unauthorized."""
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "error":   "Unauthorized",
            "message": exc.message,
            "details": exc.details,
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


async def permission_denied_handler(
    request: Request,
    exc: PermissionDeniedError,
) -> JSONResponse:
    """403 Forbidden."""
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "error":   "Forbidden",
            "message": exc.message,
            "details": exc.details,
        },
    )


async def database_error_handler(
    request: Request,
    exc: DatabaseError,
) -> JSONResponse:
    """500 Internal Server Error. Details production da yashiriladi."""
    from app.config import settings
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error":   "Internal Server Error",
            "message": exc.message if settings.DEBUG else "Ichki server xatosi.",
        },
    )