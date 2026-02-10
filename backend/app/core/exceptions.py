"""
Custom exceptions for Taurus Vision API.

These exceptions represent domain-specific errors and are caught
by FastAPI exception handlers to return proper HTTP responses.
"""

from typing import Any, Optional


class TaurusException(Exception):
    """
    Base exception for all Taurus Vision errors.
    
    All custom exceptions should inherit from this.
    """
    
    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class EntityNotFoundError(TaurusException):
    """
    Raised when a requested entity is not found in the database.
    
    Maps to HTTP 404 Not Found.
    
    Example:
        raise EntityNotFoundError(
            message="Animal not found",
            details={"animal_id": 42}
        )
    """
    pass


class EntityAlreadyExistsError(TaurusException):
    """
    Raised when trying to create an entity that already exists.
    
    Maps to HTTP 400 Bad Request (or 409 Conflict).
    
    Example:
        raise EntityAlreadyExistsError(
            message="Animal with this tag already exists",
            details={"tag_id": "JNV-001"}
        )
    """
    pass


class BusinessRuleViolationError(TaurusException):
    """
    Raised when a business rule is violated.
    
    Maps to HTTP 400 Bad Request.
    
    Example:
        raise BusinessRuleViolationError(
            message="Cannot modify archived animal",
            details={"status": "DECEASED", "animal_id": 42}
        )
    """
    pass


class ValidationError(TaurusException):
    """
    Raised when validation fails.
    
    Maps to HTTP 422 Unprocessable Entity.
    
    Example:
        raise ValidationError(
            message="Birth date cannot be in the future",
            details={"birth_date": "2027-01-01"}
        )
    """
    pass


class DatabaseError(TaurusException):
    """
    Raised when a database operation fails.
    
    Maps to HTTP 500 Internal Server Error.
    
    Example:
        raise DatabaseError(
            message="Failed to connect to database",
            details={"error": str(e)}
        )
    """
    pass