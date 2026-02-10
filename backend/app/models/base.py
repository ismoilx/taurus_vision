"""
Base database models and mixins.

This module provides the declarative base for all database models
and common mixins for timestamp tracking and soft deletes.
"""

from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, Boolean, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """
    Base class for all database models.
    
    All models inherit from this class to get SQLAlchemy ORM functionality.
    """
    pass


class TimestampMixin:
    """
    Mixin to add created_at and updated_at timestamps.
    
    Automatically tracks when records are created and modified.
    Use this for audit trail and debugging.
    """
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when record was created",
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Timestamp when record was last updated",
    )


class SoftDeleteMixin:
    """
    Mixin to add soft delete functionality.
    
    Instead of actually deleting records, we mark them as deleted.
    This preserves data for audit and recovery.
    """
    
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Soft delete flag",
    )
    
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when record was soft deleted",
    )


class IDMixin:
    """
    Mixin for standard integer primary key.
    
    Most tables use auto-incrementing integer IDs.
    """
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Primary key",
    )


# Type alias for common model combination
class BaseModel(Base, IDMixin, TimestampMixin):
    """
    Standard base model with ID and timestamps.
    
    Most models should inherit from this unless they need
    custom primary keys or don't need timestamps.
    """
    __abstract__ = True  # This won't create a table
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<{self.__class__.__name__}(id={self.id})>"
    
    def to_dict(self) -> dict[str, Any]:
        """
        Convert model instance to dictionary.
        
        Useful for serialization and debugging.
        
        Returns:
            Dictionary with all column values
        """
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }