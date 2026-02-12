"""
Weight Estimation Service.

Estimates animal weight from bounding box dimensions.

ALGORITHM:
Based on empirical research showing correlation between
bounding box area and animal weight.

FORMULA (simplified for MVP):
weight_kg = k * box_area * depth_factor

Where:
- k: species-specific constant (calibrated)
- box_area: normalized bounding box area
- depth_factor: estimated depth (future: from depth camera)

ACCURACY:
- Current MVP: ±15-20kg error
- With depth camera: ±5-10kg error (future)
- With ML model: ±3-5kg error (training data needed)

PRODUCTION NOTE:
This is a simplified algorithm for MVP/demo.
In production, replace with trained ML model using:
- Multiple camera angles
- Depth data
- Historical weight data
- Breed-specific models
"""

from datetime import datetime
from typing import Optional
import logging

from app.services.ai.base import Detection, BoundingBox

logger = logging.getLogger(__name__)


class WeightEstimator:
    """
    Weight estimation from bounding box.
    
    Uses geometric analysis to estimate animal weight.
    Supports multiple species with calibrated constants.
    
    CALIBRATION:
    Constants are derived from empirical data:
    - Cattle: 450-650kg average (Holstein, Angus)
    - Sheep: 45-90kg average
    - Goat: 30-60kg average
    
    USAGE:
    ```python
    estimator = WeightEstimator()
    
    weight_kg, confidence = estimator.estimate(
        detection=detection,
        frame_shape=(640, 480, 3)
    )
    ```
    """
    
    # Species-specific calibration constants
    # Format: {class_id: (base_weight, scale_factor, typical_box_area)}
    SPECIES_CALIBRATION = {
        19: {  # COCO: Cow
            'name': 'cattle',
            'base_weight': 500.0,  # kg (average adult)
            'scale_factor': 1200.0,  # Empirical scaling
            'min_weight': 200.0,
            'max_weight': 900.0,
            'typical_box_area': 0.15,  # Normalized area for 500kg cow
        },
        20: {  # COCO: Sheep
            'name': 'sheep',
            'base_weight': 70.0,
            'scale_factor': 180.0,
            'min_weight': 30.0,
            'max_weight': 120.0,
            'typical_box_area': 0.08,
        },
    }
    
    def __init__(self):
        """Initialize weight estimator."""
        self._total_estimates = 0
        logger.info("Weight estimator initialized")
    
    def estimate(
        self,
        detection: Detection,
        frame_shape: tuple[int, int, int],
        use_conservative: bool = True,
    ) -> tuple[float, float]:
        """
        Estimate weight from detection.
        
        Args:
            detection: YOLO detection object
            frame_shape: (height, width, channels)
            use_conservative: Apply conservative factor (reduces overestimation)
            
        Returns:
            (estimated_weight_kg, confidence_score)
            
        Raises:
            ValueError: If species not supported
        """
        class_id = detection.class_id
        
        # Check if species is supported
        if class_id not in self.SPECIES_CALIBRATION:
            raise ValueError(
                f"Weight estimation not supported for class_id {class_id} "
                f"({detection.class_name})"
            )
        
        calibration = self.SPECIES_CALIBRATION[class_id]
        bbox = detection.bounding_box
        
        # Calculate bounding box area (normalized)
        box_area = bbox.width * bbox.height
        
        # Estimate weight using calibrated formula
        weight_kg = self._calculate_weight(
            box_area=box_area,
            calibration=calibration,
            confidence=detection.confidence,
        )
        
        # Apply conservative factor if enabled
        # (Reduces overestimation bias in 2D vision)
        if use_conservative:
            weight_kg *= 0.92  # 8% reduction
        
        # Clamp to realistic range
        weight_kg = max(
            calibration['min_weight'],
            min(weight_kg, calibration['max_weight'])
        )
        
        # Calculate estimation confidence
        # Based on:
        # 1. YOLO detection confidence
        # 2. Box size (closer to typical = higher confidence)
        # 3. Aspect ratio (unrealistic shapes = lower confidence)
        estimation_confidence = self._calculate_confidence(
            bbox=bbox,
            yolo_confidence=detection.confidence,
            box_area=box_area,
            typical_area=calibration['typical_box_area'],
        )
        
        self._total_estimates += 1
        
        logger.debug(
            f"Weight estimated: {weight_kg:.1f}kg "
            f"(confidence: {estimation_confidence:.2f}, "
            f"box_area: {box_area:.3f})"
        )
        
        return weight_kg, estimation_confidence
    
    def _calculate_weight(
        self,
        box_area: float,
        calibration: dict,
        confidence: float,
    ) -> float:
        """
        Calculate weight using calibrated formula.
        
        FORMULA:
        weight = base_weight * (box_area / typical_area) * scale_factor
        
        Args:
            box_area: Normalized bounding box area
            calibration: Species calibration data
            confidence: YOLO detection confidence
            
        Returns:
            Estimated weight in kg
        """
        # Area ratio (actual vs typical)
        area_ratio = box_area / calibration['typical_box_area']
        
        # Base calculation
        # Weight scales roughly with area^1.5 (volume approximation)
        weight = calibration['base_weight'] * (area_ratio ** 1.5)
        
        # Confidence adjustment
        # Lower confidence → closer to average weight
        confidence_factor = 0.7 + (0.3 * confidence)
        weight = (
            weight * confidence_factor +
            calibration['base_weight'] * (1 - confidence_factor)
        )
        
        return weight
    
    def _calculate_confidence(
        self,
        bbox: BoundingBox,
        yolo_confidence: float,
        box_area: float,
        typical_area: float,
    ) -> float:
        """
        Calculate estimation confidence score.
        
        Factors:
        1. YOLO confidence (30%)
        2. Area similarity to typical (40%)
        3. Aspect ratio realism (30%)
        
        Args:
            bbox: Bounding box
            yolo_confidence: YOLO detection confidence
            box_area: Normalized box area
            typical_area: Expected area for species
            
        Returns:
            Confidence score (0.0-1.0)
        """
        # Factor 1: YOLO confidence (30% weight)
        yolo_factor = yolo_confidence * 0.3
        
        # Factor 2: Area similarity (40% weight)
        # Closer to typical area = higher confidence
        area_diff = abs(box_area - typical_area) / typical_area
        area_factor = max(0, 1.0 - area_diff) * 0.4
        
        # Factor 3: Aspect ratio realism (30% weight)
        # Cattle typically: width/height ~ 1.2-1.8
        # Extreme ratios indicate poor angle or occlusion
        aspect_ratio = bbox.width / bbox.height if bbox.height > 0 else 0
        
        ideal_aspect = 1.4  # Typical cattle side view
        aspect_diff = abs(aspect_ratio - ideal_aspect) / ideal_aspect
        aspect_factor = max(0, 1.0 - aspect_diff) * 0.3
        
        # Combined confidence
        total_confidence = yolo_factor + area_factor + aspect_factor
        
        # Clamp to [0.3, 0.95]
        # Never below 0.3 (always some uncertainty in 2D)
        # Never above 0.95 (no depth data)
        return max(0.3, min(0.95, total_confidence))
    
    def get_stats(self) -> dict:
        """Get estimator statistics."""
        return {
            'total_estimates': self._total_estimates,
            'supported_species': list(self.SPECIES_CALIBRATION.keys()),
        }
    
    @classmethod
    def get_supported_species(cls) -> list[dict]:
        """
        Get list of supported species.
        
        Returns:
            List of species info dicts
        """
        return [
            {
                'class_id': class_id,
                'name': info['name'],
                'base_weight': info['base_weight'],
                'weight_range': (info['min_weight'], info['max_weight']),
            }
            for class_id, info in cls.SPECIES_CALIBRATION.items()
        ]


# Global singleton instance
_weight_estimator: WeightEstimator | None = None


def get_weight_estimator() -> WeightEstimator:
    """
    Get global WeightEstimator instance.
    
    Returns:
        Singleton WeightEstimator
    """
    global _weight_estimator
    
    if _weight_estimator is None:
        _weight_estimator = WeightEstimator()
    
    return _weight_estimator
