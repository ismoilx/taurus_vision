"""
Analytics Service - Taurus Vision

Provides comprehensive analytics and statistics for farm monitoring.
Generates data for dashboards, reports, and insights.

Author: Taurus Vision Team
Date: 2026-02-16
"""

from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy import select, func, and_, or_, desc, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.animal import Animal, AnimalStatus
from app.models.detection import Detection
from app.models.weight_measurement import WeightMeasurement
from app.services.camera.camera_manager import CameraManager
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class AnalyticsService:
    """
    Analytics service for farm monitoring system.
    
    Provides methods for:
    - Dashboard overview statistics
    - Weight trend analysis
    - Detection pattern analysis
    - Health metrics calculation
    - Camera performance tracking
    
    All methods are async and work with AsyncSession.
    """
    
    def __init__(self):
        """Initialize analytics service."""
        self.camera_manager = CameraManager()
    
    # =========================================================================
    # DASHBOARD OVERVIEW
    # =========================================================================
    
    async def get_dashboard_overview(
        self,
        db: AsyncSession,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive dashboard overview statistics.
        
        Args:
            db: Database session
            date_from: Start date for time-based stats (default: today)
            date_to: End date for time-based stats (default: today)
        
        Returns:
            Dictionary containing:
            - total_animals: Total number of animals
            - active_animals: Animals with status 'active'
            - total_detections: Detection counts (today, week, month, all)
            - average_weight: Current average weight
            - weight_change: Weight change percentage (last 7 days)
            - pipeline_status: Current pipeline status
            - camera_status: Camera system status
            - recent_activity: Recent detections summary
            - alerts: System alerts and warnings
        
        Example:
            >>> service = AnalyticsService()
            >>> overview = await service.get_dashboard_overview(db)
            >>> print(overview['total_animals'])
            45
        """
        logger.info("Generating dashboard overview")
        
        # Default date range: today
        if date_to is None:
            date_to = datetime.utcnow().date()
        if date_from is None:
            date_from = date_to
        
        try:
            # ===== Animal Statistics =====
            total_animals = await self._get_total_animals(db)
            active_animals = await self._get_active_animals(db)
            animals_by_status = await self._get_animals_by_status(db)
            
            # ===== Detection Statistics =====
            detections_today = await self._get_detections_count(
                db, 
                datetime.utcnow().date(),
                datetime.utcnow().date()
            )
            detections_week = await self._get_detections_count(
                db,
                datetime.utcnow().date() - timedelta(days=7),
                datetime.utcnow().date()
            )
            detections_month = await self._get_detections_count(
                db,
                datetime.utcnow().date() - timedelta(days=30),
                datetime.utcnow().date()
            )
            total_detections = await self._get_detections_count(db)
            
            # ===== Weight Statistics =====
            avg_weight = await self._get_average_weight(db)
            weight_change = await self._get_weight_change_percentage(db, days=7)
            
            # ===== System Status =====
            camera_status = self._get_camera_status()
            
            # ===== Recent Activity =====
            recent_detections = await self._get_recent_detections(db, limit=5)
            
            # ===== Alerts =====
            alerts = await self._generate_alerts(db)
            
            overview = {
                "timestamp": datetime.utcnow().isoformat(),
                "animals": {
                    "total": total_animals,
                    "active": active_animals,
                    "by_status": animals_by_status,
                },
                "detections": {
                    "today": detections_today,
                    "week": detections_week,
                    "month": detections_month,
                    "total": total_detections,
                },
                "weight": {
                    "average_kg": round(avg_weight, 2) if avg_weight else None,
                    "change_percentage_7d": round(weight_change, 2) if weight_change else None,
                },
                "system": {
                    "cameras": camera_status,
                },
                "recent_activity": recent_detections,
                "alerts": alerts,
            }
            
            logger.info(f"Dashboard overview generated successfully: {total_animals} animals, {detections_today} detections today")
            return overview
            
        except Exception as e:
            logger.error(f"Error generating dashboard overview: {e}", exc_info=True)
            raise
    
    # =========================================================================
    # WEIGHT TRENDS
    # =========================================================================
    
    async def get_weight_trends(
        self,
        db: AsyncSession,
        animal_id: Optional[int] = None,
        days: int = 30,
        aggregation: str = "daily"  # daily, weekly, monthly
    ) -> List[Dict[str, Any]]:
        """
        Get weight trend data for charting.
        
        Args:
            db: Database session
            animal_id: Specific animal ID (None = farm-wide average)
            days: Number of days to look back
            aggregation: Data aggregation level (daily/weekly/monthly)
        
        Returns:
            List of data points with:
            - date: Date string (YYYY-MM-DD)
            - average_weight: Average weight in kg
            - min_weight: Minimum weight (if multiple animals)
            - max_weight: Maximum weight (if multiple animals)
            - measurement_count: Number of measurements
            - animal_count: Number of unique animals (if farm-wide)
        
        Example:
            >>> trends = await service.get_weight_trends(db, animal_id=5, days=30)
            >>> for point in trends:
            ...     print(f"{point['date']}: {point['average_weight']} kg")
        """
        logger.info(f"Generating weight trends: animal_id={animal_id}, days={days}, aggregation={aggregation}")
        
        try:
            date_from = datetime.utcnow().date() - timedelta(days=days)
            date_to = datetime.utcnow().date()
            
            # Build query
            query = select(
                func.date(WeightMeasurement.timestamp).label('date'),
                func.avg(WeightMeasurement.estimated_weight_kg).label('avg_weight'),
                func.min(WeightMeasurement.estimated_weight_kg).label('min_weight'),
                func.max(WeightMeasurement.estimated_weight_kg).label('max_weight'),
                func.count(WeightMeasurement.id).label('measurement_count'),
                func.count(func.distinct(WeightMeasurement.animal_id)).label('animal_count')
            ).where(
                and_(
                    func.date(WeightMeasurement.timestamp) >= date_from,
                    func.date(WeightMeasurement.timestamp) <= date_to
                )
            )
            
            # Filter by animal if specified
            if animal_id is not None:
                query = query.where(WeightMeasurement.animal_id == animal_id)
            
            # Group by date
            query = query.group_by(func.date(WeightMeasurement.timestamp))
            query = query.order_by(func.date(WeightMeasurement.timestamp))
            
            result = await db.execute(query)
            rows = result.all()
            
            trends = []
            for row in rows:
                trends.append({
                    "date": row.date.isoformat(),
                    "average_weight": round(float(row.avg_weight), 2),
                    "min_weight": round(float(row.min_weight), 2),
                    "max_weight": round(float(row.max_weight), 2),
                    "measurement_count": row.measurement_count,
                    "animal_count": row.animal_count,
                })
            
            logger.info(f"Generated {len(trends)} data points for weight trends")
            return trends
            
        except Exception as e:
            logger.error(f"Error generating weight trends: {e}", exc_info=True)
            raise
    
    # =========================================================================
    # DETECTION PATTERNS
    # =========================================================================
    
    async def get_detection_patterns(
        self,
        db: AsyncSession,
        date_from: date,
        date_to: date
    ) -> Dict[str, Any]:
        """
        Analyze detection patterns for insights.
        
        Args:
            db: Database session
            date_from: Start date
            date_to: End date
        
        Returns:
            Dictionary containing:
            - detections_by_hour: 24-hour heatmap data [0-23]
            - detections_by_day: Daily counts
            - detections_by_camera: Per-camera statistics
            - top_detected_animals: Most frequently detected animals
            - detection_rate: Detections per hour average
        
        Example:
            >>> patterns = await service.get_detection_patterns(
            ...     db, date(2026, 2, 1), date(2026, 2, 16)
            ... )
            >>> print(patterns['detections_by_hour'][10])  # 10 AM
            45
        """
        logger.info(f"Analyzing detection patterns: {date_from} to {date_to}")
        
        try:
            # ===== Detections by hour =====
            hour_query = select(
                func.extract('hour', Detection.timestamp).label('hour'),
                func.count(Detection.id).label('count')
            ).where(
                and_(
                    func.date(Detection.timestamp) >= date_from,
                    func.date(Detection.timestamp) <= date_to
                )
            ).group_by('hour').order_by('hour')
            
            hour_result = await db.execute(hour_query)
            hour_rows = hour_result.all()
            
            # Initialize 24-hour array
            detections_by_hour = [0] * 24
            for row in hour_rows:
                hour = int(row.hour)
                detections_by_hour[hour] = row.count
            
            # ===== Detections by day =====
            day_query = select(
                func.date(Detection.timestamp).label('date'),
                func.count(Detection.id).label('count')
            ).where(
                and_(
                    func.date(Detection.timestamp) >= date_from,
                    func.date(Detection.timestamp) <= date_to
                )
            ).group_by('date').order_by('date')
            
            day_result = await db.execute(day_query)
            day_rows = day_result.all()
            
            detections_by_day = [
                {
                    "date": row.date.isoformat(),
                    "count": row.count
                }
                for row in day_rows
            ]
            
            # ===== Detections by camera =====
            camera_query = select(
                Detection.camera_id,
                func.count(Detection.id).label('count'),
                func.avg(Detection.confidence_score).label('avg_confidence')
            ).where(
                and_(
                    func.date(Detection.timestamp) >= date_from,
                    func.date(Detection.timestamp) <= date_to
                )
            ).group_by(Detection.camera_id).order_by(desc('count'))
            
            camera_result = await db.execute(camera_query)
            camera_rows = camera_result.all()
            
            detections_by_camera = [
                {
                    "camera_id": row.camera_id,
                    "detections": row.count,
                    "average_confidence": round(float(row.avg_confidence), 3) if row.avg_confidence else 0.0
                }
                for row in camera_rows
            ]
            
            # ===== Top detected animals =====
            top_query = select(
                Animal.tag_id,
                Animal.species,
                func.count(Detection.id).label('detection_count')
            ).select_from(Detection).join(
                Animal, Detection.animal_id == Animal.id
            ).where(
                and_(
                    func.date(Detection.timestamp) >= date_from,
                    func.date(Detection.timestamp) <= date_to
                )
            ).group_by(Animal.id, Animal.tag_id, Animal.species).order_by(
                desc('detection_count')
            ).limit(10)
            
            top_result = await db.execute(top_query)
            top_rows = top_result.all()
            
            top_detected_animals = [
                {
                    "tag_id": row.tag_id,
                    "species": row.species,
                    "detections": row.detection_count
                }
                for row in top_rows
            ]
            
            # ===== Calculate detection rate =====
            total_detections = sum(detections_by_hour)
            days_in_range = (date_to - date_from).days + 1
            hours_in_range = days_in_range * 24
            detection_rate = total_detections / hours_in_range if hours_in_range > 0 else 0
            
            patterns = {
                "date_range": {
                    "from": date_from.isoformat(),
                    "to": date_to.isoformat(),
                    "days": days_in_range
                },
                "detections_by_hour": detections_by_hour,
                "detections_by_day": detections_by_day,
                "detections_by_camera": detections_by_camera,
                "top_detected_animals": top_detected_animals,
                "statistics": {
                    "total_detections": total_detections,
                    "detection_rate_per_hour": round(detection_rate, 2),
                    "peak_hour": detections_by_hour.index(max(detections_by_hour)) if detections_by_hour else None
                }
            }
            
            logger.info(f"Detection patterns analyzed: {total_detections} detections")
            return patterns
            
        except Exception as e:
            logger.error(f"Error analyzing detection patterns: {e}", exc_info=True)
            raise
    
    # =========================================================================
    # HEALTH METRICS
    # =========================================================================
    
    async def get_health_metrics(
        self,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Calculate health-related metrics and indicators.
        
        Args:
            db: Database session
        
        Returns:
            Dictionary containing:
            - animals_by_status: Count per status
            - weight_distribution: Weight ranges and counts
            - detection_frequency: Detection patterns
            - alerts: Health warnings (weight loss, no detection)
            - risk_score: Overall health risk score (0-100)
        
        Example:
            >>> metrics = await service.get_health_metrics(db)
            >>> print(metrics['risk_score'])
            23  # Low risk
        """
        logger.info("Calculating health metrics")
        
        try:
            # ===== Animals by status =====
            animals_by_status = await self._get_animals_by_status(db)
            
            # ===== Weight distribution =====
            weight_query = select(
                case(
                    (WeightMeasurement.estimated_weight_kg < 100, "0-100kg"),
                    (WeightMeasurement.estimated_weight_kg < 200, "100-200kg"),
                    (WeightMeasurement.estimated_weight_kg < 300, "200-300kg"),
                    (WeightMeasurement.estimated_weight_kg < 400, "300-400kg"),
                    (WeightMeasurement.estimated_weight_kg >= 400, "400kg+"),
                ).label('range'),
                func.count(func.distinct(WeightMeasurement.animal_id)).label('count')
            ).group_by('range')
            
            weight_result = await db.execute(weight_query)
            weight_rows = weight_result.all()
            
            weight_distribution = {row.range: row.count for row in weight_rows}
            
            # ===== Detection frequency =====
            freq_query = select(
                Animal.tag_id,
                Animal.species,
                func.count(Detection.id).label('detection_count'),
                func.max(Detection.timestamp).label('last_detection')
            ).select_from(Animal).outerjoin(
                Detection, Animal.id == Detection.animal_id
            ).where(
                Animal.status == AnimalStatus.ACTIVE
            ).group_by(Animal.id, Animal.tag_id, Animal.species)
            
            freq_result = await db.execute(freq_query)
            freq_rows = freq_result.all()
            
            # ===== Generate alerts =====
            alerts = []
            now = datetime.utcnow()
            
            for row in freq_rows:
                # Alert: No detection in 7 days
                if row.last_detection:
                    days_since_detection = (now - row.last_detection).days
                    if days_since_detection > 7:
                        alerts.append({
                            "type": "no_detection",
                            "severity": "warning",
                            "animal_tag": row.tag_id,
                            "message": f"No detection for {days_since_detection} days",
                            "days_since_detection": days_since_detection
                        })
                else:
                    alerts.append({
                        "type": "never_detected",
                        "severity": "critical",
                        "animal_tag": row.tag_id,
                        "message": "Animal never detected by system"
                    })
            
            # ===== Weight loss alerts =====
            weight_loss_alerts = await self._detect_weight_loss(db)
            alerts.extend(weight_loss_alerts)
            
            # ===== Calculate risk score =====
            risk_score = self._calculate_risk_score(
                animals_by_status,
                alerts,
                len(freq_rows)
            )
            
            metrics = {
                "animals_by_status": animals_by_status,
                "weight_distribution": weight_distribution,
                "alerts": alerts,
                "alert_summary": {
                    "total": len(alerts),
                    "critical": len([a for a in alerts if a["severity"] == "critical"]),
                    "warning": len([a for a in alerts if a["severity"] == "warning"]),
                },
                "risk_score": risk_score,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Health metrics calculated: {len(alerts)} alerts, risk score: {risk_score}")
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating health metrics: {e}", exc_info=True)
            raise
    
    # =========================================================================
    # CAMERA PERFORMANCE
    # =========================================================================
    
    async def get_camera_performance(
        self,
        db: AsyncSession,
        camera_id: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Analyze camera performance metrics.
        
        Args:
            db: Database session
            camera_id: Specific camera ID (None = all cameras)
            days: Number of days to analyze
        
        Returns:
            Dictionary containing per-camera:
            - camera_id: Camera identifier
            - status: Current status (running/stopped)
            - uptime_percentage: Uptime over period
            - total_detections: Number of detections
            - detections_per_hour: Detection rate
            - average_confidence: Average detection confidence
            - fps: Current FPS (if running)
            - errors: Error count
        
        Example:
            >>> perf = await service.get_camera_performance(db, days=7)
            >>> for camera in perf['cameras']:
            ...     print(f"{camera['camera_id']}: {camera['uptime_percentage']}%")
        """
        logger.info(f"Analyzing camera performance: camera_id={camera_id}, days={days}")
        
        try:
            date_from = datetime.utcnow() - timedelta(days=days)
            
            # Get registered cameras from manager
            cameras = self.camera_manager.list_cameras()
            
            performance_data = []
            
            for cam_info in cameras:
                cam_id = cam_info["camera_id"]
                
                # Skip if specific camera requested
                if camera_id is not None and cam_id != camera_id:
                    continue
                
                # ===== Detection statistics =====
                detection_query = select(
                    func.count(Detection.id).label('total_detections'),
                    func.avg(Detection.confidence_score).label('avg_confidence')
                ).where(
                    and_(
                        Detection.camera_id == cam_id,
                        Detection.timestamp >= date_from
                    )
                )
                
                detection_result = await db.execute(detection_query)
                detection_row = detection_result.one_or_none()
                
                total_detections = detection_row.total_detections if detection_row else 0
                avg_confidence = float(detection_row.avg_confidence) if detection_row and detection_row.avg_confidence else 0.0
                
                # ===== Calculate detection rate =====
                hours_in_period = days * 24
                detections_per_hour = total_detections / hours_in_period if hours_in_period > 0 else 0
                
                # ===== Camera stats =====
                cam_stats = cam_info.get("stats", {})
                
                # ===== Uptime calculation (simplified) =====
                # In real system, you'd track uptime in a separate table
                # For now, we use "running" status as indicator
                uptime_percentage = 100.0 if cam_info["status"] == "running" else 0.0
                
                performance_data.append({
                    "camera_id": cam_id,
                    "status": cam_info["status"],
                    "uptime_percentage": round(uptime_percentage, 2),
                    "total_detections": total_detections,
                    "detections_per_hour": round(detections_per_hour, 2),
                    "average_confidence": round(avg_confidence, 3),
                    "fps": cam_stats.get("fps", 0.0),
                    "errors": cam_stats.get("errors", 0),
                    "total_frames": cam_stats.get("total_frames", 0)
                })
            
            result = {
                "period": {
                    "days": days,
                    "from": date_from.isoformat(),
                    "to": datetime.utcnow().isoformat()
                },
                "cameras": performance_data,
                "summary": {
                    "total_cameras": len(performance_data),
                    "running_cameras": len([c for c in performance_data if c["status"] == "running"]),
                    "total_detections": sum(c["total_detections"] for c in performance_data),
                    "average_fps": round(
                        sum(c["fps"] for c in performance_data) / len(performance_data)
                        if performance_data else 0.0,
                        2
                    )
                }
            }
            
            logger.info(f"Camera performance analyzed: {len(performance_data)} cameras")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing camera performance: {e}", exc_info=True)
            raise
    
    # =========================================================================
    # HELPER METHODS (PRIVATE)
    # =========================================================================
    
    async def _get_total_animals(self, db: AsyncSession) -> int:
        """Get total number of animals."""
        result = await db.execute(select(func.count(Animal.id)))
        return result.scalar() or 0
    
    async def _get_active_animals(self, db: AsyncSession) -> int:
        """Get number of active animals."""
        result = await db.execute(
            select(func.count(Animal.id)).where(Animal.status == AnimalStatus.ACTIVE)
        )
        return result.scalar() or 0
    
    async def _get_animals_by_status(self, db: AsyncSession) -> Dict[str, int]:
        """Get animal counts per status."""
        result = await db.execute(
            select(
                Animal.status,
                func.count(Animal.id).label('count')
            ).group_by(Animal.status)
        )
        rows = result.all()
        return {row.status.value: row.count for row in rows}
    
    async def _get_detections_count(
        self,
        db: AsyncSession,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> int:
        """Get detection count within date range."""
        query = select(func.count(Detection.id))
        
        if date_from is not None:
            query = query.where(func.date(Detection.timestamp) >= date_from)
        if date_to is not None:
            query = query.where(func.date(Detection.timestamp) <= date_to)
        
        result = await db.execute(query)
        return result.scalar() or 0
    
    async def _get_average_weight(self, db: AsyncSession) -> Optional[float]:
        """Get current average weight across all active animals."""
        # Get most recent weight for each animal
        subquery = select(
            WeightMeasurement.animal_id,
            func.max(WeightMeasurement.timestamp).label('max_timestamp')
        ).group_by(WeightMeasurement.animal_id).subquery()
        
        query = select(
            func.avg(WeightMeasurement.estimated_weight_kg)
        ).select_from(WeightMeasurement).join(
            subquery,
            and_(
                WeightMeasurement.animal_id == subquery.c.animal_id,
                WeightMeasurement.timestamp == subquery.c.max_timestamp
            )
        )
        
        result = await db.execute(query)
        avg = result.scalar()
        return float(avg) if avg else None
    
    async def _get_weight_change_percentage(
        self,
        db: AsyncSession,
        days: int = 7
    ) -> Optional[float]:
        """Calculate weight change percentage over period."""
        now = datetime.utcnow()
        date_past = now - timedelta(days=days)
        
        # Average weight now
        current_avg = await self._get_average_weight(db)
        
        # Average weight N days ago
        query = select(
            func.avg(WeightMeasurement.estimated_weight_kg)
        ).where(
            and_(
                WeightMeasurement.timestamp >= date_past - timedelta(days=1),
                WeightMeasurement.timestamp < date_past + timedelta(days=1)
            )
        )
        result = await db.execute(query)
        past_avg = result.scalar()
        past_avg = float(past_avg) if past_avg else None
        
        if current_avg and past_avg and past_avg > 0:
            change = ((current_avg - past_avg) / past_avg) * 100
            return change
        
        return None
    
    def _get_camera_status(self) -> Dict[str, Any]:
        """Get current camera system status."""
        health = self.camera_manager.get_health_status()
        return {
            "total": health["total_cameras"],
            "running": health["running_cameras"],
            "healthy": health["healthy_cameras"],
            "status": "healthy" if health["healthy_cameras"] == health["total_cameras"] else "degraded"
        }
    
    async def _get_recent_detections(
        self,
        db: AsyncSession,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get recent detection activity."""
        query = select(Detection).options(
            selectinload(Detection.animal)
        ).order_by(desc(Detection.timestamp)).limit(limit)
        
        result = await db.execute(query)
        detections = result.scalars().all()
        
        return [
            {
                "animal_tag": d.animal.tag_id if d.animal else "Unknown",
                "camera_id": d.camera_id,
                "confidence": round(d.confidence_score, 3),
                "detected_at": d.timestamp.isoformat()
            }
            for d in detections
        ]
    
    async def _generate_alerts(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """Generate system alerts."""
        alerts = []
        
        # Check for animals not detected recently
        query = select(Animal).where(Animal.status == AnimalStatus.ACTIVE)
        result = await db.execute(query)
        animals = result.scalars().all()
        
        now = datetime.utcnow()
        
        for animal in animals:
            if animal.last_detected_at is None:
                alerts.append({
                    "type": "never_detected",
                    "severity": "critical",
                    "animal_tag": animal.tag_id,
                    "message": f"Animal {animal.tag_id} never detected"
                })
            else:
                days_since = (now - animal.last_detected_at).days
                if days_since > 7:
                    alerts.append({
                        "type": "no_recent_detection",
                        "severity": "warning",
                        "animal_tag": animal.tag_id,
                        "message": f"No detection for {days_since} days",
                        "days": days_since
                    })
        
        return alerts
    
    async def _detect_weight_loss(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """Detect significant weight loss."""
        alerts = []
        
        # Get animals with weight measurements
        query = select(Animal).options(
            selectinload(Animal.weight_measurements)
        ).where(Animal.status == AnimalStatus.ACTIVE)
        
        result = await db.execute(query)
        animals = result.scalars().all()
        
        for animal in animals:
            measurements = sorted(
                animal.weight_measurements,
                key=lambda m: m.timestamp,
                reverse=True
            )
            
            if len(measurements) >= 2:
                latest = measurements[0].estimated_weight_kg
                week_ago = None
                
                # Find measurement from ~7 days ago
                one_week_ago = datetime.utcnow() - timedelta(days=7)
                for m in measurements[1:]:
                    if m.timestamp < one_week_ago:
                        week_ago = m.estimated_weight_kg
                        break
                
                if week_ago and latest < week_ago:
                    loss_percentage = ((week_ago - latest) / week_ago) * 100
                    if loss_percentage > 5:  # More than 5% loss
                        alerts.append({
                            "type": "weight_loss",
                            "severity": "warning" if loss_percentage < 10 else "critical",
                            "animal_tag": animal.tag_id,
                            "message": f"Weight loss of {loss_percentage:.1f}% in 7 days",
                            "loss_percentage": round(loss_percentage, 2),
                            "previous_weight": round(week_ago, 2),
                            "current_weight": round(latest, 2)
                        })
        
        return alerts
    
    def _calculate_risk_score(
        self,
        animals_by_status: Dict[str, int],
        alerts: List[Dict[str, Any]],
        total_animals: int
    ) -> int:
        """
        Calculate overall health risk score (0-100).
        
        0-20: Low risk
        21-50: Medium risk
        51-80: High risk
        81-100: Critical risk
        """
        if total_animals == 0:
            return 0
        
        score = 0
        
        # Status-based risk
        inactive_ratio = animals_by_status.get("sold", 0) / total_animals
        deceased_ratio = animals_by_status.get("deceased", 0) / total_animals
        score += inactive_ratio * 20
        score += deceased_ratio * 30
        
        # Alert-based risk
        critical_alerts = len([a for a in alerts if a["severity"] == "critical"])
        warning_alerts = len([a for a in alerts if a["severity"] == "warning"])
        
        score += (critical_alerts / total_animals) * 30
        score += (warning_alerts / total_animals) * 15
        
        return min(int(score), 100)
