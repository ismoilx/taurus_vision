# """
# Animal repository for data access operations.

# This layer handles all database operations for Animal entities.
# It uses SQLAlchemy 2.0 async syntax and is strictly typed.

# RESPONSIBILITY: Database access only, NO business logic.
# """

# from typing import Optional, Sequence
# from sqlalchemy import select, func, update, delete
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.animal import Animal, AnimalStatus
# from app.schemas.animal import AnimalCreate, AnimalUpdate
# from app.core.exceptions import DatabaseError
# import logging

# logger = logging.getLogger(__name__)


# class AnimalRepository:
#     """
#     Repository for Animal entity database operations.
    
#     Provides CRUD operations using async SQLAlchemy.
#     All methods are strictly async and use SQLAlchemy 2.0 syntax.
    
#     Args:
#         db: AsyncSession instance (injected via dependency)
#     """
    
#     def __init__(self, db: AsyncSession):
#         self.db = db
    
#     async def create(self, animal_data: AnimalCreate) -> Animal:
#         """
#         Create a new animal record.
        
#         Args:
#             animal_data: Validated animal creation data
            
#         Returns:
#             Created animal instance with generated ID
            
#         Raises:
#             DatabaseError: If database operation fails
            
#         Note:
#             Does NOT check for duplicates - that's Service layer responsibility.
#         """
#         try:
#             # Create Animal instance from schema
#             animal = Animal(**animal_data.model_dump())
            
#             # Add to session
#             self.db.add(animal)
            
#             # Flush to get the ID (without committing transaction)
#             await self.db.flush()
            
#             # Refresh to get database-generated values
#             await self.db.refresh(animal)
            
#             logger.info(f"Created animal: {animal.tag_id} (ID: {animal.id})")
            
#             return animal
            
#         except Exception as e:
#             logger.error(f"Failed to create animal: {e}")
#             raise DatabaseError(
#                 message="Failed to create animal",
#                 details={"error": str(e)},
#             )
    
#     async def get_by_id(self, animal_id: int) -> Optional[Animal]:
#         """
#         Get animal by ID.
        
#         Args:
#             animal_id: Primary key
            
#         Returns:
#             Animal instance if found, None otherwise
            
#         Raises:
#             DatabaseError: If database operation fails
#         """
#         try:
#             # SQLAlchemy 2.0 syntax
#             stmt = select(Animal).where(Animal.id == animal_id)
#             result = await self.db.execute(stmt)
#             animal = result.scalar_one_or_none()
            
#             return animal
            
#         except Exception as e:
#             logger.error(f"Failed to get animal {animal_id}: {e}")
#             raise DatabaseError(
#                 message="Failed to retrieve animal",
#                 details={"animal_id": animal_id, "error": str(e)},
#             )
    
#     async def get_by_tag_id(self, tag_id: str) -> Optional[Animal]:
#         """
#         Get animal by tag ID.
        
#         Args:
#             tag_id: Unique tag identifier
            
#         Returns:
#             Animal instance if found, None otherwise
            
#         Raises:
#             DatabaseError: If database operation fails
            
#         Note:
#             tag_id is case-insensitive (stored as uppercase in DB).
#         """
#         try:
#             stmt = select(Animal).where(Animal.tag_id == tag_id.upper())
#             result = await self.db.execute(stmt)
#             animal = result.scalar_one_or_none()
            
#             return animal
            
#         except Exception as e:
#             logger.error(f"Failed to get animal by tag {tag_id}: {e}")
#             raise DatabaseError(
#                 message="Failed to retrieve animal",
#                 details={"tag_id": tag_id, "error": str(e)},
#             )
    
#     async def get_all(
#         self,
#         skip: int = 0,
#         limit: int = 100,
#         species: Optional[str] = None,
#         status: Optional[AnimalStatus] = None,
#     ) -> Sequence[Animal]:
#         """
#         Get all animals with optional filtering and pagination.
        
#         Args:
#             skip: Number of records to skip (for pagination)
#             limit: Maximum number of records to return
#             species: Filter by species (optional)
#             status: Filter by status (optional)
            
#         Returns:
#             List of animal instances
            
#         Raises:
#             DatabaseError: If database operation fails
            
#         Note:
#             Returns empty list if no animals found (not an error).
#         """
#         try:
#             # Base query
#             stmt = select(Animal)
            
#             # Apply filters
#             if species:
#                 stmt = stmt.where(Animal.species == species)
            
#             if status:
#                 stmt = stmt.where(Animal.status == status)
            
#             # Order by ID (newest first)
#             stmt = stmt.order_by(Animal.id.desc())
            
#             # Apply pagination
#             stmt = stmt.offset(skip).limit(limit)
            
#             # Execute
#             result = await self.db.execute(stmt)
#             animals = result.scalars().all()
            
