"""
Animal service for business logic.

This layer implements all business rules and orchestrates repository operations.

RESPONSIBILITY: Business logic, validation, rule enforcement.
NO direct database access - use Repository.
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.repositories.animal import AnimalRepository
from app.schemas.animal import AnimalCreate, AnimalUpdate, AnimalResponse, AnimalListResponse
from app.models.animal import Animal, AnimalStatus
from app.core.exceptions import (
    EntityNotFoundError,
    EntityAlreadyExistsError,
    BusinessRuleViolationError,
)

logger = logging.getLogger(__name__)


class AnimalService:
    """
    Service layer for Animal business logic.
    
    Enforces all business rules:
    1. Tag ID uniqueness
    2. Archived animals cannot be modified
    3. Proper status transitions
    
    Args:
        db: AsyncSession instance (injected)
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = AnimalRepository(db)
    
    async def create_animal(self, animal_data: AnimalCreate) -> AnimalResponse:
        """
        Create a new animal with business rule validation.
        
        BUSINESS RULES:
        1. Tag ID must be unique (case-insensitive)
        2. Birth date must be before acquisition date (validated in schema)
        
        Args:
            animal_data: Validated animal creation data
            
        Returns:
            Created animal response
            
        Raises:
            EntityAlreadyExistsError: If tag_id already exists
            
        Example:
            animal = await service.create_animal(AnimalCreate(
                tag_id="jnv-001",  # Will be uppercased
                species="cattle",
                ...
            ))
        """
        # BUSINESS RULE 1: Check tag_id uniqueness
        existing = await self.repository.get_by_tag_id(animal_data.tag_id)
        
        if existing:
            logger.warning(
                f"Attempted to create duplicate animal: {animal_data.tag_id}"
            )
            raise EntityAlreadyExistsError(
                message=f"Animal with tag ID '{animal_data.tag_id}' already exists",
                details={
                    "tag_id": animal_data.tag_id,
                    "existing_id": existing.id,
                },
            )
        
        # Create animal
        animal = await self.repository.create(animal_data)
        
        logger.info(
            f"Animal created successfully: {animal.tag_id} "
            f"(ID: {animal.id}, Species: {animal.species.value})"
        )
        
        return AnimalResponse.model_validate(animal)
    
    async def get_animal(self, animal_id: int) -> AnimalResponse:
        """
        Get animal by ID.
        
        Args:
            animal_id: Primary key
            
        Returns:
            Animal response
            
        Raises:
            EntityNotFoundError: If animal not found
        """
        animal = await self.repository.get_by_id(animal_id)
        
        if not animal:
            logger.warning(f"Animal not found: ID {animal_id}")
            raise EntityNotFoundError(
                message=f"Animal with ID {animal_id} not found",
                details={"animal_id": animal_id},
            )
        
        return AnimalResponse.model_validate(animal)
    
    async def get_animals(
        self,
        skip: int = 0,
        limit: int = 100,
        species: Optional[str] = None,
        status: Optional[str] = None,
    ) -> AnimalListResponse:
        """
        Get paginated list of animals with optional filters.
        
        Args:
            skip: Number of records to skip
            limit: Maximum records to return (max 100)
            species: Filter by species (optional)
            status: Filter by status (optional)
            
        Returns:
            Paginated list response with metadata
            
        Note:
            Limit is capped at 100 to prevent performance issues.
        """
        # Cap limit to prevent abuse
        if limit > 100:
            limit = 100
            logger.warning(f"Limit capped to 100 (requested: {limit})")
        
        # Convert status string to enum if provided
        status_enum = None
        if status:
            try:
                status_enum = AnimalStatus(status.lower())
            except ValueError:
                logger.warning(f"Invalid status filter: {status}")
                # Invalid status - just ignore filter
                pass
        
        # Get animals and total count
        animals = await self.repository.get_all(
            skip=skip,
            limit=limit,
            species=species,
            status=status_enum,
        )
        
        total = await self.repository.count(
            species=species,
            status=status_enum,
        )
        
        # Convert to response schemas
        items = [AnimalResponse.model_validate(animal) for animal in animals]
        
        return AnimalListResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )
    
    async def update_animal(
        self,
        animal_id: int,
        update_data: AnimalUpdate,
    ) -> AnimalResponse:
        """
        Update animal with business rule validation.
        
        BUSINESS RULES:
        1. Animal must exist
        2. Cannot update archived animals (SOLD, DECEASED)
        3. If tag_id is updated, new tag must be unique
        
        Args:
            animal_id: Primary key
            update_data: Fields to update
            
        Returns:
            Updated animal response
            
        Raises:
            EntityNotFoundError: If animal not found
            BusinessRuleViolationError: If trying to modify archived animal
            EntityAlreadyExistsError: If new tag_id already exists
        """
        # Get existing animal
        animal = await self.repository.get_by_id(animal_id)
        
        if not animal:
            logger.warning(f"Update failed: Animal {animal_id} not found")
            raise EntityNotFoundError(
                message=f"Animal with ID {animal_id} not found",
                details={"animal_id": animal_id},
            )
        
        # BUSINESS RULE 2: Cannot modify archived animals
        if animal.status in (AnimalStatus.SOLD, AnimalStatus.DECEASED):
            logger.warning(
                f"Attempted to update archived animal: "
                f"ID {animal_id}, Status {animal.status.value}"
            )
            raise BusinessRuleViolationError(
                message=(
                    f"Cannot modify archived animal "
                    f"(status: {animal.status.value})"
                ),
                details={
                    "animal_id": animal_id,
                    "status": animal.status.value,
                },
            )
        
        # BUSINESS RULE 3: If updating tag_id, check uniqueness
        if update_data.tag_id and update_data.tag_id != animal.tag_id:
            existing = await self.repository.get_by_tag_id(update_data.tag_id)
            
            if existing and existing.id != animal_id:
                logger.warning(
                    f"Tag ID conflict: {update_data.tag_id} "
                    f"already exists (ID: {existing.id})"
                )
                raise EntityAlreadyExistsError(
                    message=f"Tag ID '{update_data.tag_id}' already exists",
                    details={
                        "tag_id": update_data.tag_id,
                        "existing_id": existing.id,
                    },
                )
        
        # Perform update
        updated_animal = await self.repository.update(animal_id, update_data)
        
        logger.info(f"Animal updated successfully: ID {animal_id}")
        
        return AnimalResponse.model_validate(updated_animal)
    
    async def delete_animal(self, animal_id: int) -> None:
        """
        Delete animal with business rule validation.
        
        BUSINESS RULE: Cannot delete archived animals (SOLD, DECEASED).
        These should remain in the system for audit/history.
        
        Args:
            animal_id: Primary key
            
        Raises:
            EntityNotFoundError: If animal not found
            BusinessRuleViolationError: If trying to delete archived animal
            
        Note:
            This is a HARD delete. For production, consider implementing
            soft delete for all animals.
        """
        # Get existing animal
        animal = await self.repository.get_by_id(animal_id)
        
        if not animal:
            logger.warning(f"Delete failed: Animal {animal_id} not found")
            raise EntityNotFoundError(
                message=f"Animal with ID {animal_id} not found",
                details={"animal_id": animal_id},
            )
        
        # BUSINESS RULE: Cannot delete archived animals
        if animal.status in (AnimalStatus.SOLD, AnimalStatus.DECEASED):
            logger.warning(
                f"Attempted to delete archived animal: "
                f"ID {animal_id}, Status {animal.status.value}"
            )
            raise BusinessRuleViolationError(
                message=(
                    f"Cannot delete archived animal "
                    f"(status: {animal.status.value}). "
                    f"Archived animals must be preserved for audit trail."
                ),
                details={
                    "animal_id": animal_id,
                    "status": animal.status.value,
                },
            )
        
        # Perform delete
        deleted = await self.repository.delete(animal_id)
        
        if deleted:
            logger.info(f"Animal deleted successfully: ID {animal_id}")
        else:
            # This shouldn't happen (we already checked existence)
            # but handle it gracefully
            logger.error(f"Unexpected: Animal {animal_id} not found during delete")
            raise EntityNotFoundError(
                message=f"Animal with ID {animal_id} not found",
                details={"animal_id": animal_id},
            )
    
    async def get_animal_by_tag(self, tag_id: str) -> AnimalResponse:
        """
        Get animal by tag ID.
        
        Convenience method for looking up by tag instead of database ID.
        
        Args:
            tag_id: Unique tag identifier
            
        Returns:
            Animal response
            
        Raises:
            EntityNotFoundError: If animal not found
        """
        animal = await self.repository.get_by_tag_id(tag_id)
        
        if not animal:
            logger.warning(f"Animal not found: Tag {tag_id}")
            raise EntityNotFoundError(
                message=f"Animal with tag ID '{tag_id}' not found",
                details={"tag_id": tag_id},
            )
        
        return AnimalResponse.model_validate(animal)