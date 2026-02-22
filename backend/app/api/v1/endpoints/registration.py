"""
Animal Registration & Identification Endpoints.

Handles:
1. POST /register/{animal_id}  — Register muzzle photo for an animal
2. POST /identify              — Identify unknown animal from photo
3. GET  /{animal_id}/embeddings — List stored embeddings for animal
4. DELETE /embeddings/{embedding_id} — Remove specific embedding

WORKFLOW:
First time: Operator registers animal by uploading muzzle photo.
  → System extracts embedding and stores in DB.

Detection: YOLO detects cattle, system auto-identifies.
  → If score ≥ 0.80: matched to known animal
  → If score < 0.80: unknown, alert operator to register
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.v1.deps import get_current_active_user
from app.core.exceptions import EntityNotFoundError
from app.models.animal import Animal
from app.models.animal_embedding import AnimalEmbedding
from app.services.identification_service import (
    IdentificationService,
    IDENTIFICATION_THRESHOLD,
)
from app.schemas.registration import (
    RegistrationResponse,
    IdentificationResponse,
    EmbeddingInfo,
)
from app.utils.image_utils import decode_frame_bytes, extract_muzzle_region

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/identification", tags=["Identification"], dependencies=[Depends(get_current_active_user)])

# Max upload size: 10MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024


# ============================================================================
# HELPER
# ============================================================================

async def _get_animal_or_404(animal_id: int, db: AsyncSession) -> Animal:
    """Get animal by ID or raise 404."""
    stmt = select(Animal).where(Animal.id == animal_id)
    result = await db.execute(stmt)
    animal = result.scalar_one_or_none()
    if animal is None:
        raise HTTPException(status_code=404, detail=f"Animal {animal_id} not found")
    return animal


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post(
    "/register/{animal_id}",
    response_model=RegistrationResponse,
    summary="Register muzzle photo for an animal",
    description="""
Upload a clear frontal photo of the cattle's muzzle to register the animal
for AI identification.

**Requirements:**
- Clear frontal or semi-frontal view of muzzle
- Good lighting (avoid harsh shadows)
- JPEG or PNG format
- Minimum resolution: 640x480

**Tips for best accuracy:**
- Upload 3-5 photos in different lighting conditions
- The first photo becomes the reference (shown in UI)
- Subsequent uploads improve identification robustness
""",
)
async def register_animal_muzzle(
    animal_id: int,
    photo: UploadFile = File(..., description="Muzzle photo (JPEG/PNG)"),
    full_frame: bool = Form(
        default=False,
        description="If True: photo is full frame with YOLO bbox. "
                    "If False (default): photo is already cropped muzzle.",
    ),
    bbox_x: Optional[float] = Form(default=None, description="YOLO bbox center X (normalized, only if full_frame=True)"),
    bbox_y: Optional[float] = Form(default=None, description="YOLO bbox center Y (normalized, only if full_frame=True)"),
    bbox_w: Optional[float] = Form(default=None, description="YOLO bbox width (normalized, only if full_frame=True)"),
    bbox_h: Optional[float] = Form(default=None, description="YOLO bbox height (normalized, only if full_frame=True)"),
    db: AsyncSession = Depends(get_db),
) -> RegistrationResponse:
    """
    Register animal muzzle print for identification.

    Upload a frontal muzzle photo. System extracts MobileNetV2 embedding
    and stores it in DB for future identification.
    """
    # Validate animal exists
    animal = await _get_animal_or_404(animal_id, db)

    # Read and validate image
    image_bytes = await photo.read()
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Image too large (max {MAX_IMAGE_SIZE // 1024 // 1024}MB)",
        )

    frame = decode_frame_bytes(image_bytes)
    if frame is None:
        raise HTTPException(
            status_code=422,
            detail="Invalid image file. Upload a valid JPEG or PNG.",
        )

    # Extract muzzle region
    if full_frame:
        if any(v is None for v in [bbox_x, bbox_y, bbox_w, bbox_h]):
            raise HTTPException(
                status_code=422,
                detail="full_frame=True requires bbox_x, bbox_y, bbox_w, bbox_h",
            )
        muzzle_crop = extract_muzzle_region(
            frame, bbox_x, bbox_y, bbox_w, bbox_h, normalized=True
        )
        if muzzle_crop is None:
            raise HTTPException(
                status_code=422,
                detail="Could not extract muzzle region from bounding box. "
                       "Check that the bounding box is valid.",
            )
    else:
        # Assume entire image is the muzzle crop
        muzzle_crop = frame

    # Validate muzzle crop is large enough
    h, w = muzzle_crop.shape[:2]
    if h < 32 or w < 32:
        raise HTTPException(
            status_code=422,
            detail=f"Muzzle crop too small ({w}x{h}px). Minimum 32x32px required.",
        )

    # Check if this is the first embedding (→ reference)
    service = IdentificationService(db)
    existing_count = await service.get_animal_embedding_count(animal_id)
    is_reference = existing_count == 0

    # Extract and save embedding
    try:
        embedding_record = await service.add_embedding(
            animal_id=animal_id,
            muzzle_crop=muzzle_crop,
            is_reference=is_reference,
            source="registration",
            quality_score=None,  # Future: compute sharpness score
        )
        await db.commit()
        await db.refresh(embedding_record)
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail=f"AI model error: {e}. Ensure AI models are loaded.",
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Registration failed for animal {animal_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Registration failed")

    new_count = existing_count + 1

    logger.info(
        f"✓ Registered muzzle for animal {animal.tag_id} "
        f"(embedding #{new_count}, reference={is_reference})"
    )

    return RegistrationResponse(
        animal_id=animal_id,
        tag_id=animal.tag_id,
        embedding_id=embedding_record.id,
        embedding_count=new_count,
        is_reference=is_reference,
        message=(
            f"Muzzle registered successfully for {animal.tag_id}. "
            f"Total embeddings: {new_count}. "
            + ("This is the reference embedding." if is_reference
               else "Additional embedding added for better accuracy.")
        ),
    )


@router.post(
    "/identify",
    response_model=IdentificationResponse,
    summary="Identify animal from muzzle photo",
    description="""
