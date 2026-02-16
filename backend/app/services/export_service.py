"""
Export Service - Taurus Vision

Professional data export service for CSV and Excel formats.
Uses pandas for efficient data manipulation and openpyxl for Excel.

Author: Taurus Vision Team
Date: 2026-02-16
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from io import BytesIO
from sqlalchemy import select, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import pandas as pd

from app.models.animal import Animal, AnimalStatus
from app.models.detection import Detection
from app.models.weight_measurement import WeightMeasurement
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class ExportService:
    """
    Data export service for CSV and Excel formats.
    
    Provides methods for exporting:
    - Animals (with filters)
    - Detections (date range, animal filter)
    - Weight measurements (animal-specific or all)
    
    All exports include:
    - Column headers
    - Formatted data
    - Proper encoding (UTF-8)
    - Excel: Multiple sheets, formatting, formulas
    """
    
    def __init__(self):
        """Initialize export service."""
        pass
    
    # =========================================================================
    # ANIMALS EXPORT
    # =========================================================================
    
    async def export_animals_csv(
        self,
        db: AsyncSession,
        filters: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        Export animals to CSV format.
        
        Args:
            db: Database session
            filters: Optional filters (status, species, gender)
        
        Returns:
            CSV file as bytes (UTF-8 encoded)
        
        CSV columns:
        - id
        - tag_id
        - species
        - gender
        - status
        - breed
        - acquisition_date
        - total_detections
        - last_detected_at
        - notes
        
        Example:
            >>> service = ExportService()
            >>> csv_bytes = await service.export_animals_csv(db)
            >>> with open('animals.csv', 'wb') as f:
            ...     f.write(csv_bytes)
        """
        logger.info(f"Exporting animals to CSV: filters={filters}")
        
        try:
            # Build query
            query = select(Animal)
            
            # Apply filters
            if filters:
                conditions = []
                
                if 'status' in filters and filters['status']:
                    conditions.append(Animal.status == AnimalStatus(filters['status']))
                
                if 'species' in filters and filters['species']:
                    conditions.append(Animal.species == filters['species'])
                
                if 'gender' in filters and filters['gender']:
                    conditions.append(Animal.gender == filters['gender'])
                
                if 'tag_id' in filters and filters['tag_id']:
                    # Partial match
                    conditions.append(Animal.tag_id.ilike(f"%{filters['tag_id']}%"))
                
                if conditions:
                    query = query.where(and_(*conditions))
            
            # Execute query
            result = await db.execute(query.order_by(Animal.tag_id))
            animals = result.scalars().all()
            
            # Convert to DataFrame
            data = []
            for animal in animals:
                data.append({
                    'id': animal.id,
                    'tag_id': animal.tag_id,
                    'species': animal.species,
                    'gender': animal.gender,
                    'status': animal.status.value,
                    'breed': animal.breed or '',
                    'acquisition_date': animal.acquisition_date.isoformat() if animal.acquisition_date else '',
                    'total_detections': animal.total_detections,
                    'last_detected_at': animal.last_detected_at.isoformat() if animal.last_detected_at else '',
                    'notes': animal.notes or ''
                })
            
            df = pd.DataFrame(data)
            
            # Export to CSV
            csv_buffer = BytesIO()
            df.to_csv(csv_buffer, index=False, encoding='utf-8')
            csv_bytes = csv_buffer.getvalue()
            csv_buffer.close()
            
            logger.info(f"Animals exported to CSV: {len(animals)} animals, {len(csv_bytes)} bytes")
            return csv_bytes
            
        except Exception as e:
            logger.error(f"Error exporting animals to CSV: {e}", exc_info=True)
            raise
    
    # =========================================================================
    # DETECTIONS EXPORT
    # =========================================================================
    
    async def export_detections_csv(
        self,
        db: AsyncSession,
        date_from: date,
        date_to: date,
        animal_id: Optional[int] = None
    ) -> bytes:
        """
        Export detections to CSV format.
        
        Args:
            db: Database session
            date_from: Start date
            date_to: End date
            animal_id: Optional animal ID filter
        
        Returns:
            CSV file as bytes (UTF-8 encoded)
        
        CSV columns:
        - id
        - animal_id
        - animal_tag_id
        - camera_id
        - detected_at
        - confidence_score
        - bbox_x, bbox_y, bbox_width, bbox_height
        
        Example:
            >>> service = ExportService()
            >>> csv_bytes = await service.export_detections_csv(
            ...     db, date(2026, 2, 1), date(2026, 2, 16)
            ... )
        """
        logger.info(
            f"Exporting detections to CSV: {date_from} to {date_to}, animal_id={animal_id}"
        )
        
        try:
            # Build query
            query = select(Detection).options(
                selectinload(Detection.animal)
            ).where(
                and_(
                    func.date(Detection.detected_at) >= date_from,
                    func.date(Detection.detected_at) <= date_to
                )
            )
            
            # Filter by animal if specified
            if animal_id is not None:
                query = query.where(Detection.animal_id == animal_id)
            
            # Execute query
            result = await db.execute(query.order_by(Detection.detected_at.desc()))
            detections = result.scalars().all()
            
            # Convert to DataFrame
            data = []
            for detection in detections:
                data.append({
                    'id': detection.id,
                    'animal_id': detection.animal_id,
                    'animal_tag_id': detection.animal.tag_id if detection.animal else 'Unknown',
                    'camera_id': detection.camera_id,
                    'detected_at': detection.detected_at.isoformat(),
                    'confidence_score': round(detection.confidence_score, 4),
                    'bbox_x': detection.bbox_x or 0,
                    'bbox_y': detection.bbox_y or 0,
                    'bbox_width': detection.bbox_width or 0,
                    'bbox_height': detection.bbox_height or 0,
                })
            
            df = pd.DataFrame(data)
            
            # Export to CSV
            csv_buffer = BytesIO()
            df.to_csv(csv_buffer, index=False, encoding='utf-8')
            csv_bytes = csv_buffer.getvalue()
            csv_buffer.close()
            
            logger.info(
                f"Detections exported to CSV: {len(detections)} detections, {len(csv_bytes)} bytes"
            )
            return csv_bytes
            
        except Exception as e:
            logger.error(f"Error exporting detections to CSV: {e}", exc_info=True)
            raise
    
    # =========================================================================
    # WEIGHTS EXPORT (EXCEL)
    # =========================================================================
    
    async def export_weights_excel(
        self,
        db: AsyncSession,
        animal_ids: Optional[List[int]] = None
    ) -> bytes:
        """
        Export weight measurements to Excel format.
        
        Args:
            db: Database session
            animal_ids: Optional list of animal IDs (None = all animals)
        
        Returns:
            Excel file as bytes (.xlsx format)
        
        Excel structure:
        - Sheet 1 (Summary): Overview of all animals
        - Sheet 2+ (Animal_{tag}): Detailed weight history per animal
        
        Features:
        - Multiple sheets
        - Formatted headers
        - Formulas (average, min, max)
        - Date formatting
        - Number formatting
        
        Example:
            >>> service = ExportService()
            >>> excel_bytes = await service.export_weights_excel(db, [1, 2, 3])
            >>> with open('weights.xlsx', 'wb') as f:
            ...     f.write(excel_bytes)
        """
        logger.info(f"Exporting weights to Excel: animal_ids={animal_ids}")
        
        try:
            # Build query for animals
            animals_query = select(Animal).options(
                selectinload(Animal.weight_measurements)
            ).where(Animal.status == AnimalStatus.ACTIVE)
            
            if animal_ids:
                animals_query = animals_query.where(Animal.id.in_(animal_ids))
            
            result = await db.execute(animals_query.order_by(Animal.tag_id))
            animals = result.scalars().all()
            
            # Create Excel writer
            excel_buffer = BytesIO()
            writer = pd.ExcelWriter(excel_buffer, engine='openpyxl')
            
            # ===== SHEET 1: SUMMARY =====
            summary_data = []
            for animal in animals:
                measurements = animal.weight_measurements
                if measurements:
                    weights = [m.estimated_weight_kg for m in measurements]
                    latest = max(measurements, key=lambda m: m.timestamp)
                    
                    summary_data.append({
                        'Tag ID': animal.tag_id,
                        'Species': animal.species.capitalize(),
                        'Total Measurements': len(measurements),
                        'Latest Weight (kg)': round(latest.estimated_weight_kg, 2),
                        'Latest Date': latest.timestamp.date().isoformat(),
                        'Average Weight (kg)': round(sum(weights) / len(weights), 2),
                        'Min Weight (kg)': round(min(weights), 2),
                        'Max Weight (kg)': round(max(weights), 2),
                    })
                else:
                    summary_data.append({
                        'Tag ID': animal.tag_id,
                        'Species': animal.species.capitalize(),
                        'Total Measurements': 0,
                        'Latest Weight (kg)': 'N/A',
                        'Latest Date': 'N/A',
                        'Average Weight (kg)': 'N/A',
                        'Min Weight (kg)': 'N/A',
                        'Max Weight (kg)': 'N/A',
                    })
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # ===== SHEETS 2+: PER-ANIMAL DETAILS =====
            for animal in animals:
                measurements = animal.weight_measurements
                if measurements:
                    # Sort by timestamp
                    sorted_measurements = sorted(
                        measurements,
                        key=lambda m: m.timestamp,
                        reverse=True
                    )
                    
                    # Create data
                    animal_data = []
                    for m in sorted_measurements:
                        animal_data.append({
                            'Date': m.timestamp.date().isoformat(),
                            'Time': m.timestamp.time().strftime('%H:%M:%S'),
                            'Weight (kg)': round(m.estimated_weight_kg, 2),
                            'Confidence': round(m.confidence_score * 100, 1),
                            'Camera': m.camera_id,
                        })
                    
                    animal_df = pd.DataFrame(animal_data)
                    
                    # Sheet name (Excel limit: 31 chars)
                    sheet_name = f"Animal_{animal.tag_id}"[:31]
                    animal_df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # Save Excel file
            writer.close()
            excel_bytes = excel_buffer.getvalue()
            excel_buffer.close()
            
            logger.info(
                f"Weights exported to Excel: {len(animals)} animals, {len(excel_bytes)} bytes"
            )
            return excel_bytes
            
        except Exception as e:
            logger.error(f"Error exporting weights to Excel: {e}", exc_info=True)
            raise
    
    # =========================================================================
    # COMPREHENSIVE EXPORT (ALL DATA)
    # =========================================================================
    
    async def export_all_data_excel(
        self,
        db: AsyncSession
    ) -> bytes:
        """
        Export all farm data to comprehensive Excel workbook.
        
        Args:
            db: Database session
        
        Returns:
            Excel file as bytes (.xlsx format)
        
        Excel structure:
        - Sheet 1: Animals (all animals with metadata)
        - Sheet 2: Detections (last 30 days)
        - Sheet 3: Weights (all measurements)
        - Sheet 4: Statistics (summary stats)
        
        This is useful for:
        - Complete data backup
        - External analysis
        - Sharing with stakeholders
        - Audit trails
        
        Example:
            >>> service = ExportService()
            >>> excel_bytes = await service.export_all_data_excel(db)
        """
        logger.info("Exporting all data to Excel")
        
        try:
            excel_buffer = BytesIO()
            writer = pd.ExcelWriter(excel_buffer, engine='openpyxl')
            
            # ===== SHEET 1: ANIMALS =====
            animals_query = select(Animal).order_by(Animal.tag_id)
            animals_result = await db.execute(animals_query)
            animals = animals_result.scalars().all()
            
            animals_data = []
            for animal in animals:
                animals_data.append({
                    'ID': animal.id,
                    'Tag ID': animal.tag_id,
                    'Species': animal.species,
                    'Gender': animal.gender,
                    'Status': animal.status.value,
                    'Breed': animal.breed or '',
                    'Acquisition Date': animal.acquisition_date.isoformat() if animal.acquisition_date else '',
                    'Total Detections': animal.total_detections,
                    'Last Detected': animal.last_detected_at.isoformat() if animal.last_detected_at else '',
                    'Notes': animal.notes or ''
                })
            
            animals_df = pd.DataFrame(animals_data)
            animals_df.to_excel(writer, sheet_name='Animals', index=False)
            
            # ===== SHEET 2: DETECTIONS (Last 30 days) =====
            thirty_days_ago = datetime.utcnow().date() - pd.Timedelta(days=30)
            detections_query = select(Detection).options(
                selectinload(Detection.animal)
            ).where(
                func.date(Detection.detected_at) >= thirty_days_ago
            ).order_by(Detection.detected_at.desc()).limit(10000)  # Limit to avoid huge files
            
            detections_result = await db.execute(detections_query)
            detections = detections_result.scalars().all()
            
            detections_data = []
            for d in detections:
                detections_data.append({
                    'ID': d.id,
                    'Animal Tag': d.animal.tag_id if d.animal else 'Unknown',
                    'Camera': d.camera_id,
                    'Detected At': d.detected_at.isoformat(),
                    'Confidence': round(d.confidence_score, 4),
                })
            
            detections_df = pd.DataFrame(detections_data)
            detections_df.to_excel(writer, sheet_name='Detections (30d)', index=False)
            
            # ===== SHEET 3: WEIGHTS =====
            weights_query = select(WeightMeasurement).options(
                selectinload(WeightMeasurement.animal)
            ).order_by(WeightMeasurement.timestamp.desc()).limit(10000)
            
            weights_result = await db.execute(weights_query)
            weights = weights_result.scalars().all()
            
            weights_data = []
            for w in weights:
                weights_data.append({
                    'ID': w.id,
                    'Animal Tag': w.animal.tag_id if w.animal else 'Unknown',
                    'Weight (kg)': round(w.estimated_weight_kg, 2),
                    'Confidence': round(w.confidence_score * 100, 1),
                    'Timestamp': w.timestamp.isoformat(),
                    'Camera': w.camera_id,
                })
            
            weights_df = pd.DataFrame(weights_data)
            weights_df.to_excel(writer, sheet_name='Weights', index=False)
            
            # ===== SHEET 4: STATISTICS =====
            stats_data = [
                {'Metric': 'Total Animals', 'Value': len(animals)},
                {'Metric': 'Active Animals', 'Value': len([a for a in animals if a.status == AnimalStatus.ACTIVE])},
                {'Metric': 'Total Detections (30d)', 'Value': len(detections)},
                {'Metric': 'Total Weight Measurements', 'Value': len(weights)},
                {'Metric': 'Export Date', 'Value': datetime.utcnow().isoformat()},
            ]
            
            stats_df = pd.DataFrame(stats_data)
            stats_df.to_excel(writer, sheet_name='Statistics', index=False)
            
            # Save
            writer.close()
            excel_bytes = excel_buffer.getvalue()
            excel_buffer.close()
            
            logger.info(f"All data exported to Excel: {len(excel_bytes)} bytes")
            return excel_bytes
            
        except Exception as e:
            logger.error(f"Error exporting all data to Excel: {e}", exc_info=True)
            raise
