"""
FastAPI exception handlers.

Maps custom exceptions to proper HTTP responses.
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import (
    EntityNotFoundError,
    EntityAlreadyExistsError,
    BusinessRuleViolationError,
    ValidationError,
    DatabaseError,
)


async def entity_not_found_handler(
    request: Request,
    exc: EntityNotFoundError,
) -> JSONResponse:
    """Handle 404 Not Found errors."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "Not Found",
            "message": exc.message,
            "details": exc.details,
        },
    )


async def entity_already_exists_handler(
    request: Request,
    exc: EntityAlreadyExistsError,
) -> JSONResponse:
    """Handle 400 Bad Request (duplicate entity)."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Entity Already Exists",
            "message": exc.message,
            "details": exc.details,
        },
    )


async def business_rule_violation_handler(
    request: Request,
    exc: BusinessRuleViolationError,
) -> JSONResponse:
    """Handle 400 Bad Request (business rule violation)."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Business Rule Violation",
            "message": exc.message,
            "details": exc.details,
        },
    )


async def validation_error_handler(
    request: Request,
    exc: ValidationError,
) -> JSONResponse:
    """Handle 422 Unprocessable Entity (validation error)."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "message": exc.message,
            "details": exc.details,
        },
    )


async def database_error_handler(
    request: Request,
    exc: DatabaseError,
) -> JSONResponse:
    """Handle 500 Internal Server Error (database error)."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Database Error",
            "message": exc.message,
            # Don't expose internal details in production
        },
    )