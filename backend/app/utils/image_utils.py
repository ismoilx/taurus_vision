"""
Image Preprocessing Utilities.

Provides image manipulation functions used across the AI pipeline:
- Muzzle region extraction from YOLO bounding boxes
- Image normalization for MobileNetV2 input
- Frame format conversions

MUZZLE REGION LOGIC:
Cattle muzzle is located in the lower-center portion of the bounding box.
Based on empirical bovine anatomy:
  - Vertical: bottom 45% of bounding box
  - Horizontal: center 60% of bounding box

This heuristic works for frontal/semi-frontal camera angles.
For side-view cameras, identification accuracy will be lower.
"""

import logging
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# MobileNetV2 expected input
MOBILENET_INPUT_SIZE = (224, 224)

# ImageNet normalization constants (used by torchvision pretrained models)
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# Muzzle crop ratios relative to bounding box
MUZZLE_TOP_RATIO    = 0.55   # Start at 55% from top of bbox
MUZZLE_BOTTOM_RATIO = 1.00   # End at bottom of bbox
MUZZLE_LEFT_RATIO   = 0.20   # Start at 20% from left
MUZZLE_RIGHT_RATIO  = 0.80   # End at 80% from left

# Minimum crop size to avoid degenerate inputs
MIN_CROP_SIZE = 32  # pixels


def extract_muzzle_region(
    frame: np.ndarray,
    bbox_x: float,
    bbox_y: float,
    bbox_w: float,
    bbox_h: float,
    normalized: bool = True,
    padding: float = 0.05,
) -> Optional[np.ndarray]:
    """
    Extract cattle muzzle region from frame using YOLO bounding box.

    The muzzle (nose/mouth area) is the most distinctive feature for
    individual cattle identification, similar to a human fingerprint.

    Args:
        frame:      BGR image as numpy array (H, W, 3)
        bbox_x:     Bounding box center X
        bbox_y:     Bounding box center Y
        bbox_w:     Bounding box width
        bbox_h:     Bounding box height
        normalized: If True, coordinates are in [0,1] range.
                    If False, coordinates are absolute pixels.
        padding:    Extra padding ratio around muzzle crop (default 5%)

    Returns:
        Cropped muzzle region as BGR numpy array, or None if crop invalid.

    Example:
        >>> muzzle = extract_muzzle_region(frame, 0.5, 0.6, 0.3, 0.4)
        >>> # muzzle is ready for feature_extractor input
    """
    img_h, img_w = frame.shape[:2]

    # Convert normalized → absolute coordinates
    if normalized:
        cx = bbox_x * img_w
        cy = bbox_y * img_h
        w  = bbox_w * img_w
        h  = bbox_h * img_h
    else:
        cx, cy, w, h = bbox_x, bbox_y, bbox_w, bbox_h

    # Full bounding box corners
    x1 = cx - w / 2
    y1 = cy - h / 2
    x2 = cx + w / 2
    y2 = cy + h / 2

    # Apply muzzle ratios within bounding box
    muzzle_x1 = x1 + w * MUZZLE_LEFT_RATIO
    muzzle_x2 = x1 + w * MUZZLE_RIGHT_RATIO
    muzzle_y1 = y1 + h * MUZZLE_TOP_RATIO
    muzzle_y2 = y1 + h * MUZZLE_BOTTOM_RATIO

    # Apply padding
    pad_x = (muzzle_x2 - muzzle_x1) * padding
    pad_y = (muzzle_y2 - muzzle_y1) * padding
    muzzle_x1 -= pad_x
    muzzle_x2 += pad_x
    muzzle_y1 -= pad_y
    muzzle_y2 += pad_y

    # Clamp to image boundaries
    crop_x1 = max(0, int(muzzle_x1))
    crop_y1 = max(0, int(muzzle_y1))
    crop_x2 = min(img_w, int(muzzle_x2))
    crop_y2 = min(img_h, int(muzzle_y2))

    # Validate crop dimensions
    crop_w = crop_x2 - crop_x1
    crop_h = crop_y2 - crop_y1

    if crop_w < MIN_CROP_SIZE or crop_h < MIN_CROP_SIZE:
        logger.warning(
            f"Muzzle crop too small: {crop_w}x{crop_h}px "
            f"(min: {MIN_CROP_SIZE}px). Skipping identification."
        )
        return None

    cropped = frame[crop_y1:crop_y2, crop_x1:crop_x2]

    if cropped.size == 0:
        logger.warning("Empty muzzle crop. Skipping identification.")
        return None

    logger.debug(
        f"Muzzle crop: ({crop_x1},{crop_y1}) → ({crop_x2},{crop_y2}) "
        f"= {crop_w}x{crop_h}px"
    )

    return cropped


