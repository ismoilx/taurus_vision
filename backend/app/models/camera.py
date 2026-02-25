"""
Taurus Vision — Camera Database Model

Ferma kameralarini persistent saqlash uchun ORM modeli.

NIMA UCHUN DB DA:
    - Server restart bo'lganda kamera konfiguratsiyalari saqlanib qoladi
    - Bir nechta server instance o'rtasida kameralar sinxronlanadi
    - Audit trail: qachon qo'shilgan, kim tomonidan o'zgartirilgan

RUNTIME HOLAT:
    is_active va fps kabi runtime qiymatlar DB da emas,
    balki CameraManager xotirasida saqlanadi va dinamik olinadi.

DIZAYN:
    camera_id — noyob string identifikator (masalan: "CAM-BARN-01")
    BaseModel.id — ichki integer PK (boshqa tablalar bilan JOIN uchun)
"""

import enum
from typing import Optional

from sqlalchemy import String, Integer, Boolean, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class CameraType(str, enum.Enum):
    """
    Kamera manba turi.

    Hierarchy:
        SIMULATED — development/test uchun, real kamera kerak emas
        USB       — mahalliy USB/webcam
        RTSP      — tarmoq IP kamera
    """
    SIMULATED = "simulated"
    USB       = "usb"
    RTSP      = "rtsp"


class Camera(BaseModel):
    """
    Kamera konfiguratsiyasi — persistent DB yozuvi.

    Runtime holat (is_active, current_fps, frames_captured) bu yerda
    saqlanmaydi — ular CameraManager dan so'ralganda olinadi.
    """

    __tablename__ = "cameras"

    # =========================================================================
    # IDENTITY
    # =========================================================================

    camera_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        comment="Noyob kamera identifikatori, masalan: CAM-BARN-01",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Ko'rsatiladigan nom, masalan: Shimoliy molxona",
    )

    # =========================================================================
    # TYPE & SOURCE
    # =========================================================================

    type: Mapped[CameraType] = mapped_column(
        SQLEnum(CameraType, name="camera_type"),
        nullable=False,
        default=CameraType.SIMULATED,
        comment="Kamera manba turi: simulated | usb | rtsp",
    )

    source: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="RTSP URL (masalan: rtsp://192.168.1.100:554/stream) yoki None",
    )

    device_index: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="USB kamera indeks raqami (0 — birinchi kamera)",
    )

    # =========================================================================
    # PARAMETERS
    # =========================================================================

    fps: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
        comment="Maqsadli kadr tezligi (FPS). Tavsiya: 10–15",
    )

    # =========================================================================
    # STATUS
    # =========================================================================

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="False = kamera o'chirilgan (o'chirilmaydi, faqat deaktiv)",
    )

    # =========================================================================
    # HELPERS
    # =========================================================================

    def __repr__(self) -> str:
        return (
            f"<Camera("
            f"id={self.id}, "
            f"camera_id='{self.camera_id}', "
            f"name='{self.name}', "
            f"type={self.type.value}"
            f")>"
        )