Upload a cattle muzzle photo to identify which registered animal it is.

Returns the matched animal with similarity score, or 'unknown' if no
registered animal matches above the threshold (0.80).
""",
)
async def identify_animal(
    photo: UploadFile = File(..., description="Muzzle photo to identify"),
    full_frame: bool = Form(
        default=False,
        description="If True: provide YOLO bbox coordinates below.",
    ),
    bbox_x: Optional[float] = Form(default=None),
    bbox_y: Optional[float] = Form(default=None),
    bbox_w: Optional[float] = Form(default=None),
    bbox_h: Optional[float] = Form(default=None),
    threshold: float = Form(
        default=IDENTIFICATION_THRESHOLD,
        ge=0.5,
        le=1.0,
        description="Similarity threshold (0.5-1.0). Default: 0.80",
    ),
    db: AsyncSession = Depends(get_db),
) -> IdentificationResponse:
    """
    Identify an animal from a muzzle photo.

    Compares uploaded photo against all registered animals.
    """
    # Read image
    image_bytes = await photo.read()
    frame = decode_frame_bytes(image_bytes)
    if frame is None:
        raise HTTPException(status_code=422, detail="Invalid image file.")

    # Get muzzle crop
    if full_frame:
        if any(v is None for v in [bbox_x, bbox_y, bbox_w, bbox_h]):
            raise HTTPException(
                status_code=422,
                detail="full_frame=True requires bbox parameters.",
            )
        muzzle_crop = extract_muzzle_region(
            frame, bbox_x, bbox_y, bbox_w, bbox_h, normalized=True
        )
        if muzzle_crop is None:
            raise HTTPException(
                status_code=422,
                detail="Could not extract muzzle from bounding box.",
            )
    else:
        muzzle_crop = frame

    # Run identification
    service = IdentificationService(db)
    try:
        result = await service.identify_from_crop(muzzle_crop, threshold=threshold)
    except Exception as e:
        logger.error(f"Identification failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Identification error: {e}")

    if result.is_identified:
        message = (
            f"Animal identified: {result.tag_id} "
            f"(confidence: {result.similarity_score:.1%})"
        )
    else:
        message = (
            f"Unknown animal (best match: {result.similarity_score:.1%}, "
            f"threshold: {threshold:.1%}). Please register this animal."
        )

    return IdentificationResponse(
        animal_id=result.animal_id,
        tag_id=result.tag_id,
        similarity_score=result.similarity_score,
        is_identified=result.is_identified,
        message=message,
    )


@router.get(
    "/{animal_id}/embeddings",
    response_model=list[EmbeddingInfo],
    summary="List embeddings for an animal",
)
async def list_animal_embeddings(
    animal_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[EmbeddingInfo]:
    """
    Get all stored embeddings for a specific animal.

    Useful for checking registration status and managing embeddings.
    """
    await _get_animal_or_404(animal_id, db)

    stmt = (
        select(AnimalEmbedding)
        .where(AnimalEmbedding.animal_id == animal_id)
        .order_by(AnimalEmbedding.created_at.desc())
    )
    result = await db.execute(stmt)
    embeddings = result.scalars().all()

    return [
        EmbeddingInfo(
            id=e.id,
            animal_id=e.animal_id,
            is_reference=e.is_reference,
            source=e.source,
            quality_score=e.quality_score,
            photo_path=e.photo_path,
            created_at=e.created_at,
        )
        for e in embeddings
    ]


@router.delete(
    "/embeddings/{embedding_id}",
    summary="Delete a specific embedding",
)
async def delete_embedding(
    embedding_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Delete a specific embedding.

    WARNING: Deleting the reference embedding will require re-registration.
    The next oldest embedding will NOT automatically become the reference.
    """
    stmt = select(AnimalEmbedding).where(AnimalEmbedding.id == embedding_id)
    result = await db.execute(stmt)
    embedding = result.scalar_one_or_none()

    if embedding is None:
        raise HTTPException(status_code=404, detail=f"Embedding {embedding_id} not found")

    was_reference = embedding.is_reference
    animal_id = embedding.animal_id

    await db.delete(embedding)
    await db.commit()

    logger.info(f"Deleted embedding {embedding_id} (animal_id={animal_id})")

    return {
        "deleted": True,
        "embedding_id": embedding_id,
        "animal_id": animal_id,
        "was_reference": was_reference,
        "warning": (
            "This was the reference embedding. "
            "Upload a new photo to re-register."
        ) if was_reference else None,
    }