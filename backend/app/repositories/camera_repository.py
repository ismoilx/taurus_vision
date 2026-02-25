"""
Taurus Vision — Camera Repository

Kamera konfiguratsiyalari uchun barcha DB operatsiyalari.

Repository pattern: endpoint → service → repository → SQLAlchemy.
Endpoint yoki service hech qachon to'g'ridan-to'g'ri DB so'rovi yozmaydi.
"""

import logging
import re
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.camera import Camera, CameraType
from app.core.exceptions import EntityNotFoundError, EntityAlreadyExistsError

logger = logging.getLogger(__name__)


class CameraRepository:
    """
    Camera modeli uchun barcha CRUD operatsiyalari.

    Args:
        db: Async SQLAlchemy session
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------ #
    # READ                                                                 #
    # ------------------------------------------------------------------ #

    async def get_all(self, only_enabled: bool = False) -> list[Camera]:
        """
        Barcha kameralarni qaytaradi.

        Args:
            only_enabled: True bo'lsa faqat is_enabled=True kameralar

        Returns:
            Camera list, name bo'yicha tartiblangan
        """
        stmt = select(Camera).order_by(Camera.name)
        if only_enabled:
            stmt = stmt.where(Camera.is_enabled.is_(True))
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_camera_id(self, camera_id: str) -> Optional[Camera]:
        """
        camera_id string bo'yicha kamerani topadi.

        Args:
            camera_id: Noyob kamera identifikatori

        Returns:
            Camera yoki None
        """
        result = await self._db.execute(
            select(Camera).where(Camera.camera_id == camera_id)
        )
        return result.scalar_one_or_none()

    async def get_by_camera_id_or_raise(self, camera_id: str) -> Camera:
        """
        camera_id bo'yicha kamera topadi yoki EntityNotFoundError raise qiladi.

        Args:
            camera_id: Noyob kamera identifikatori

        Returns:
            Camera instance

        Raises:
            EntityNotFoundError: Kamera topilmasa
        """
        camera = await self.get_by_camera_id(camera_id)
        if camera is None:
            raise EntityNotFoundError(
                entity="Camera",
                identifier=camera_id,
            )
        return camera

    async def exists_by_camera_id(self, camera_id: str) -> bool:
        """camera_id mavjudligini tekshiradi."""
        count = await self._db.scalar(
            select(func.count(Camera.id)).where(Camera.camera_id == camera_id)
        )
        return (count or 0) > 0

    async def count(self) -> int:
        """Jami kameralar soni."""
        return await self._db.scalar(select(func.count(Camera.id))) or 0

    # ------------------------------------------------------------------ #
    # WRITE                                                                #
    # ------------------------------------------------------------------ #

    async def create(
        self,
        name:         str,
        camera_type:  CameraType,
        source:       Optional[str] = None,
        device_index: Optional[int] = None,
        fps:          int           = 10,
        is_enabled:   bool          = True,
        camera_id:    Optional[str] = None,
    ) -> Camera:
        """
        Yangi kamera konfiguratsiyasini yaratadi.

        camera_id ko'rsatilmasa, name dan avtomatik generatsiya qilinadi.
        Agar generatsiya qilingan camera_id band bo'lsa, raqam sufiks qo'shiladi.

        Args:
            name:         Ko'rsatiladigan nom
            camera_type:  CameraType enum qiymati
            source:       RTSP URL (RTSP uchun)
            device_index: USB device indeksi (USB uchun)
            fps:          Kadr tezligi
            is_enabled:   Faollik holati
            camera_id:    Ixtiyoriy — berilmasa avtomatik generatsiya

        Returns:
            Yaratilgan Camera instance

        Raises:
            EntityAlreadyExistsError: camera_id allaqachon mavjud bo'lsa
        """
        # camera_id generatsiya yoki tekshirish
        if camera_id is None:
            camera_id = await self._generate_unique_camera_id(name)
        else:
            camera_id = camera_id.upper()
            if await self.exists_by_camera_id(camera_id):
                raise EntityAlreadyExistsError(
                    entity="Camera",
                    field="camera_id",
                    value=camera_id,
                )

        camera = Camera(
            camera_id    = camera_id,
            name         = name,
            type         = camera_type,
            source       = source,
            device_index = device_index,
            fps          = fps,
            is_enabled   = is_enabled,
        )

        self._db.add(camera)
        await self._db.flush()
        await self._db.refresh(camera)
        await self._db.commit()

        logger.info(
            "Camera yaratildi",
            extra={"extra_data": {
                "camera_id": camera.camera_id,
                "name":      camera.name,
                "type":      camera.type.value,
            }},
        )
        return camera

    async def update(
        self,
        camera_id:   str,
        name:        Optional[str]        = None,
        source:      Optional[str]        = None,
        device_index: Optional[int]       = None,
        fps:         Optional[int]        = None,
        is_enabled:  Optional[bool]       = None,
    ) -> Camera:
        """
        Kamera konfiguratsiyasini yangilaydi.

        Args:
            camera_id: Yangilanadigan kamera identifikatori
            name:      Yangi nom (ixtiyoriy)
            source:    Yangi RTSP URL (ixtiyoriy)
            fps:       Yangi FPS (ixtiyoriy)
            is_enabled: Yangi holat (ixtiyoriy)

        Returns:
            Yangilangan Camera instance

        Raises:
            EntityNotFoundError: Kamera topilmasa
        """
        camera = await self.get_by_camera_id_or_raise(camera_id)

        if name         is not None: camera.name         = name
        if source       is not None: camera.source       = source
        if device_index is not None: camera.device_index = device_index
        if fps          is not None: camera.fps          = fps
        if is_enabled   is not None: camera.is_enabled   = is_enabled

        await self._db.flush()
        await self._db.refresh(camera)
        await self._db.commit()

        logger.info(
            "Camera yangilandi",
            extra={"extra_data": {"camera_id": camera.camera_id}},
        )
        return camera

    async def delete(self, camera_id: str) -> None:
        """
        Kamerani DB dan o'chiradi.

        Args:
            camera_id: O'chiriladigan kamera identifikatori

        Raises:
            EntityNotFoundError: Kamera topilmasa
        """
        camera = await self.get_by_camera_id_or_raise(camera_id)
        await self._db.delete(camera)
        await self._db.commit()

        logger.info(
            "Camera o'chirildi",
            extra={"extra_data": {"camera_id": camera_id}},
        )

    # ------------------------------------------------------------------ #
    # INTERNAL                                                             #
    # ------------------------------------------------------------------ #

    async def _generate_unique_camera_id(self, name: str) -> str:
        """
        Name dan noyob camera_id generatsiya qiladi.

        Algoritm:
            1. Nomni slug ga aylantiradi: "Shimoliy Molxona" → "SHIMOLIY-MOLXONA"
            2. "CAM-" prefiksi qo'shadi
            3. Agar band bo'lsa, raqam sufiks qo'shadi: "CAM-SHIMOLIY-1"

        Args:
            name: Kamera nomi

        Returns:
            Noyob camera_id string
        """
        # Noyob slug yasash
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip())
        slug = slug.strip("-").upper()[:20]
        base_id = f"CAM-{slug}"

        # Noyobligini tekshirish
        candidate = base_id
        suffix = 1
        while await self.exists_by_camera_id(candidate):
            candidate = f"{base_id}-{suffix}"
            suffix += 1

        return candidate