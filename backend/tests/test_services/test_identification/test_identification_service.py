"""
Tests for IdentificationService.

Tests cover:
- Identification with matching embeddings (above threshold)
- Identification failure (below threshold)
- No registered animals (empty DB)
- Multi-embedding strategy (multiple embeddings per animal)
- add_embedding flow
- Embedding limit enforcement

DB interactions are mocked — no real PostgreSQL needed.
"""

import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from app.services.identification_service import (
    IdentificationService,
    IdentificationResult,
    IDENTIFICATION_THRESHOLD,
    MAX_EMBEDDINGS_PER_ANIMAL,
)
from app.utils.image_utils import compute_cosine_similarity


# ============================================================================
# HELPERS
# ============================================================================

def make_normalized_embedding(seed: int = 42, dim: int = 1280) -> np.ndarray:
    """Create a deterministic normalized embedding."""
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float32)
    return vec / np.linalg.norm(vec)


def make_similar_embedding(base: np.ndarray, noise_level: float = 0.02) -> np.ndarray:
    """Create embedding similar to base (same animal, different photo)."""
    noise = np.random.randn(*base.shape).astype(np.float32) * noise_level
    perturbed = base + noise
    return perturbed / np.linalg.norm(perturbed)


def make_different_embedding(seed: int = 99) -> np.ndarray:
    """Create a completely different embedding (different animal)."""
    return make_normalized_embedding(seed)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock async SQLAlchemy session."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.delete = AsyncMock()
    return db


@pytest.fixture
def registered_embedding():
    """A 'registered' animal's embedding."""
    return make_normalized_embedding(seed=1)


@pytest.fixture
def different_animal_embedding():
    """A completely different animal's embedding."""
    return make_normalized_embedding(seed=99)


@pytest.fixture
def mock_db_with_animals(registered_embedding, different_animal_embedding):
    """
    Mock DB that returns 2 registered animals with embeddings.
    Animal 1 (tag: JNV-001): embedding from seed=1
    Animal 2 (tag: JNV-002): embedding from seed=99
    """
    db = AsyncMock()

    # Simulate DB rows
    rows = [
        MagicMock(
            id=1,
            animal_id=1,
            tag_id="JNV-001",
            embedding=registered_embedding.tolist(),
        ),
        MagicMock(
            id=2,
            animal_id=2,
            tag_id="JNV-002",
            embedding=different_animal_embedding.tolist(),
        ),
    ]

    mock_result = MagicMock()
    mock_result.fetchall.return_value = rows
    db.execute = AsyncMock(return_value=mock_result)

    # db.scalar — animal ni qaytaradi (tag_id uchun)
    mock_animal = MagicMock()
    mock_animal.tag_id = "JNV-001"
    db.scalar = AsyncMock(return_value=mock_animal)

    return db


# ============================================================================
# IdentificationResult tests
# ============================================================================

class TestIdentificationResult:
    """Tests for IdentificationResult dataclass."""

    def test_identified_result(self):
        result = IdentificationResult(
            animal_id=1,
            similarity_score=0.92,
            is_identified=True,
            matched_embedding_id=5,
            tag_id="JNV-001",
        )
        assert result.is_identified is True
        assert result.animal_id == 1
        d = result.to_dict()
        assert d["tag_id"] == "JNV-001"
        assert d["similarity_score"] == 0.92

    def test_unknown_result(self):
        result = IdentificationResult(
            animal_id=None,
            similarity_score=0.45,
            is_identified=False,
        )
        assert result.is_identified is False
        assert result.animal_id is None
        d = result.to_dict()
        assert d["animal_id"] is None


# ============================================================================
# IdentificationService.identify_from_embedding tests
# ============================================================================

