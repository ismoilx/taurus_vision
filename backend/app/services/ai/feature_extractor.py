"""
MobileNetV2 Feature Extractor for Cattle Identification.

Extracts 1280-dimensional embedding vectors from cattle muzzle images.
Used as the backbone for individual animal identification.
"""

import logging
import os
import time
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torchvision.models as models

# ============================================================================
# BUG FIX & CONFIGURATION
# Set PyTorch cache directory before any model loading.
# This resolves PermissionErrors in Docker by routing downloads to our volume.
# ============================================================================
os.environ["TORCH_HOME"] = "/app/ml/models"

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 1280  # MobileNetV2 final feature dimension


class MuzzleFeatureExtractor:
    """
    Extracts feature embeddings from cattle muzzle images.
    
    This class is designed to be instantiated once and reused.
    Thread-safety: Initialization should happen in the main thread.
    Inference is safe for sequential calls. For concurrent API requests,
    use a ThreadPoolExecutor.
    """

    def __init__(self):
        self._model: Optional[nn.Module] = None
        self._is_loaded: bool = False

    def load(self) -> None:
        """
        Load the MobileNetV2 model and prepare it for feature extraction.
        Downloads pretrained weights on the first run.
        """
        if self._is_loaded:
            logger.debug("Feature extractor is already loaded. Skipping.")
            return

        logger.info("Loading MobileNetV2 feature extractor...")
        start_time = time.time()

        try:
            # Load pretrained MobileNetV2
            mobilenet = models.mobilenet_v2(
                weights=models.MobileNet_V2_Weights.IMAGENET1K_V1
            )

            # Strip the classifier head, keep only the backbone and add Global Average Pooling
            self._model = nn.Sequential(
                mobilenet.features,
                nn.AdaptiveAvgPool2d((1, 1)),
                nn.Flatten(),
            )

            # Freeze weights to save memory and compute
            for param in self._model.parameters():
                param.requires_grad = False

            # Set to evaluation mode and move to CPU
            self._model.eval()
            self._model.to("cpu")

            self._is_loaded = True
            elapsed_ms = (time.time() - start_time) * 1000
            
            logger.info(
                f"✓ MobileNetV2 loaded in {elapsed_ms:.0f}ms "
                f"(embedding_dim={EMBEDDING_DIM}, device=CPU)"
            )

        except Exception as e:
            logger.error(f"Failed to load MobileNetV2: {e}", exc_info=True)
            raise RuntimeError(f"Feature extractor load failed: {e}") from e

    def extract(self, preprocessed: np.ndarray) -> np.ndarray:
        """
        Extract L2-normalized embedding from a preprocessed muzzle image.

        Args:
            preprocessed: Float32 array of shape (1, 3, 224, 224).

        Returns:
            L2-normalized embedding of shape (1280,).
        """
        if not self._is_loaded or self._model is None:
            raise RuntimeError("Feature extractor not loaded. Call load() first.")

        expected_shape = (1, 3, 224, 224)
        if preprocessed.shape != expected_shape:
            raise ValueError(
                f"Expected input shape {expected_shape}, got {preprocessed.shape}"
            )

        start_time = time.time()

        # inference_mode is strictly faster and more memory-efficient than no_grad
        with torch.inference_mode():
            tensor = torch.from_numpy(preprocessed)
            features = self._model(tensor)
            embedding = features.squeeze(0).numpy()

        # L2 normalize to project onto the unit hypersphere
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        elapsed_ms = (time.time() - start_time) * 1000
        logger.debug(f"Feature extraction completed in {elapsed_ms:.1f}ms")

        return embedding.astype(np.float32)

    def unload(self) -> None:
        """Release model from memory to free up resources."""
        if self._model is not None:
            del self._model
            self._model = None
            self._is_loaded = False
            logger.info("Feature extractor unloaded successfully.")

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def embedding_dim(self) -> int:
        return EMBEDDING_DIM


# ============================================================================
# Global Instance Management
# ============================================================================

_extractor: Optional[MuzzleFeatureExtractor] = None


def get_feature_extractor() -> MuzzleFeatureExtractor:
    """
    Get the global feature extractor instance.
    Initializes and loads the model if called for the first time.
    """
    global _extractor
    if _extractor is None:
        _extractor = MuzzleFeatureExtractor()
        _extractor.load()
    return _extractor


async def initialize_feature_extractor() -> None:
    """
    App startup hook to initialize the feature extractor.
    """
    logger.info("Initializing feature extractor...")
    try:
        extractor = get_feature_extractor()
        logger.info(f"✓ Feature extractor ready (embedding_dim={extractor.embedding_dim})")
    except Exception as e:
        logger.error(f"✗ Feature extractor init failed: {e}")
        logger.warning("⚠️ Identification will not work until feature extractor is loaded")


async def shutdown_feature_extractor() -> None:
    """
    App shutdown hook to clean up resources.
    """
    global _extractor
    if _extractor is not None:
        _extractor.unload()
        _extractor = None