#             logger.info(
#                 f"Retrieved {len(animals)} animals "
#                 f"(skip={skip}, limit={limit}, species={species}, status={status})"
#             )
            
#             return animals
            
#         except Exception as e:
#             logger.error(f"Failed to get animals: {e}")
#             raise DatabaseError(
#                 message="Failed to retrieve animals",
#                 details={"error": str(e)},
#             )
    
#     async def count(
#         self,
#         species: Optional[str] = None,
#         status: Optional[AnimalStatus] = None,
#     ) -> int:
#         """
#         Count total animals (for pagination metadata).
        
#         Args:
#             species: Filter by species (optional)
#             status: Filter by status (optional)
            
#         Returns:
#             Total count of animals matching filters
            
#         Raises:
#             DatabaseError: If database operation fails
#         """
#         try:
#             # Base query
#             stmt = select(func.count()).select_from(Animal)
            
#             # Apply same filters as get_all
#             if species:
#                 stmt = stmt.where(Animal.species == species)
            
#             if status:
#                 stmt = stmt.where(Animal.status == status)
            
#             # Execute
#             result = await self.db.execute(stmt)
#             count = result.scalar_one()
            
#             return count
            
#         except Exception as e:
#             logger.error(f"Failed to count animals: {e}")
#             raise DatabaseError(
#                 message="Failed to count animals",
#                 details={"error": str(e)},
#             )
    
#     async def update(self, animal_id: int, update_data: AnimalUpdate) -> Optional[Animal]:
#         """
#         Update animal record.
        
#         Args:
#             animal_id: Primary key
#             update_data: Fields to update (only non-None fields are updated)
            
#         Returns:
#             Updated animal instance if found, None otherwise
            
#         Raises:
#             DatabaseError: If database operation fails
            
#         Note:
#             Uses Pydantic's exclude_unset to only update provided fields.
#             Does NOT enforce business rules - that's Service layer responsibility.
#         """
#         try:
#             # Get existing animal
#             animal = await self.get_by_id(animal_id)
            
#             if not animal:
#                 return None
            
#             # Get only fields that were actually set (exclude None/unset)
#             update_dict = update_data.model_dump(exclude_unset=True)
            
#             if not update_dict:
#                 # No fields to update
#                 return animal
            
#             # Update fields
#             for field, value in update_dict.items():
#                 setattr(animal, field, value)
            
#             # Flush changes
#             await self.db.flush()
#             await self.db.refresh(animal)
            
#             logger.info(f"Updated animal {animal_id}: {list(update_dict.keys())}")
            
#             return animal
            
#         except Exception as e:
#             logger.error(f"Failed to update animal {animal_id}: {e}")
#             raise DatabaseError(
#                 message="Failed to update animal",
#                 details={"animal_id": animal_id, "error": str(e)},
#             )
    
#     async def delete(self, animal_id: int) -> bool:
#         """
#         Delete animal record (hard delete).
        
#         Args:
#             animal_id: Primary key
            
#         Returns:
#             True if animal was deleted, False if not found
            
#         Raises:
#             DatabaseError: If database operation fails
            
#         Note:
#             This is a HARD delete (permanent).
#             Service layer should enforce soft delete for archived animals.
#         """
#         try:
#             # Check if exists
#             animal = await self.get_by_id(animal_id)
            
#             if not animal:
#                 return False
            
#             # Delete using SQLAlchemy 2.0 syntax
#             stmt = delete(Animal).where(Animal.id == animal_id)
#             await self.db.execute(stmt)
#             await self.db.flush()
            
#             logger.info(f"Deleted animal {animal_id}")
            
#             return True
            
#         except Exception as e:
#             logger.error(f"Failed to delete animal {animal_id}: {e}")
#             raise DatabaseError(
#                 message="Failed to delete animal",
#                 details={"animal_id": animal_id, "error": str(e)},
#             )
#######################################################################################
#Gemini tavfsiya qildi 10/02/2026
"""
Animal repository for data access operations.

This layer handles all database operations for Animal entities.
It uses SQLAlchemy 2.0 async syntax and is strictly typed.

RESPONSIBILITY: Database access only, NO business logic.
"""

