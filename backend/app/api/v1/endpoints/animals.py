"""
API endpoints for Animal resources.

This module defines HTTP routes for CRUD operations on animals.
It handles HTTP-specific concerns (request/response, status codes)
and delegates business logic to the service layer.
"""

from typing import Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.animal import AnimalService
from app.schemas.animal import (
    AnimalCreate,
    AnimalUpdate,
    AnimalResponse,
    AnimalListResponse,
)

# Create router
router = APIRouter(
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
        400: {"description": "Tag ID already exists or validation error"},
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
    return await service.create_animal(animal_data)


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