"""
AnimalEmbedding database model.

Stores MobileNetV2 feature embeddings extracted from cattle muzzle images.
Each animal can have multiple embeddings (different lighting, angles)
for more robust identification.

DESIGN:
- Multiple embeddings per animal → better accuracy in varied conditions
- Soft limit: max 10 embeddings/animal (configurable)
- Oldest embeddings replaced when limit reached
- is_reference: first/best embedding flagged for display
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Index, String, ForeignKey, Boolean, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class AnimalEmbedding(BaseModel):
    """
    Stored feature embedding for animal identification.

    Each row = one muzzle photo's 1280-dim feature vector.
    Identification queries compare new embeddings against all stored ones.

    Attributes:
        animal_id:       FK → Animal.id
        embedding:       1280-dim float list (JSON array)
        photo_path:      Optional path to saved muzzle photo
        is_reference:    True for the first/best embedding (used in UI)
        source:          How this embedding was created ('registration', 'auto')
        similarity_score: Self-similarity score during registration (quality check)
    """

    __tablename__ = "animal_embeddings"

    # Foreign key to animal
    animal_id: Mapped[int] = mapped_column(
        ForeignKey("animals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Animal this embedding belongs to",
    )

    # The actual embedding vector (1280 floats stored as JSON)
    embedding: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        comment="MobileNetV2 1280-dim L2-normalized embedding vector",
    )

    # Optional reference photo path (stored in MinIO/local)
    photo_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Path to muzzle reference photo",
    )

    # Quality / metadata
    is_reference: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="True for the primary/best embedding shown in UI",
    )

    source: Mapped[str] = mapped_column(
        String(50),
        default="registration",
        nullable=False,
        comment="How this embedding was created: registration | auto_detection",
    )

    # Confidence of this embedding (higher = better quality photo)
    quality_score: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="Quality score 0-1 based on detection confidence and image clarity",
    )

    # Relationship back to animal
    animal: Mapped["Animal"] = relationship(  # type: ignore[name-defined]
        "Animal",
        back_populates="embeddings",
        lazy="select",
    )

    __table_args__ = (
        # Fast lookup: find all embeddings for an animal
        Index("ix_embeddings_animal_reference", "animal_id", "is_reference"),
    )

    def __repr__(self) -> str:
        return (
            f"<AnimalEmbedding(id={self.id}, animal_id={self.animal_id}, "
            f"is_reference={self.is_reference}, source='{self.source}')>"
        )

    def get_embedding_array(self):
        """Convert stored JSON list to numpy array."""
        import numpy as np
        return np.array(self.embedding, dtype=np.float32)