from typing import Optional, Sequence
from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.animal import Animal, AnimalStatus
from app.schemas.animal import AnimalCreate, AnimalUpdate
from app.core.exceptions import DatabaseError
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AnimalRepository:
    """
    Repository for Animal entity database operations.
    
    Provides CRUD operations using async SQLAlchemy.
    All methods are strictly async and use SQLAlchemy 2.0 syntax.
    
    Args:
        db: AsyncSession instance (injected via dependency)
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, animal_data: AnimalCreate) -> Animal:
        """
        Create a new animal record with timezone normalization.
        """
        try:
            # 1. Ma'lumotlarni lug'atga aylantiramiz
            data = animal_data.model_dump()
            
            # 2. BAZA BILAN MOSLASHTIRISH: 
            # PostgreSQL 'TIMESTAMP WITHOUT TIME ZONE' ishlatgani uchun 
            # Python'dagi aware datetime'larni naive holatga keltiramiz.
            for key, value in data.items():
                if isinstance(value, datetime) and value.tzinfo is not None:
                    data[key] = value.replace(tzinfo=None)
            
            # 3. Tozalangan ma'lumotlar bilan model yaratamiz
            animal = Animal(**data)
            
            # Add to session
            self.db.add(animal)
            
            # Flush to get the ID
            await self.db.flush()
            
            # Refresh to get database-generated values
            await self.db.refresh(animal)
            
            logger.info(f"Created animal: {animal.tag_id} (ID: {animal.id})")
            
            return animal
            
        except Exception as e:
            logger.error(f"Failed to create animal: {e}")
            raise DatabaseError(
                message="Failed to create animal",
                details={"error": str(e)},
            )
    
    async def get_by_id(self, animal_id: int) -> Optional[Animal]:
        """Get animal by ID."""
        try:
            stmt = select(Animal).where(Animal.id == animal_id)
            result = await self.db.execute(stmt)
            animal = result.scalar_one_or_none()
            return animal
        except Exception as e:
            logger.error(f"Failed to get animal {animal_id}: {e}")
            raise DatabaseError(
                message="Failed to retrieve animal",
                details={"animal_id": animal_id, "error": str(e)},
            )
    
    async def get_by_tag_id(self, tag_id: str) -> Optional[Animal]:
        """Get animal by tag ID."""
        try:
            stmt = select(Animal).where(Animal.tag_id == tag_id.upper())
            result = await self.db.execute(stmt)
            animal = result.scalar_one_or_none()
            return animal
        except Exception as e:
            logger.error(f"Failed to get animal by tag {tag_id}: {e}")
            raise DatabaseError(
                message="Failed to retrieve animal",
                details={"tag_id": tag_id, "error": str(e)},
            )
    
    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        species: Optional[str] = None,
        status: Optional[AnimalStatus] = None,
    ) -> Sequence[Animal]:
        """Get all animals with optional filtering and pagination."""
        try:
            stmt = select(Animal)
            if species:
                stmt = stmt.where(Animal.species == species)
            if status:
                stmt = stmt.where(Animal.status == status)
            
            stmt = stmt.order_by(Animal.id.desc())
            stmt = stmt.offset(skip).limit(limit)
            
            result = await self.db.execute(stmt)
            animals = result.scalars().all()
            
            logger.info(f"Retrieved {len(animals)} animals")
            return animals
        except Exception as e:
            logger.error(f"Failed to get animals: {e}")
            raise DatabaseError(message="Failed to retrieve animals", details={"error": str(e)})
    
    async def count(
        self,
        species: Optional[str] = None,
        status: Optional[AnimalStatus] = None,
    ) -> int:
        """Count total animals matching filters."""
        try:
            stmt = select(func.count()).select_from(Animal)
            if species:
                stmt = stmt.where(Animal.species == species)
            if status:
                stmt = stmt.where(Animal.status == status)
            
            result = await self.db.execute(stmt)
            return result.scalar_one()
        except Exception as e:
            logger.error(f"Failed to count animals: {e}")
            raise DatabaseError(message="Failed to count animals")
    
    async def update(self, animal_id: int, update_data: AnimalUpdate) -> Optional[Animal]:
        """Update animal record with timezone normalization."""
        try:
            animal = await self.get_by_id(animal_id)
            if not animal:
                return None
            
            # 1. Faqat kiritilgan maydonlarni lug'atga olamiz
            update_dict = update_data.model_dump(exclude_unset=True)
            
            # 2. Vaqt zonalarini tozalash
            for key, value in update_dict.items():
                if isinstance(value, datetime) and value.tzinfo is not None:
                    update_dict[key] = value.replace(tzinfo=None)
            
            if not update_dict:
                return animal
            
            # 3. Maydonlarni yangilash
            for field, value in update_dict.items():
                setattr(animal, field, value)
            
            await self.db.flush()
            await self.db.refresh(animal)
            
            logger.info(f"Updated animal {animal_id}")
            return animal
            
        except Exception as e:
            logger.error(f"Failed to update animal {animal_id}: {e}")
            raise DatabaseError(
                message="Failed to update animal",
                details={"animal_id": animal_id, "error": str(e)},
            )
    
    async def delete(self, animal_id: int) -> bool:
        """Hard delete animal record."""
        try:
            animal = await self.get_by_id(animal_id)
            if not animal:
                return False
            
            stmt = delete(Animal).where(Animal.id == animal_id)
            await self.db.execute(stmt)
            await self.db.flush()
            
            logger.info(f"Deleted animal {animal_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete animal {animal_id}: {e}")
            raise DatabaseError(message="Failed to delete animal")