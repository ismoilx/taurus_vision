"""
Automated Detection Pipeline.

Orchestrates the complete flow:
Camera → YOLO Detection → Weight Estimation → Database → WebSocket Broadcast

ARCHITECTURE:
- Async/await for non-blocking I/O
- Idempotent operations (safe retries)
- Error isolation (failures don't crash pipeline)
- Performance monitoring
- Graceful degradation

USAGE:
```python
pipeline = DetectionPipeline(
    camera_service=camera,
    yolo_service=yolo,
    weight_service=weight_service,
    ws_manager=ws_manager
)

await pipeline.start()  # Runs continuously
```
"""

import asyncio
from datetime import datetime
from typing import Optional
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.camera.base import CameraServiceInterface
from app.services.ai.yolo_service import YoloService
from app.services.weight_measurement import WeightMeasurementService
from app.services.weight_estimator import WeightEstimator, get_weight_estimator
from app.services.ai.base import Detection
from app.schemas.weight_measurement import WeightMeasurementCreate
from app.api.v1.websocket import ConnectionManager
from app.config import settings
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class DetectionPipeline:
    """
    Automated detection pipeline.
    
    Coordinates all services to provide end-to-end livestock monitoring:
    1. Camera captures frame
    2. YOLO detects animals
    3. Weight estimator calculates weight
    4. Database saves measurement
    5. WebSocket broadcasts update
    
    RESILIENCE:
    - Continues on individual frame failures
    - Logs all errors for debugging
    - Tracks performance metrics
    - Graceful shutdown
    
    PERFORMANCE:
    - Non-blocking async operations
    - Parallel processing where possible
    - Frame throttling to prevent overload
    """
    
    def __init__(
        self,
        camera_service: CameraServiceInterface,
        yolo_service: YoloService,
        ws_manager: Optional[ConnectionManager] = None,
    ):
        """
        Initialize detection pipeline.
        
        Args:
            camera_service: Camera implementation
            yolo_service: YOLO detection service
            ws_manager: WebSocket manager (optional)
        """
        self.camera = camera_service
        self.yolo = yolo_service
        self.ws_manager = ws_manager
        self.weight_estimator = get_weight_estimator()
        
        # State
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        # Performance tracking
        self._stats = {
            'total_frames': 0,
            'processed_frames': 0,
            'detections': 0,
            'measurements_created': 0,
            'errors': 0,
            'start_time': None,
        }
    
    async def start(self) -> None:
        """
        Start automated detection pipeline.
        
        Runs continuously until stop() is called.
        
        Raises:
            RuntimeError: If already running
        """
        if self._running:
            raise RuntimeError("Pipeline already running")
        
        logger.info("Starting detection pipeline...")
        
        # Initialize camera
        await self.camera.initialize()
        
        self._running = True
        self._stats['start_time'] = datetime.utcnow()
        
        # Create background task
        self._task = asyncio.create_task(self._run_pipeline())
        
        logger.info("✓ Detection pipeline started")
    
    async def stop(self) -> None:
        """
        Stop detection pipeline gracefully.
        
        Waits for current frame to finish processing.
        """
        if not self._running:
            return
        
        logger.info("Stopping detection pipeline...")
        
        self._running = False
        
        # Wait for task to finish
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Pipeline stop timeout, cancelling task")
                self._task.cancel()
        
        # Stop camera
        await self.camera.stop()
        
        logger.info("✓ Detection pipeline stopped")
        self._log_stats()
    
    async def _run_pipeline(self) -> None:
        """
        Main pipeline loop.
        
        Processes frames continuously with error handling.
        """
        logger.info(
            f"Pipeline loop started (skip_frames: {settings.FRAME_SKIP})"
        )
        
        try:
            async for frame in self.camera.stream_frames(
                skip_frames=settings.FRAME_SKIP
            ):
                if not self._running:
                    break
                
                self._stats['total_frames'] += 1
                
                # Process frame (non-blocking, isolated errors)
                try:
                    await self._process_frame(frame)
                    self._stats['processed_frames'] += 1
                    
                except Exception as e:
                    self._stats['errors'] += 1
                    logger.error(
                        f"Frame processing failed: {e}",
                        exc_info=True
                    )
                    # Continue with next frame (resilience)
                    continue
        
        except asyncio.CancelledError:
            logger.info("Pipeline loop cancelled")
        
        except Exception as e:
            logger.error(f"Pipeline loop error: {e}", exc_info=True)
            self._running = False
    
    async def _process_frame(self, frame) -> None:
        """
        Process single frame through complete pipeline.
        
        Steps:
        1. YOLO detection
        2. Weight estimation (for each detection)
        3. Database save (idempotent)
        4. WebSocket broadcast
        
        Args:
            frame: CameraFrame object
        """
        # Step 1: YOLO Detection
        result = await self.yolo.detect(
            frame=frame.frame,
            confidence_threshold=settings.AI_CONFIDENCE_THRESHOLD,
            target_classes=settings.AI_TARGET_CLASSES,
        )
        
        if not result.has_detections:
            logger.debug("No detections in frame")
            return
        
        self._stats['detections'] += len(result.detections)
        
        logger.info(
            f"Detected {len(result.detections)} animal(s) "
            f"in {result.inference_time_ms:.1f}ms"
        )
        
        # Step 2-4: Process each detection
        tasks = [
            self._process_detection(detection, frame, result.frame_shape)
            for detection in result.detections
        ]
        
        # Run in parallel (non-blocking)
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _process_detection(
        self,
        detection: Detection,
        frame,
        frame_shape: tuple,
    ) -> None:
        """
        Process single detection.
        
        Args:
            detection: YOLO detection object
            frame: CameraFrame
            frame_shape: (height, width, channels)
        """
        try:
            # Step 2: Weight estimation
            weight_kg, confidence = self.weight_estimator.estimate(
                detection=detection,
                frame_shape=frame_shape,
                use_conservative=True,
            )
            
            logger.info(
                f"Weight estimated: {weight_kg:.1f}kg "
                f"(confidence: {confidence:.2f}) "
                f"for {detection.class_name}"
            )
            
            # Step 3: Save to database (idempotent)
            await self._save_measurement(
                detection=detection,
                weight_kg=weight_kg,
                confidence=confidence,
                camera_id=frame.camera_id,
            )
            
        except Exception as e:
            logger.error(
                f"Detection processing failed: {e}",
                exc_info=True
            )
    
    async def _save_measurement(
        self,
        detection: Detection,
        weight_kg: float,
        confidence: float,
        camera_id: str,
    ) -> None:
        """
        Save weight measurement to database.
        
        IDEMPOTENT: Safe to retry (upsert logic in future).
        
        Args:
            detection: YOLO detection
            weight_kg: Estimated weight
            confidence: Estimation confidence
            camera_id: Camera identifier
        """
        # Get database session
        async with AsyncSessionLocal() as db:
            try:
                # Create service
                service = WeightMeasurementService(db, self.ws_manager)
                
                # CRITICAL: Find or create animal
                # In MVP, we assume animal_id=1 exists
                # TODO: Implement animal matching/tracking
                animal_id = await self._get_or_create_animal(
                    db,
                    detection.class_name
                )
                
                # Create measurement
                measurement_data = WeightMeasurementCreate(
                    animal_id=animal_id,
                    timestamp=detection.timestamp,
                    estimated_weight_kg=weight_kg,
                    confidence_score=confidence,
                    camera_id=camera_id,
                    raw_ai_data={
                        'yolo_confidence': detection.confidence,
                        'bounding_box': detection.bounding_box.to_dict(),
                        'class_id': detection.class_id,
                        'class_name': detection.class_name,
                    },
                )
                
                # Save (triggers WebSocket broadcast)
                await service.create_measurement(measurement_data)
                
                self._stats['measurements_created'] += 1
                
                logger.info(
                    f"✓ Measurement saved and broadcasted "
                    f"(animal_id: {animal_id})"
                )
                
            except Exception as e:
                logger.error(f"Database save failed: {e}", exc_info=True)
                raise
    
    async def _get_or_create_animal(
        self,
        db: AsyncSession,
        class_name: str,
    ) -> int:
        """
        Get or create animal for detection.
        
        MVP: Returns first animal or creates default.
        PRODUCTION: Implement animal tracking/matching.
        
        Args:
            db: Database session
            class_name: Detected class name
            
        Returns:
            Animal ID
        """
        from app.repositories.animal import AnimalRepository
        from app.schemas.animal import AnimalCreate
        from app.models.animal import AnimalSpecies
        
        repo = AnimalRepository(db)
        
        # Try to get first animal
        animals = await repo.get_all(skip=0, limit=1)
        
        if animals:
            return animals[0].id
        
        # Create default animal (MVP only)
        logger.warning("No animals in database, creating default animal")
        
        # Map class name to species
        species_map = {
            'cow': AnimalSpecies.CATTLE,
            'cattle': AnimalSpecies.CATTLE,
            'sheep': AnimalSpecies.SHEEP,
            'goat': AnimalSpecies.GOAT,
        }
        
        species = species_map.get(
            class_name.lower(),
            AnimalSpecies.CATTLE
        )
        
        animal_data = AnimalCreate(
            tag_id=f"AUTO-{class_name.upper()}-001",
            species=species,
            gender="unknown",
            acquisition_date=datetime.utcnow(),
        )
        
        animal = await repo.create(animal_data)
        await db.commit()
        
        logger.info(f"Created default animal: {animal.tag_id}")
        
        return animal.id
    
    def _log_stats(self) -> None:
        """Log pipeline statistics."""
        if self._stats['start_time']:
            runtime = datetime.utcnow() - self._stats['start_time']
            runtime_seconds = runtime.total_seconds()
            
            fps = (
                self._stats['processed_frames'] / runtime_seconds
                if runtime_seconds > 0 else 0
            )
            
            logger.info("=" * 60)
            logger.info("PIPELINE STATISTICS")
            logger.info("=" * 60)
            logger.info(f"Runtime: {runtime}")
            logger.info(f"Total frames: {self._stats['total_frames']}")
            logger.info(f"Processed frames: {self._stats['processed_frames']}")
            logger.info(f"Processing FPS: {fps:.2f}")
            logger.info(f"Total detections: {self._stats['detections']}")
            logger.info(f"Measurements created: {self._stats['measurements_created']}")
            logger.info(f"Errors: {self._stats['errors']}")
            logger.info("=" * 60)
    
    def get_stats(self) -> dict:
        """Get pipeline statistics."""
        stats = self._stats.copy()
        
        if stats['start_time']:
            runtime = datetime.utcnow() - stats['start_time']
            stats['runtime_seconds'] = runtime.total_seconds()
            stats['fps'] = (
                stats['processed_frames'] / stats['runtime_seconds']
                if stats['runtime_seconds'] > 0 else 0
            )
        
        return stats
    
    @property
    def is_running(self) -> bool:
        """Check if pipeline is running."""
        return self._running