def preprocess_for_mobilenet(
    image: np.ndarray,
    target_size: Tuple[int, int] = MOBILENET_INPUT_SIZE,
) -> np.ndarray:
    """
    Preprocess image for MobileNetV2 inference.

    Pipeline:
    1. Resize to 224x224 (MobileNetV2 input)
    2. BGR → RGB conversion
    3. Normalize to [0,1]
    4. Apply ImageNet mean/std normalization
    5. Add batch dimension → (1, 3, H, W) CHW format for PyTorch

    Args:
        image:       BGR numpy array (any size)
        target_size: Target (width, height), default (224, 224)

    Returns:
        Float32 numpy array of shape (1, 3, H, W), normalized.

    Raises:
        ValueError: If image is empty or has wrong channels.

    Example:
        >>> preprocessed = preprocess_for_mobilenet(muzzle_crop)
        >>> tensor = torch.from_numpy(preprocessed)
    """
    if image is None or image.size == 0:
        raise ValueError("Cannot preprocess empty image")

    if len(image.shape) == 2:
        # Grayscale → convert to BGR
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif image.shape[2] == 4:
        # BGRA → BGR
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    elif image.shape[2] != 3:
        raise ValueError(f"Unexpected image channels: {image.shape[2]}")

    # Resize
    resized = cv2.resize(image, target_size, interpolation=cv2.INTER_LINEAR)

    # BGR → RGB
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

    # Normalize to [0, 1]
    normalized = rgb.astype(np.float32) / 255.0

    # ImageNet normalization
    normalized = (normalized - IMAGENET_MEAN) / IMAGENET_STD

    # HWC → CHW (PyTorch format)
    chw = np.transpose(normalized, (2, 0, 1))

    # Add batch dimension: (3, H, W) → (1, 3, H, W)
    batched = np.expand_dims(chw, axis=0)

    return batched.astype(np.float32)


def decode_frame_bytes(frame_bytes: bytes) -> Optional[np.ndarray]:
    """
    Decode image bytes to numpy array.

    Used for processing uploaded images in registration endpoint.

    Args:
        frame_bytes: Raw image bytes (JPEG, PNG, etc.)

    Returns:
        BGR numpy array, or None if decoding fails.
    """
    try:
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return frame
    except Exception as e:
        logger.error(f"Failed to decode image bytes: {e}")
        return None


def encode_frame_to_bytes(frame: np.ndarray, quality: int = 85) -> bytes:
    """
    Encode numpy frame to JPEG bytes.

    Used for storing reference muzzle images.

    Args:
        frame:   BGR numpy array
        quality: JPEG quality (0-100), default 85

    Returns:
        JPEG bytes
    """
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    _, buffer = cv2.imencode(".jpg", frame, encode_params)
    return buffer.tobytes()


def compute_cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    Compute cosine similarity between two embedding vectors.

    Args:
        vec_a: First embedding vector (1D)
        vec_b: Second embedding vector (1D)

    Returns:
        Similarity score in [-1, 1]. Higher = more similar.
        Returns 0.0 if either vector is zero.

    Example:
        >>> sim = compute_cosine_similarity(embedding_a, embedding_b)
        >>> if sim >= 0.85:
        ...     print("Same animal")
    """
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
