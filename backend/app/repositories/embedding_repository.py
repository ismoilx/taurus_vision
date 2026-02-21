"""
Embedding Repository — MobileNetV2 muzzle embedding ma'lumotlar qatlami.

JAVOBGARLIK:
    Jonivorlarni identifikatsiya qilish uchun ishlatiladigan
    muzzle embedding vektorlarini saqlash va o'qish.

ARXITEKTURA:
    IdentificationService  →  EmbeddingRepository  →  SQLAlchemy
    RegistrationEndpoint   →  EmbeddingRepository  →  PostgreSQL

DIZAYN QARORLARI:
    - Har jonivor uchun maksimum 10 ta embedding (MAX_EMBEDDINGS_PER_ANIMAL)
    - Limit oshganda eng eskirgan embedding o'chiriladi (FIFO)
    - is_reference: birinchi/eng sifatli embedding UI da ko'rsatiladi
    - JSON formatda saqlanadi (1280-dim float array)
    - Barcha embedding ID lar va vektorlar bitta queryda yuklanadi
      (N+1 muammosidan qochish uchun)
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.animal_embedding import AnimalEmbedding
from app.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)

# Har jonivor uchun maksimum saqlash chegarasi
MAX_EMBEDDINGS_PER_ANIMAL = 10


class EmbeddingRepository:
    """
    Repository for AnimalEmbedding entity database operations.

    All methods are strictly async and fully type-annotated.
    No ML/inference logic — pure DB access layer.

    Args:
        db: AsyncSession injected via FastAPI Depends()

    Example:
        repo = EmbeddingRepository(db)
        embeddings = await repo.get_all_for_animal(animal_id=1)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # CREATE
    # =========================================================================

    async def create(self, embedding: AnimalEmbedding) -> AnimalEmbedding:
        """
        Yangi embedding yozuvini DB ga qo'shish.

        NOTE: Limit tekshiruvi va eski embedding o'chirishni
        IdentificationService / RegistrationEndpoint amalga oshiradi.
        Bu metod faqat saqlaydi.

        Args:
            embedding: To'ldirilgan AnimalEmbedding ORM instance

        Returns:
            Saqlangan AnimalEmbedding (generated id bilan)

        Raises:
            DatabaseError: DB xatosi
        """
        try:
            self.db.add(embedding)
            await self.db.flush()
            await self.db.refresh(embedding)
            logger.debug(
                f"[embedding_repo] Created embedding: "
                f"animal_id={embedding.animal_id} "
                f"source={embedding.source} "
                f"quality={embedding.quality_score}"
            )
            return embedding
        except Exception as exc:
            logger.error(f"[embedding_repo] create failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="Embedding yaratishda xato",
                details={"error": str(exc)},
            ) from exc

    async def add_with_limit_check(
        self,
        animal_id: int,
        embedding_vector: list[float],
        source: str = "registration",
        quality_score: Optional[float] = None,
        photo_path: Optional[str] = None,
        is_reference: bool = False,
    ) -> AnimalEmbedding:
        """
        Embedding qo'shish — limit oshsa eng eskisini o'chirish bilan.

        Jonivor uchun maksimum MAX_EMBEDDINGS_PER_ANIMAL ta embedding
        bo'lishi mumkin. Bu chegaraga yetilsa eng eski embedding
        avtomatik o'chiriladi (FIFO).

        Args:
            animal_id:        Jonivor ID
            embedding_vector: 1280-dim float ro'yxat (L2-normalized)
            source:           "registration" | "auto_detection"
            quality_score:    Sifat ko'rsatkichi 0.0-1.0 (ixtiyoriy)
            photo_path:       Rasmga yo'l (ixtiyoriy)
            is_reference:     True = UI da asosiy embedding sifatida ko'rsatish

        Returns:
            Yangi AnimalEmbedding

        Raises:
            DatabaseError: DB xatosi
        """
        try:
            # Joriy soni
            count = await self.count_for_animal(animal_id)

            if count >= MAX_EMBEDDINGS_PER_ANIMAL:
                # Eng eskisini o'chirish (created_at bo'yicha)
                await self._delete_oldest(animal_id)
                logger.debug(
                    f"[embedding_repo] Limit reached ({MAX_EMBEDDINGS_PER_ANIMAL}) "
                    f"for animal_id={animal_id}, deleted oldest"
                )

            # Agar is_reference=True bo'lsa, boshqalarni False qilish
            if is_reference:
                await self._clear_reference_flag(animal_id)

            # Yangi embedding yaratish
            embedding = AnimalEmbedding(
                animal_id=animal_id,
                embedding=embedding_vector,
                source=source,
                quality_score=quality_score,
                photo_path=photo_path,
                is_reference=is_reference,
            )
            return await self.create(embedding)

        except DatabaseError:
            raise
        except Exception as exc:
            logger.error(
                f"[embedding_repo] add_with_limit_check failed: {exc}",
                exc_info=True,
            )
            raise DatabaseError(
                message="Embedding qo'shishda xato",
                details={"animal_id": animal_id, "error": str(exc)},
            ) from exc

    # =========================================================================
    # READ — single
    # =========================================================================

    async def get_by_id(self, embedding_id: int) -> Optional[AnimalEmbedding]:
        """
        Primary key orqali embedding olish.

        Args:
            embedding_id: AnimalEmbedding.id

        Returns:
            AnimalEmbedding yoki None
        """
        try:
            result = await self.db.execute(
                select(AnimalEmbedding).where(AnimalEmbedding.id == embedding_id)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(f"[embedding_repo] get_by_id({embedding_id}) failed: {exc}")
            raise DatabaseError(
                message=f"Embedding olishda xato (id={embedding_id})",
                details={"error": str(exc)},
            ) from exc

    async def get_reference_for_animal(
        self, animal_id: int
    ) -> Optional[AnimalEmbedding]:
        """
        Jonivorning asosiy (reference) embeddingini olish.

        UI da jonivor muzzle rasmini ko'rsatish uchun.

        Args:
            animal_id: Jonivor ID

        Returns:
            Reference AnimalEmbedding yoki None
        """
        try:
            result = await self.db.execute(
                select(AnimalEmbedding).where(
                    and_(
                        AnimalEmbedding.animal_id == animal_id,
                        AnimalEmbedding.is_reference == True,  # noqa: E712
                    )
                ).limit(1)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(
                f"[embedding_repo] get_reference_for_animal({animal_id}) failed: {exc}"
            )
            raise DatabaseError(
                message="Reference embedding olishda xato",
                details={"animal_id": animal_id, "error": str(exc)},
            ) from exc

    # =========================================================================
    # READ — collections
    # =========================================================================

    async def get_all_for_animal(
        self, animal_id: int
    ) -> list[AnimalEmbedding]:
        """
        Jonivorning barcha embeddinglarini olish.

        Identification pipeline uchun — yangi deteksiya bilan
        barcha stored embeddinglar o'rtasida cosine similarity hisoblash.

        Args:
            animal_id: Jonivor ID

        Returns:
            AnimalEmbedding ro'yxati (yangi → eski tartibda)
        """
        try:
            result = await self.db.execute(
                select(AnimalEmbedding)
                .where(AnimalEmbedding.animal_id == animal_id)
                .order_by(AnimalEmbedding.created_at.desc())
            )
            return list(result.scalars().all())
        except Exception as exc:
            logger.error(
                f"[embedding_repo] get_all_for_animal({animal_id}) failed: {exc}"
            )
            raise DatabaseError(
                message="Embeddinglarni olishda xato",
                details={"animal_id": animal_id, "error": str(exc)},
            ) from exc

    async def get_all_active_embeddings(
        self,
    ) -> dict[int, list[list[float]]]:
        """
        Barcha jonivorlarning embeddinglarini bir queryda yuklash.

        Identification pipeline uchun kritik metod.
        N+1 muammosidan qochish uchun bitta queryda hammasi yuklanadi.

        Returns:
            {animal_id: [[embedding_vector], ...], ...}

        Performance:
            ~10ms uchun 50 jonivor, 500 ta embedding
        """
        try:
            result = await self.db.execute(
                select(
                    AnimalEmbedding.animal_id,
                    AnimalEmbedding.embedding,
                    AnimalEmbedding.quality_score,
                ).order_by(
                    AnimalEmbedding.animal_id,
                    # Eng sifatli embeddinglar birinchi kelsin
                    AnimalEmbedding.quality_score.desc().nullslast(),
                )
            )
            rows = result.fetchall()

            # animal_id → embedding vektorlar ro'yxati
            embedding_map: dict[int, list[list[float]]] = {}
            for row in rows:
                # Testdagi Mock'lar va SQLAlchemy'da barqaror ishlashi uchun attribute orqali o'qish:
                animal_id = row.animal_id
                embedding_vector = row.embedding
                
                if animal_id not in embedding_map:
                    embedding_map[animal_id] = []
                embedding_map[animal_id].append(embedding_vector)

            logger.debug(
                f"[embedding_repo] Loaded embeddings for "
                f"{len(embedding_map)} animals ({len(rows)} total)"
            )
            return embedding_map

        except Exception as exc:
            logger.error(
                f"[embedding_repo] get_all_active_embeddings failed: {exc}",
                exc_info=True,
            )
            raise DatabaseError(
                message="Barcha embeddinglarni yuklashda xato",
                details={"error": str(exc)},
            ) from exc

    # =========================================================================
    # COUNT / EXISTS
    # =========================================================================

    async def count_for_animal(self, animal_id: int) -> int:
        """
        Jonivorning embedding soni.

        Args:
            animal_id: Jonivor ID

        Returns:
            Embedding soni
        """
        try:
            result = await self.db.execute(
                select(func.count(AnimalEmbedding.id)).where(
                    AnimalEmbedding.animal_id == animal_id
                )
            )
            return result.scalar_one() or 0
        except Exception as exc:
            raise DatabaseError(
                message="Embedding sanoq xatosi",
                details={"animal_id": animal_id, "error": str(exc)},
            ) from exc

    async def has_embeddings(self, animal_id: int) -> bool:
        """
        Jonivorning kamida bitta embeddingga ega ekanligini tekshirish.

        Identification pipeline boshlashdan oldin tekshiruv uchun.

        Args:
            animal_id: Jonivor ID

        Returns:
            True — embedding bor, False — yo'q
        """
        count = await self.count_for_animal(animal_id)
        return count > 0

    # =========================================================================
    # DELETE
    # =========================================================================

    async def delete_by_id(self, embedding_id: int) -> bool:
        """
        ID bo'yicha embedding o'chirish.

        Args:
            embedding_id: AnimalEmbedding.id

        Returns:
            True — o'chirildi, False — topilmadi
        """
        try:
            existing = await self.get_by_id(embedding_id)
            if not existing:
                return False

            await self.db.delete(existing)
            await self.db.flush()
            logger.debug(f"[embedding_repo] Deleted embedding id={embedding_id}")
            return True
        except DatabaseError:
            raise
        except Exception as exc:
            logger.error(
                f"[embedding_repo] delete_by_id({embedding_id}) failed: {exc}"
            )
            raise DatabaseError(
                message="Embedding o'chirishda xato",
                details={"embedding_id": embedding_id, "error": str(exc)},
            ) from exc

    async def delete_all_for_animal(self, animal_id: int) -> int:
        """
        Jonivorning barcha embeddinglarini o'chirish.

        Jonivor o'chirilganda yoki qayta ro'yxatdan o'tkazilganda.

        Args:
            animal_id: Jonivor ID

        Returns:
            O'chirilgan embedding soni
        """
        try:
            result = await self.db.execute(
                delete(AnimalEmbedding).where(
                    AnimalEmbedding.animal_id == animal_id
                )
            )
            await self.db.flush()
            deleted_count = result.rowcount
            logger.info(
                f"[embedding_repo] Deleted {deleted_count} embeddings "
                f"for animal_id={animal_id}"
            )
            return deleted_count
        except Exception as exc:
            logger.error(
                f"[embedding_repo] delete_all_for_animal({animal_id}) failed: {exc}"
            )
            raise DatabaseError(
                message="Embeddinglarni o'chirishda xato",
                details={"animal_id": animal_id, "error": str(exc)},
            ) from exc

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    async def _delete_oldest(self, animal_id: int) -> None:
        """
        Jonivorning eng eski embeddingini o'chirish.

        FIFO limit logikasi uchun (limit_check da ishlatiladi).

        Args:
            animal_id: Jonivor ID

        Raises:
            DatabaseError: DB xatosi
        """
        try:
            # Eng eski (created_at min) embedding ID sini topish
            result = await self.db.execute(
                select(AnimalEmbedding.id)
                .where(AnimalEmbedding.animal_id == animal_id)
                .order_by(AnimalEmbedding.created_at.asc())
                .limit(1)
            )
            oldest_id = result.scalar_one_or_none()

            if oldest_id is not None:
                await self.db.execute(
                    delete(AnimalEmbedding).where(AnimalEmbedding.id == oldest_id)
                )
                await self.db.flush()
                logger.debug(
                    f"[embedding_repo] Deleted oldest embedding "
                    f"id={oldest_id} for animal_id={animal_id}"
                )
        except Exception as exc:
            raise DatabaseError(
                message="Eng eski embeddingni o'chirishda xato",
                details={"animal_id": animal_id, "error": str(exc)},
            ) from exc

    async def _clear_reference_flag(self, animal_id: int) -> None:
        """
        Jonivorning barcha embeddinglaridan is_reference flagini olib tashlash.

        Yangi reference qo'shilishidan oldin chaqiriladi.

        Args:
            animal_id: Jonivor ID
        """
        try:
            result = await self.db.execute(
                select(AnimalEmbedding).where(
                    and_(
                        AnimalEmbedding.animal_id == animal_id,
                        AnimalEmbedding.is_reference == True,  # noqa: E712
                    )
                )
            )
            embeddings = result.scalars().all()

            for emb in embeddings:
                emb.is_reference = False

            if embeddings:
                await self.db.flush()
                logger.debug(
                    f"[embedding_repo] Cleared reference flag from "
                    f"{len(embeddings)} embeddings for animal_id={animal_id}"
                )
        except Exception as exc:
            raise DatabaseError(
                message="Reference flag tozalashda xato",
                details={"animal_id": animal_id, "error": str(exc)},
            ) from exc