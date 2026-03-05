"""
AnimalPhoto database model.

Jonivor rasmlari galereyasi.
Har bir jonivorga ko'p rasm bog'lanishi mumkin.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class AnimalPhoto(BaseModel):
    """
    Jonivor rasmi.

    Har bir jonivorga ko'p rasm yuklanishi mumkin.
    profile_image animals jadvalidagi ustun orqali tanlanadi.
    """

    __tablename__ = "animal_photos"

    animal_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("animals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Fayl yo'li (data/images/animals/ ichida)",
    )

    file_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Asl fayl nomi",
    )

    file_size: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Fayl hajmi (bayt)",
    )

    # Relationship
    animal: Mapped["Animal"] = relationship(  # type: ignore[name-defined]
        "Animal",
        back_populates="photos",
    )

    def __repr__(self) -> str:
        return f"<AnimalPhoto(id={self.id}, animal_id={self.animal_id}, file={self.file_name})>"

    @property
    def url(self) -> str:
        """Frontend uchun URL path."""
        return f"/api/v1/animals/photos/file/{self.id}"