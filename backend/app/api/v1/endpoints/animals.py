"""
API endpoints for Animal resources.

This module defines HTTP routes for CRUD operations on animals.
It handles HTTP-specific concerns (request/response, status codes)
and delegates business logic to the service layer.
"""

from typing import Optional
from fastapi import APIRouter, Depends, status, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from fastapi import Query
from app.models.animal import AnimalSpecies, AnimalStatus
from app.core.database import get_db
from app.services.animal import AnimalService
from app.schemas.animal import (
    AnimalCreate,
    AnimalUpdate,
    AnimalResponse,
    AnimalListResponse,
)
import logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    redirect_slashes=False,
    prefix="/animals",
    tags=["animals"],
)


# Dependency: Get service instance
def get_animal_service(
    db: AsyncSession = Depends(get_db)
) -> AnimalService:
    """
    Dependency injection for AnimalService.
    
    Creates a new service instance for each request with the database session.
    """
    return AnimalService(db)


@router.post(
    "/",
    response_model=AnimalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new animal",
    description="""
    Create a new animal record.
    
    **Business Rules:**
    - Tag ID must be unique (case-insensitive)
    - Tag ID will be automatically converted to uppercase
    - Birth date cannot be in the future
    - Acquisition date cannot be in the future
    """,
    responses={
        201: {"description": "Animal created successfully"},
        400: {"description": "Validation error"},
        409: {"description": "Tag ID already exists"},
        422: {"description": "Invalid request data"},
    },
)
async def create_animal(
    animal_data: AnimalCreate,
    service: AnimalService = Depends(get_animal_service),
) -> AnimalResponse:
    """
    Create a new animal.
    
    Returns the created animal with generated ID and timestamps.
    """
    try:
        return await service.create_animal(animal_data)
    except ValueError as e:
        if "already exists" in str(e) or "duplicate" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


    # ============================================================================
    # ADVANCED SEARCH API ENDPOINT - ADD TO ANIMALS API
    # ============================================================================