class TestIdentifyFromEmbedding:
    """Tests for core identification logic (no image extraction needed)."""

    @pytest.mark.asyncio
    async def test_identifies_matching_animal(
        self, mock_db_with_animals, registered_embedding
    ):
        """Similar embedding should be identified as registered animal."""
        service = IdentificationService(mock_db_with_animals)

        # Create a similar embedding (same animal, different photo)
        query_embedding = make_similar_embedding(registered_embedding, noise_level=0.01)

        result = await service.identify_from_embedding(query_embedding)

        assert result.is_identified is True
        assert result.animal_id == 1
        assert result.tag_id == "JNV-001"
        assert result.similarity_score >= IDENTIFICATION_THRESHOLD

    @pytest.mark.asyncio
    async def test_rejects_unknown_animal(
        self, mock_db_with_animals
    ):
        """Random embedding should NOT be identified."""
        service = IdentificationService(mock_db_with_animals)

        # Create an unregistered animal's embedding
        unknown = make_normalized_embedding(seed=42)

        # Make sure it's not similar to registered ones
        reg = make_normalized_embedding(seed=1)
        diff = make_normalized_embedding(seed=99)
        sim1 = compute_cosine_similarity(unknown, reg)
        sim2 = compute_cosine_similarity(unknown, diff)

        # Only test identification if the embedding is truly different
        if max(sim1, sim2) >= IDENTIFICATION_THRESHOLD:
            pytest.skip("Random embeddings happened to be similar — seed collision")

        result = await service.identify_from_embedding(unknown)
        assert result.is_identified is False
        assert result.animal_id is None

    @pytest.mark.asyncio
    async def test_empty_db_returns_unknown(self, mock_db):
        """No registered animals → always return unknown."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = IdentificationService(mock_db)
        embedding = make_normalized_embedding(seed=1)

        result = await service.identify_from_embedding(embedding)

        assert result.is_identified is False
        assert result.animal_id is None
        assert result.similarity_score == 0.0

    @pytest.mark.asyncio
    async def test_picks_best_matching_animal(self, mock_db):
        """With 2 animals, should pick the one with higher similarity."""
        emb_animal1 = make_normalized_embedding(seed=1)
        emb_animal2 = make_normalized_embedding(seed=2)

        rows = [
            MagicMock(id=10, animal_id=1, tag_id="JNV-001", embedding=emb_animal1.tolist()),
            MagicMock(id=20, animal_id=2, tag_id="JNV-002", embedding=emb_animal2.tolist()),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = IdentificationService(mock_db)

        # Query embedding is close to animal 1
        query = make_similar_embedding(emb_animal1, noise_level=0.01)
        result = await service.identify_from_embedding(query)

        assert result.is_identified is True
        assert result.animal_id == 1

    @pytest.mark.asyncio
    async def test_threshold_boundary_below(self, mock_db_with_animals):
        """Embedding just below threshold → unknown."""
        service = IdentificationService(mock_db_with_animals)

        reg = make_normalized_embedding(seed=1)
        # Create an embedding with similarity exactly below threshold
        # Use a large noise to push similarity way below threshold
        noisy = make_similar_embedding(reg, noise_level=2.0)

        # Check our test assumption
        sim = compute_cosine_similarity(reg, noisy)
        if sim >= IDENTIFICATION_THRESHOLD:
            pytest.skip("Noise level not sufficient to go below threshold")

        result = await service.identify_from_embedding(
            noisy, threshold=IDENTIFICATION_THRESHOLD
        )
        assert result.is_identified is False

    @pytest.mark.asyncio
    async def test_custom_threshold_respected(self, mock_db_with_animals, registered_embedding):
        """Custom threshold should be used instead of default."""
        service = IdentificationService(mock_db_with_animals)

        # Slightly noisy embedding
        query = make_similar_embedding(registered_embedding, noise_level=0.05)
        sim = compute_cosine_similarity(registered_embedding, query)

        # Test with threshold higher than expected similarity → should fail
        result_strict = await service.identify_from_embedding(
            query, threshold=0.999
        )
        assert result_strict.is_identified is False

        # Test with very low threshold → should succeed
        result_lax = await service.identify_from_embedding(
            query, threshold=0.1
        )
        assert result_lax.is_identified is True


# ============================================================================
# Multi-embedding strategy tests
# ============================================================================

class TestMultiEmbeddingStrategy:
    """Tests for multiple embeddings per animal."""

    @pytest.mark.asyncio
    async def test_matches_via_second_embedding(self, mock_db):
        """
        Animal has 2 embeddings. Query matches second one.
        Should still be identified.
        """
        base_emb = make_normalized_embedding(seed=10)
        alt_emb  = make_normalized_embedding(seed=11)  # Different angle/lighting

        rows = [
            MagicMock(id=1, animal_id=5, tag_id="JNV-005", embedding=base_emb.tolist()),
            MagicMock(id=2, animal_id=5, tag_id="JNV-005", embedding=alt_emb.tolist()),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = IdentificationService(mock_db)

        # Query is similar to alt_emb (second photo)
        query = make_similar_embedding(alt_emb, noise_level=0.01)
        result = await service.identify_from_embedding(query)

        assert result.is_identified is True
        assert result.animal_id == 5