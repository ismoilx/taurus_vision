"""
Tests for image_utils.py preprocessing utilities.

Tests cover:
- Muzzle region extraction from bounding boxes
- Preprocessing pipeline for MobileNetV2
- Cosine similarity computation
- Edge cases (too small crops, wrong formats)
"""

import numpy as np
import pytest
import cv2

from app.utils.image_utils import (
    extract_muzzle_region,
    preprocess_for_mobilenet,
    compute_cosine_similarity,
    decode_frame_bytes,
    encode_frame_to_bytes,
    MOBILENET_INPUT_SIZE,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_frame():
    """Create a 640x480 BGR test frame."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Add some visual content (gradient)
    for i in range(480):
        frame[i, :] = [i % 256, (i * 2) % 256, (i * 3) % 256]
    return frame


@pytest.fixture
def small_frame():
    """Small 100x100 frame for edge case tests."""
    return np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)


@pytest.fixture
def sample_embedding():
    """Random normalized embedding vector."""
    vec = np.random.randn(1280).astype(np.float32)
    return vec / np.linalg.norm(vec)


# ============================================================================
# extract_muzzle_region tests
# ============================================================================

class TestExtractMuzzleRegion:
    """Tests for muzzle crop extraction."""

    def test_basic_extraction_returns_array(self, sample_frame):
        """Normal input should return a non-None numpy array."""
        crop = extract_muzzle_region(
            frame=sample_frame,
            bbox_x=0.5,   # center
            bbox_y=0.5,
            bbox_w=0.4,
            bbox_h=0.6,
            normalized=True,
        )
        assert crop is not None
        assert isinstance(crop, np.ndarray)
        assert crop.ndim == 3
        assert crop.shape[2] == 3  # BGR channels

    def test_normalized_coordinates(self, sample_frame):
        """Normalized [0,1] coordinates should work correctly."""
        crop = extract_muzzle_region(
            sample_frame, 0.5, 0.7, 0.3, 0.5, normalized=True
        )
        assert crop is not None
        assert crop.size > 0

    def test_absolute_coordinates(self, sample_frame):
        """Absolute pixel coordinates should work correctly."""
        h, w = sample_frame.shape[:2]
        crop = extract_muzzle_region(
            sample_frame,
            bbox_x=w // 2,
            bbox_y=h // 2,
            bbox_w=w // 3,
            bbox_h=h // 2,
            normalized=False,
        )
        assert crop is not None

    def test_too_small_bbox_returns_none(self, sample_frame):
        """Bounding box too small for muzzle crop → None."""
        crop = extract_muzzle_region(
            sample_frame,
            bbox_x=0.5,
            bbox_y=0.5,
            bbox_w=0.01,   # Very small
            bbox_h=0.01,
            normalized=True,
        )
        assert crop is None

    def test_edge_bbox_clamped(self, sample_frame):
        """Bbox at image edge should be clamped, not raise error."""
        crop = extract_muzzle_region(
            sample_frame,
            bbox_x=0.05,  # Near left edge
            bbox_y=0.95,  # Near bottom
            bbox_w=0.2,
            bbox_h=0.15,
            normalized=True,
        )
        # May return None if too small after clamping, but must not raise
        if crop is not None:
            assert crop.ndim == 3

    def test_muzzle_is_bottom_portion(self, sample_frame):
        """Muzzle crop should come from lower portion of bounding box."""
        # Create frame with distinct colors in top vs bottom halves
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:240, :] = [0, 0, 255]    # Blue top half
        frame[240:, :] = [0, 255, 0]    # Green bottom half

        crop = extract_muzzle_region(
            frame, 0.5, 0.5, 0.8, 0.8, normalized=True
        )
        assert crop is not None

        # Muzzle should be primarily from bottom (green) portion
        # Mean blue channel should be lower than mean green channel
        mean_blue  = crop[:, :, 0].mean()
        mean_green = crop[:, :, 1].mean()
        assert mean_green > mean_blue, (
            "Muzzle should be from bottom of bbox (green area)"
        )


# ============================================================================
# preprocess_for_mobilenet tests
# ============================================================================

class TestPreprocessForMobilenet:
    """Tests for MobileNetV2 preprocessing pipeline."""

    def test_output_shape(self, sample_frame):
        """Output should be (1, 3, 224, 224)."""
        result = preprocess_for_mobilenet(sample_frame)
        assert result.shape == (1, 3, 224, 224)

    def test_output_dtype(self, sample_frame):
        """Output should be float32."""
        result = preprocess_for_mobilenet(sample_frame)
        assert result.dtype == np.float32

    def test_output_range(self, sample_frame):
        """Output values should be normalized (not raw 0-255)."""
        result = preprocess_for_mobilenet(sample_frame)
        # After ImageNet normalization, values should be roughly in [-3, 3]
        assert result.min() > -10
        assert result.max() < 10
        # Should NOT be in [0, 255] range
        assert result.max() < 10

    def test_grayscale_input(self):
        """Grayscale input should be converted to 3-channel."""
        gray = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        result = preprocess_for_mobilenet(gray)
        assert result.shape == (1, 3, 224, 224)

    def test_small_image_resized(self):
        """Small input should be resized to 224x224."""
        small = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
        result = preprocess_for_mobilenet(small)
        assert result.shape == (1, 3, 224, 224)

    def test_large_image_resized(self):
        """Large input should be downsampled to 224x224."""
        large = np.random.randint(0, 255, (1920, 1080, 3), dtype=np.uint8)
        result = preprocess_for_mobilenet(large)
        assert result.shape == (1, 3, 224, 224)

    def test_empty_image_raises(self):
        """Empty image should raise ValueError."""
        empty = np.array([])
        with pytest.raises((ValueError, Exception)):
            preprocess_for_mobilenet(empty)

    def test_custom_target_size(self, sample_frame):
        """Custom target size should be respected."""
        result = preprocess_for_mobilenet(sample_frame, target_size=(128, 128))
        assert result.shape == (1, 3, 128, 128)


# ============================================================================
# compute_cosine_similarity tests
# ============================================================================

class TestCosineSimilarity:
    """Tests for cosine similarity computation."""

    def test_identical_vectors_score_one(self):
        """Identical vectors should have similarity = 1.0."""
        vec = np.random.randn(1280).astype(np.float32)
        vec /= np.linalg.norm(vec)
        sim = compute_cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 1e-5

    def test_opposite_vectors_score_negative_one(self):
        """Opposite vectors should have similarity ≈ -1.0."""
        vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        neg = np.array([-1.0, 0.0, 0.0], dtype=np.float32)
        sim = compute_cosine_similarity(vec, neg)
        assert abs(sim - (-1.0)) < 1e-5

    def test_orthogonal_vectors_score_zero(self):
        """Perpendicular vectors should have similarity ≈ 0.0."""
        vec_a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec_b = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        sim = compute_cosine_similarity(vec_a, vec_b)
        assert abs(sim) < 1e-5

    def test_zero_vector_returns_zero(self):
        """Zero vector should return 0.0 (no division by zero)."""
        zero = np.zeros(1280, dtype=np.float32)
        vec = np.random.randn(1280).astype(np.float32)
        sim = compute_cosine_similarity(zero, vec)
        assert sim == 0.0

    def test_score_range(self, sample_embedding):
        """Score should always be in [-1, 1]."""
        other = np.random.randn(1280).astype(np.float32)
        other /= np.linalg.norm(other)
        sim = compute_cosine_similarity(sample_embedding, other)
        assert -1.0 <= sim <= 1.0

    def test_symmetric(self, sample_embedding):
        """Cosine similarity should be symmetric: sim(a,b) == sim(b,a)."""
        other = np.random.randn(1280).astype(np.float32)
        sim_ab = compute_cosine_similarity(sample_embedding, other)
        sim_ba = compute_cosine_similarity(other, sample_embedding)
        assert abs(sim_ab - sim_ba) < 1e-6

    def test_similar_embeddings_high_score(self, sample_embedding):
        """Slightly perturbed embedding should have high similarity."""
        noise = np.random.randn(1280).astype(np.float32) * 0.05
        perturbed = sample_embedding + noise
        sim = compute_cosine_similarity(sample_embedding, perturbed)
        assert sim > 0.90, f"Expected high similarity, got {sim:.3f}"

    def test_random_embeddings_lower_score(self, sample_embedding):
        """Completely random embedding should have lower similarity."""
        random_vec = np.random.randn(1280).astype(np.float32)
        sim = compute_cosine_similarity(sample_embedding, random_vec)
        # For 1280-dim random vectors, expected similarity ≈ 0 ± small noise
        assert abs(sim) < 0.2, f"Expected low similarity, got {sim:.3f}"


# ============================================================================
# encode/decode tests
# ============================================================================

class TestImageEncoding:
    """Tests for image byte encoding/decoding."""

    def test_encode_decode_roundtrip(self, sample_frame):
        """Encode to bytes and decode back should give similar image."""
        encoded = encode_frame_to_bytes(sample_frame)
        assert isinstance(encoded, bytes)
        assert len(encoded) > 0

        decoded = decode_frame_bytes(encoded)
        assert decoded is not None
        assert decoded.shape == sample_frame.shape

    def test_decode_invalid_bytes_returns_none(self):
        """Invalid bytes should return None, not raise."""
        result = decode_frame_bytes(b"not_an_image_xxx")
        assert result is None

    def test_decode_empty_bytes_returns_none(self):
        """Empty bytes should return None."""
        result = decode_frame_bytes(b"")
        assert result is None