@router.get(
    "/search",
    response_model=list[AnimalResponse],
    summary="Advanced animal search",
    description="""
    Advanced multi-field search with filtering, sorting, and pagination.
    
    **Search capabilities:**
    - Tag ID (partial match, case-insensitive)
    - Species filter
    - Gender filter
    - Status filter
    - Breed (partial match)
    - Minimum detections threshold
    - Full-text search across tag_id, breed, notes
    
    **Sorting:**
    - Sort by: tag_id, species, status, total_detections, last_detected_at
    - Order: asc (ascending) or desc (descending)
    
    **Pagination:**
    - skip: Offset (default: 0)
    - limit: Max results (default: 20, max: 100)
    
    **Examples:**
    
    Find all active cattle:
    ```
    GET /api/v1/animals/search?species=cattle&status=active
    ```
    
    Search for animals with "JNV" in tag:
    ```
    GET /api/v1/animals/search?tag_id=JNV
    ```
    
    Find most detected animals:
    ```
    GET /api/v1/animals/search?sort_by=total_detections&sort_order=desc&limit=10
    ```
    
    Full-text search:
    ```
    GET /api/v1/animals/search?search_text=holstein
    ```
    """,
    responses={
        200: {
            "description": "Search results retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 1,
                            "tag_id": "JNV-001",
                            "species": "cattle",
                            "gender": "female",
                            "status": "active",
                            "breed": "Holstein",
                            "acquisition_date": "2024-01-15",
                            "birth_date": "2023-06-10",
                            "total_detections": 145,
                            "last_detected_at": "2026-02-16T10:30:00",
                            "first_detected_at": "2024-01-16T08:00:00",
                            "notes": "High milk producer",
                            "created_at": "2024-01-15T12:00:00",
                            "updated_at": "2026-02-16T10:30:00"
                        }
                    ]
                }
            }
        },
        400: {"description": "Invalid parameters"},
        500: {"description": "Server error"}
    },
    tags=["Animals"]
)
async def search_animals(
    tag_id: Optional[str] = Query(None, description="Filter by tag ID (partial match)"),
    species: Optional[str] = Query(None, description="Filter by species (cattle/sheep/goat/horse/other)"),
    gender: Optional[str] = Query(None, description="Filter by gender (male/female/unknown)"),
    status: Optional[str] = Query(None, description="Filter by status (active/quarantine/sick/sold/deceased/transferred)"),
    breed: Optional[str] = Query(None, description="Filter by breed (partial match)"),
    min_detections: Optional[int] = Query(None, description="Minimum number of detections", ge=0),
    search_text: Optional[str] = Query(None, description="Full-text search across tag_id, breed, notes"),
    sort_by: str = Query("tag_id", description="Sort by field", pattern="^(tag_id|species|status|total_detections|last_detected_at)$"),
    sort_order: str = Query("asc", description="Sort order", pattern="^(asc|desc)$"),
    skip: int = Query(0, description="Pagination offset", ge=0),
    limit: int = Query(20, description="Maximum results", ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> list[AnimalResponse]:
    """
    Advanced animal search with multiple filters.
    
    This endpoint provides powerful search capabilities for finding animals
    based on various criteria. Combine multiple filters for precise results.
    
    Performance note: Queries are optimized with proper indexing.
    Large result sets are paginated for efficiency.
    
    Frontend usage example:
    ```javascript
    // Search for active cattle sorted by detections
    const response = await fetch(
      '/api/v1/animals/search?species=cattle&status=active&sort_by=total_detections&sort_order=desc'
    );
    const animals = await response.json();
    ```
    """
    from app.repositories.animal import AnimalRepository
    from app.schemas.animal import AnimalResponse
    from app.models.animal import AnimalSpecies, AnimalStatus
    
    logger.info(
        f"API call: GET /animals/search",
        extra={
            "extra_data": {
                "tag_id": tag_id,
                "species": species,
                "status": status,
                "search_text": search_text,
                "sort_by": sort_by
            }
        }
    )
    
    try:
        # Convert string enums to proper types
        species_enum = AnimalSpecies(species) if species else None
        status_enum = AnimalStatus(status) if status else None
        
        # Perform search
        repo = AnimalRepository(db)
        animals, total = await repo.advanced_search(
            tag_id=tag_id,
            species=species_enum,
            gender=gender,
            status=status_enum,
            breed=breed,
            min_detections=min_detections,
            search_text=search_text,
            sort_by=sort_by,
            sort_order=sort_order,
            skip=skip,
            limit=limit
        )
        
        logger.info(
            f"Search completed: found {len(animals)} animals (total: {total})",
            extra={
                "extra_data": {
                    "results_count": len(animals),
                    "total": total,
                    "skip": skip,
                    "limit": limit
                }
            }
        )
        
        # Note: We're returning list directly, not paginated response
        # Frontend can use skip/limit for pagination
        return [AnimalResponse.model_validate(animal) for animal in animals]
        
    except ValueError as e:
        logger.warning(f"Invalid parameter: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameter: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error during search: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform search"
        )


@router.get(
    "/search/text",
    response_model=list[AnimalResponse],
    summary="Simple text search",
    description="""
    Simple full-text search across animal data.
    
    Searches in:
    - Tag ID
    - Breed
    - Notes
    
    Case-insensitive, partial matching.
    
    **Example:**
    ```
    GET /api/v1/animals/search/text?q=holstein&limit=10
    ```
    
    Use this for:
    - Quick search bars
    - Autocomplete
    - Simple filtering
    
    For advanced filtering, use `/search` endpoint instead.
    """,
    responses={
        200: {"description": "Search results retrieved successfully"},
        400: {"description": "Missing or invalid search query"},
        500: {"description": "Server error"}
    },
    tags=["Animals"]
)
async def text_search_animals(
    q: str = Query(..., description="Search query", min_length=1),
    skip: int = Query(0, description="Pagination offset", ge=0),
    limit: int = Query(20, description="Maximum results", ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> list[AnimalResponse]:
    """
    Simple text search across animal fields.
    
    Args:
        q: Search query (minimum 1 character)
        skip: Pagination offset
        limit: Maximum results
        db: Database session
    
    Returns:
        List of matching animals
    
    Frontend usage:
    ```javascript
    // Search as user types
    const results = await fetch(`/api/v1/animals/search/text?q=${userInput}`);
    ```
    """
    from app.repositories.animal import AnimalRepository
    from app.schemas.animal import AnimalResponse
    
    logger.info(f"API call: GET /animals/search/text?q={q}")
    
    try:
        repo = AnimalRepository(db)
        animals, total = await repo.search_by_text(
            search_text=q,
            skip=skip,
            limit=limit
        )
        
        logger.info(f"Text search completed: found {len(animals)} animals (total: {total})")
        
        return [AnimalResponse.model_validate(animal) for animal in animals]
        
    except Exception as e:
        logger.error(f"Error during text search: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform text search"
        )


@router.get(
    "/{animal_id}",
    response_model=AnimalResponse,
    summary="Get animal by ID",
    description="Retrieve a single animal by its database ID.",
    responses={
        200: {"description": "Animal found"},
        404: {"description": "Animal not found"},
    },
)
async def get_animal(
    animal_id: int,
    service: AnimalService = Depends(get_animal_service),
) -> AnimalResponse:
    """
    Get a single animal by ID.
    
    Args:
        animal_id: Primary key of the animal
    """
    return await service.get_animal(animal_id)


@router.get(
    "/",
    response_model=AnimalListResponse,
    summary="List all animals",
    description="""
    Get a paginated list of animals with optional filtering.
    
    **Filtering:**
    - `species`: Filter by species (cattle, sheep, goat, horse, other)
    - `status`: Filter by status (active, quarantine, sick, sold, deceased, transferred)
    
    **Pagination:**
    - `skip`: Number of records to skip (default: 0)
    - `limit`: Maximum records to return (default: 10, max: 100)
    """,
    responses={
        200: {"description": "List of animals"},
    },
)
async def list_animals(
    skip: int = Query(
        default=0,
        ge=0,
        description="Number of records to skip",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of records to return",
    ),
    species: Optional[str] = Query(
        default=None,
        description="Filter by species (e.g., 'cattle', 'sheep')",
    ),
    status: Optional[str] = Query(
        default=None,
        description="Filter by status (e.g., 'active', 'sold')",
    ),
    service: AnimalService = Depends(get_animal_service),
) -> AnimalListResponse:
    """
    Get paginated list of animals.
    
    Returns list with pagination metadata.
    """
    return await service.get_animals(
        skip=skip,
        limit=limit,
        species=species,
        status=status,
    )


@router.patch(
    "/{animal_id}",
    response_model=AnimalResponse,
    summary="Update animal",
    description="""
    Partially update an animal record.
    
    **Business Rules:**
    - Only provided fields will be updated (partial update)
    - Cannot update archived animals (status: SOLD or DECEASED)
    - If updating tag_id, new tag must be unique
    """,
    responses={
        200: {"description": "Animal updated successfully"},
        400: {
            "description": (
                "Cannot modify archived animal or tag_id conflict"
            ),
        },
        404: {"description": "Animal not found"},
        422: {"description": "Invalid request data"},
    },
)
async def update_animal(
    animal_id: int,
    update_data: AnimalUpdate,
    service: AnimalService = Depends(get_animal_service),
) -> AnimalResponse:
    """
    Update an existing animal (partial update).
    
    Only non-null fields in the request body will be updated.
    """
    return await service.update_animal(animal_id, update_data)


@router.delete(
    "/{animal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete animal",
    description="""
    Delete an animal record.
    
    **Business Rule:**
    - Cannot delete archived animals (status: SOLD or DECEASED)
    - Archived animals must be preserved for audit trail
    """,
    responses={
        204: {"description": "Animal deleted successfully"},
        400: {"description": "Cannot delete archived animal"},
        404: {"description": "Animal not found"},
    },
)
async def delete_animal(
    animal_id: int,
    service: AnimalService = Depends(get_animal_service),
) -> None:
    """
    Delete an animal.
    
    Returns 204 No Content on success.
    """
    await service.delete_animal(animal_id)
    # FastAPI automatically returns 204 with no body


@router.get(
    "/tag/{tag_id}",
    response_model=AnimalResponse,
    summary="Get animal by tag ID",
    description="Retrieve a single animal by its tag identifier (case-insensitive).",
    responses={
        200: {"description": "Animal found"},
        404: {"description": "Animal not found"},
    },
)
async def get_animal_by_tag(
    tag_id: str,
    service: AnimalService = Depends(get_animal_service),
) -> AnimalResponse:
    """
    Get a single animal by tag ID.
    
    Args:
        tag_id: Unique tag identifier (e.g., "JNV-001")
    """
    return await service.get_animal_by_tag(tag_id)

# ──────────────────────────────────────────────────────────────────────────────
# Animal Detection Tarixi  (Sprint 3 qo'shimcha)
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{animal_id}/detections",
    summary="Get detection history for an animal",
    description="Return the most recent YOLO detections linked to a specific animal.",
)
async def get_animal_detections(
    animal_id: int,
    limit: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    Return detection records for one animal (newest first).

    Args:
        animal_id: Animal primary key
        limit:     Max records to return (default 20)
        db:        DB session

    Returns:
        List of detection dicts with id, camera_id, timestamp,
        confidence, class_name.

    Raises:
        HTTPException 404: If animal not found
    """
    from sqlalchemy import select, desc
    from app.models.animal import Animal
    from app.models.detection import Detection

    # Jonivor mavjudligini tekshirish
    animal = await db.scalar(select(Animal).where(Animal.id == animal_id))
    if not animal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Animal {animal_id} not found",
        )

    result = await db.execute(
        select(Detection)
        .where(Detection.animal_id == animal_id)
        .order_by(desc(Detection.timestamp))
        .limit(limit)
    )
    rows = result.scalars().all()

    return [
        {
            "id":         d.id,
            "camera_id":  d.camera_id,
            "timestamp":  d.timestamp.isoformat(),
            "confidence": round(d.confidence, 3),
            "class_name": d.class_name,
            "bbox":       d.bbox,
        }
        for d in rows
    ]