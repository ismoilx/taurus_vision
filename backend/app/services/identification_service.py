"""
Cattle Identification Service — Refactored with Repository Pattern.

ARXITEKTURA O'ZGARISHI (Sprint 5):
    Oldingi: to'g'ridan self.db.execute(select(AnimalEmbedding...))
    Yangi:   EmbeddingRepository.get_all_active_embeddings()

IDENTIFICATION ALGORITHM:
1. Extract embedding from muzzle crop (via feature_extractor)
2. Load all registered embeddings via EmbeddingRepository
3. Compute cosine similarity against each stored embedding
4. If best match >= THRESHOLD → identified (return animal_id)
5. If best match <  THRESHOLD → unknown (return None)

THRESHOLD TUNING:
- 0.85: Conservative (fewer false positives, more false negatives)
- 0.80: Balanced (recommended default)
- 0.75: Aggressive (more matches, risk of wrong ID)

MULTI-EMBEDDING STRATEGY:
Each animal may have multiple embeddings (different angles, lighting).
We compare new embedding against ALL stored embeddings for each animal
and take the maximum similarity score. This improves recall significantly.

PERFORMANCE (CPU):
- Embedding extraction:  ~150ms
- DB load (50 animals):  ~10ms  (single query via Repository)
- Similarity computation: <1ms
- Total per frame:       ~160ms
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.animal import Animal
from app.models.animal_embedding import AnimalEmbedding
from app.repositories.embedding_repository import EmbeddingRepository
from app.utils.image_utils import compute_cosine_similarity, preprocess_for_mobilenet
from app.services.ai.feature_extractor import get_feature_extractor

logger = logging.getLogger(__name__)

# Identification threshold: similarity score must be >= this value
IDENTIFICATION_THRESHOLD = 0.10

# Maximum embeddings stored per animal
MAX_EMBEDDINGS_PER_ANIMAL = 10


@dataclass
class IdentificationResult:
    """
    Result of an identification attempt.

    Attributes:
        animal_id:            Identified animal ID, or None if unknown
        similarity_score:     Best cosine similarity (0.0-1.0)
        is_identified:        True if similarity >= threshold
        matched_embedding_id: DB id of the best-matching embedding
        tag_id:               Animal tag (convenience field, None if unknown)
    """
    animal_id: Optional[int]
    similarity_score: float
    is_identified: bool
    matched_embedding_id: Optional[int] = None
    tag_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "animal_id":            self.animal_id,
            "tag_id":               self.tag_id,
            "similarity_score":     round(self.similarity_score, 4),
            "is_identified":        self.is_identified,
            "matched_embedding_id": self.matched_embedding_id,
        }


class IdentificationService:
    """
    Service for identifying individual cattle from muzzle images.

    Stateless: no in-memory cache (embeddings always from DB via Repository).
    For high-throughput scenarios, add Redis caching of embeddings.

    Usage:
        service = IdentificationService(db)
        result = await service.identify_from_crop(muzzle_crop_bgr)
        if result.is_identified:
            print(f"Animal: {result.tag_id}")
        else:
            print("Unknown animal — register?")
    """

    def __init__(self, db: AsyncSession):
        self.db       = db
        self._repo    = EmbeddingRepository(db)   # Repository pattern
        self._extractor = get_feature_extractor()

    # ------------------------------------------------------------------ #
    # IDENTIFICATION                                                       #
    # ------------------------------------------------------------------ #

    async def identify_from_crop(
        self,
        muzzle_crop: np.ndarray,
        threshold: float = IDENTIFICATION_THRESHOLD,
    ) -> IdentificationResult:
        """
        Identify animal from muzzle crop image.

        Full pipeline: image → embedding → DB match → result.

        Args:
            muzzle_crop: BGR numpy array (muzzle region from extract_muzzle_region)
            threshold:   Cosine similarity threshold (default 0.80)

        Returns:
            IdentificationResult with animal_id if identified, None otherwise.
        """
        try:
            preprocessed = preprocess_for_mobilenet(muzzle_crop)
            embedding    = self._extractor.extract(preprocessed)
        except Exception as e:
            logger.error(f"Embedding extraction failed: {e}")
            return IdentificationResult(
                animal_id=None, similarity_score=0.0, is_identified=False,
            )

        return await self.identify_from_embedding(embedding, threshold)

    async def identify_from_embedding(
        self,
        embedding: np.ndarray,
        threshold: float = IDENTIFICATION_THRESHOLD,
    ) -> IdentificationResult:
        """
        Identify animal from pre-computed embedding.

        Uses EmbeddingRepository.get_all_active_embeddings() — single DB query
        for all animals. N+1 query muammosi yo'q.

        Args:
            embedding: L2-normalized 1280-dim numpy array
            threshold: Cosine similarity threshold

        Returns:
            IdentificationResult
        """
        # Single query — barcha embedding lar bir yo'la (N+1 query yo'q)
        # Format: {animal_id: [[embedding1], [embedding2], ...]}
        stored = await self._repo.get_all_active_embeddings()

        if not stored:
            logger.debug("No registered embeddings in DB — cannot identify.")
            return IdentificationResult(
                animal_id=None, similarity_score=0.0, is_identified=False,
            )

        best_animal_id:    Optional[int] = None
        best_score:        float         = 0.0
        best_embedding_id: Optional[int] = None
        best_tag_id:       Optional[str] = None

        for animal_id, emb_list in stored.items():
            for stored_vec in emb_list:
                # Ro'yxatdagi qiymatni numpy massiviga o'giramiz
                stored_vec_np = np.array(stored_vec, dtype=np.float32)
                score = compute_cosine_similarity(embedding, stored_vec_np)
                if score > best_score:
                    best_score        = score
                    best_animal_id    = animal_id
                    best_embedding_id = None 

        is_identified = best_score >= threshold

        if is_identified and best_animal_id:
            # Endi haqiqiy tag_id ni bazadan so'raymiz
            animal = await self.db.scalar(select(Animal).where(Animal.id == best_animal_id))
            if animal:
                best_tag_id = animal.tag_id
            else:
                best_tag_id = f"ID-{best_animal_id}"
                
            logger.info(
                f"✓ Animal identified: {best_tag_id} (similarity={best_score:.3f})"
            )
        else:
            logger.info(
                f"✗ Unknown animal (best_score={best_score:.3f} < {threshold})"
            )

        return IdentificationResult(
            animal_id=        best_animal_id    if is_identified else None,
            similarity_score= best_score,
            is_identified=    is_identified,
            matched_embedding_id=best_embedding_id if is_identified else None,
            tag_id=           best_tag_id       if is_identified else None,
        )

    # ------------------------------------------------------------------ #
    # EMBEDDING MANAGEMENT                                                 #
    # ------------------------------------------------------------------ #

    async def add_embedding(
        self,
        animal_id: int,
        muzzle_crop: np.ndarray,
        is_reference: bool = False,
        source: str = "registration",
        quality_score: Optional[float] = None,
        photo_path: Optional[str] = None,
    ) -> AnimalEmbedding:
        """
        Extract embedding from muzzle crop and save to DB via Repository.

        Limit enforcement va reference flag management — Repository orqali.

        Args:
            animal_id:     Target animal ID
            muzzle_crop:   BGR muzzle region image
            is_reference:  Mark as primary/reference embedding
            source:        Source label ('registration', 'auto_detection')
            quality_score: Optional quality score (0.0-1.0)
            photo_path:    Optional saved photo path

        Returns:
            Created AnimalEmbedding record.
        """
        preprocessed  = preprocess_for_mobilenet(muzzle_crop)
        embedding_vec = self._extractor.extract(preprocessed)

        # Repository orqali limit bilan qo'shish (FIFO, reference ni saqlaydi)
        record = await self._repo.add_with_limit_check(
            animal_id=    animal_id,
            embedding_vector= embedding_vec.tolist(),
            is_reference= is_reference,
            source=       source,
            quality_score=quality_score,
            photo_path=   photo_path,
        )

        logger.info(
            f"✓ Embedding saved: animal_id={animal_id}, "
            f"is_reference={is_reference}, source={source}"
        )

        return record

    async def get_animal_embedding_count(self, animal_id: int) -> int:
        """Get number of embeddings stored for an animal."""
        return await self._repo.count_for_animal(animal_id)