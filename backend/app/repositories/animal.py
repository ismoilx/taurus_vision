"""
Animal repository for data access operations.

RESPONSIBILITY: Database access ONLY — no business logic here.
All queries use SQLAlchemy 2.0 async syntax with full type safety.

PATTERN: Repository pattern isolates DB layer from business logic.
Service layer calls repository; repository never calls service.
"""

from typing import Optional, Sequence
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.animal import Animal, AnimalStatus, AnimalSpecies
from app.schemas.animal import AnimalCreate, AnimalUpdate
from app.core.exceptions import DatabaseError
import logging

logger = logging.getLogger(__name__)


class AnimalRepository:
    """
    Repository for Animal entity database operations.

    Provides full CRUD + filtering using async SQLAlchemy 2.0.
    All methods are strictly async and type-annotated.

    Args:
        db: AsyncSession injected via FastAPI Depends()
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -------------------------------------------------------------------------
    # CREATE
    # -------------------------------------------------------------------------

    async def create(self, animal_data: AnimalCreate) -> Animal:
        """
        Insert a new animal row.

        NOTE: Does NOT check uniqueness — that is the Service layer's job.

        Args:
            animal_data: Validated Pydantic schema

        Returns:
            Persisted Animal ORM instance (with generated id)

        Raises:
            DatabaseError: On any SQLAlchemy/DB-level failure
        """
        try:
            animal = Animal(**animal_data.model_dump())
            self.db.add(animal)
            await self.db.flush()          # Get generated PK without commit
            await self.db.refresh(animal)  # Load DB-computed defaults
            logger.debug(f"[repo] Created animal pk={animal.id} tag={animal.tag_id}")
            return animal
        except Exception as exc:
            logger.error(f"[repo] create failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="Failed to create animal",
                details={"error": str(exc)},
            ) from exc

    # -------------------------------------------------------------------------
    # READ — single
    # -------------------------------------------------------------------------

    async def get_by_id(self, animal_id: int) -> Optional[Animal]:
        """
        Fetch animal by primary key.

        Returns:
            Animal instance or None if not found
        """
        try:
            result = await self.db.execute(
                select(Animal).where(Animal.id == animal_id)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(f"[repo] get_by_id({animal_id}) failed: {exc}")
            raise DatabaseError(
                message=f"Failed to fetch animal id={animal_id}",
                details={"error": str(exc)},
            ) from exc

    async def get_by_tag_id(self, tag_id: str) -> Optional[Animal]:
        """
        Fetch animal by tag identifier (case-insensitive).

        Args:
            tag_id: e.g. "jnv-001" or "JNV-001" — treated equally

        Returns:
            Animal instance or None
        """
        try:
            result = await self.db.execute(
                select(Animal).where(
                    func.upper(Animal.tag_id) == tag_id.upper()
                )
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(f"[repo] get_by_tag_id({tag_id}) failed: {exc}")
            raise DatabaseError(
                message=f"Failed to fetch animal tag={tag_id}",
                details={"error": str(exc)},
            ) from exc

    # -------------------------------------------------------------------------
    # READ — collection
    # -------------------------------------------------------------------------

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        species: Optional[str] = None,
        status: Optional[AnimalStatus] = None,
    ) -> Sequence[Animal]:
        """
        Paginated list with optional filters.

        Args:
            skip:    Offset for pagination
            limit:   Page size (caller should cap at 100)
            species: Filter by species string (e.g. "cattle")
            status:  Filter by AnimalStatus enum

        Returns:
            Sequence of Animal instances (may be empty)
        """
        try:
            stmt = select(Animal)

            # Build WHERE clauses dynamically
            conditions = []
            if species:
                try:
                    conditions.append(
                        Animal.species == AnimalSpecies(species.lower())
                    )
                except ValueError:
                    logger.warning(f"[repo] Unknown species filter: {species!r} — ignored")

            if status:
                conditions.append(Animal.status == status)

            if conditions:
                stmt = stmt.where(and_(*conditions))

            stmt = stmt.offset(skip).limit(limit).order_by(Animal.id)

            result = await self.db.execute(stmt)
            return result.scalars().all()

        except Exception as exc:
            logger.error(f"[repo] get_all failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="Failed to fetch animals",
                details={"error": str(exc)},
            ) from exc

    async def count(
        self,
        species: Optional[str] = None,
        status: Optional[AnimalStatus] = None,
    ) -> int:
        """
        Count animals matching optional filters.

        Used alongside get_all() to build paginated responses.

        Returns:
            Integer count
        """
        try:
            stmt = select(func.count()).select_from(Animal)

            conditions = []
            if species:
                try:
                    conditions.append(
                        Animal.species == AnimalSpecies(species.lower())
                    )
                except ValueError:
                    pass

            if status:
                conditions.append(Animal.status == status)

            if conditions:
                stmt = stmt.where(and_(*conditions))

            result = await self.db.execute(stmt)
            return result.scalar_one()

        except Exception as exc:
            logger.error(f"[repo] count failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="Failed to count animals",
                details={"error": str(exc)},
            ) from exc

    # -------------------------------------------------------------------------
    # UPDATE
    # -------------------------------------------------------------------------

    async def update(
        self,
        animal_id: int,
        update_data: AnimalUpdate,
    ) -> Optional[Animal]:
        """
        Partial update — only non-None fields are applied.

        Args:
            animal_id:   PK of the animal to update
            update_data: Pydantic schema; None fields are skipped

        Returns:
            Updated Animal instance, or None if not found

        Raises:
            DatabaseError: On DB failure
        """
        try:
            animal = await self.get_by_id(animal_id)
            if not animal:
                return None

            # Apply only fields that were explicitly set
            update_fields = update_data.model_dump(exclude_none=True)
            for field, value in update_fields.items():
                setattr(animal, field, value)

            await self.db.flush()
            await self.db.refresh(animal)

            logger.debug(
                f"[repo] Updated animal pk={animal_id} "
                f"fields={list(update_fields.keys())}"
            )
            return animal

        except DatabaseError:
            raise
        except Exception as exc:
            logger.error(f"[repo] update({animal_id}) failed: {exc}", exc_info=True)
            raise DatabaseError(
                message=f"Failed to update animal id={animal_id}",
                details={"error": str(exc)},
            ) from exc

    # -------------------------------------------------------------------------
    # DELETE
    # -------------------------------------------------------------------------

    async def delete(self, animal_id: int) -> bool:
        """
        Hard-delete animal by PK.

        Returns:
            True if deleted, False if not found
        """
        try:
            animal = await self.get_by_id(animal_id)
            if not animal:
                return False

            await self.db.delete(animal)
            await self.db.flush()

            logger.debug(f"[repo] Deleted animal pk={animal_id}")
            return True

        except DatabaseError:
            raise
        except Exception as exc:
            logger.error(f"[repo] delete({animal_id}) failed: {exc}", exc_info=True)
            raise DatabaseError(
                message=f"Failed to delete animal id={animal_id}",
                details={"error": str(exc)},
            ) from exc

    # -------------------------------------------------------------------------
    # HELPERS (used by pipeline / detection)
    # -------------------------------------------------------------------------

    async def get_first_active(self) -> Optional[Animal]:
        """
        Return the first active animal.

        Used by the detection pipeline when animal matching is not yet
        implemented (MVP fallback).
        """
        try:
            result = await self.db.execute(
                select(Animal)
                .where(Animal.status == AnimalStatus.ACTIVE)
                .order_by(Animal.id)
                .limit(1)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            raise DatabaseError(
                message="Failed to fetch first active animal",
                details={"error": str(exc)},
            ) from exc

    async def increment_detection_count(
        self,
        animal_id: int,
    ) -> None:
        """
        Atomically increment total_detections and update last_detected_at.

        Called by the detection pipeline after each confirmed detection.

        Args:
            animal_id: PK of the detected animal
        """
        from datetime import datetime

        try:
            animal = await self.get_by_id(animal_id)
            if not animal:
                logger.warning(
                    f"[repo] increment_detection_count: animal {animal_id} not found"
                )
                return

            animal.mark_detected()   # uses the model helper method
            await self.db.flush()

        except Exception as exc:
            logger.error(
                f"[repo] increment_detection_count({animal_id}) failed: {exc}"
            )
            # Non-critical — don't raise, just log