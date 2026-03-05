"""
Comprehensive health check system.

Provides detailed health status for monitoring tools like:
- Kubernetes readiness/liveness probes
- Docker healthcheck
- Prometheus monitoring
- Load balancers
"""

import time
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings


logger = logging.getLogger(__name__)


class HealthStatus:
    """Health check status constants."""
    
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheck:
    """
    Comprehensive health check service.
    
    Checks:
    - Database connectivity and performance
    - Disk space
    - Memory usage
    - Application uptime
    - AI model availability
    """
    
    def __init__(self):
        """Initialize health checker."""
        self._start_time = datetime.utcnow()
        self._last_check_time: Optional[datetime] = None
        self._cached_status: Dict[str, Any] = {}
        self._cache_ttl = 10  # seconds
    
    async def check_all(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Perform all health checks.
        
        Args:
            db: Database session
            
        Returns:
            Complete health status report
        """
        # Use cache if recent
        if self._last_check_time:
            age = (datetime.utcnow() - self._last_check_time).total_seconds()
            if age < self._cache_ttl:
                return self._cached_status
        
        start_time = time.time()
        
        # Run all checks concurrently
        results = await asyncio.gather(
            self._check_database(db),
            self._check_disk_space(),
            self._check_memory(),
            self._check_ai_models(),
            return_exceptions=True
        )
        
        # Parse results
        db_check, disk_check, memory_check, ai_check = results
        
        # Handle exceptions
        checks = {
            "database": db_check if not isinstance(db_check, Exception) else self._error_result(str(db_check)),
            "disk": disk_check if not isinstance(disk_check, Exception) else self._error_result(str(disk_check)),
            "memory": memory_check if not isinstance(memory_check, Exception) else self._error_result(str(memory_check)),
            "ai": ai_check if not isinstance(ai_check, Exception) else self._error_result(str(ai_check)),
        }
        
        # Determine overall status
        overall_status = self._determine_overall_status(checks)
        
        # Build response
        health_report = {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds(),
            "version": settings.APP_VERSION,
            "checks": checks,
            "response_time_ms": round((time.time() - start_time) * 1000, 2),
        }
        
        # Cache result
        self._cached_status = health_report
        self._last_check_time = datetime.utcnow()
        
        return health_report
    
    async def _check_database(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Check database connectivity and performance.
        
        Tests:
        - Connection is alive
        - Query execution time
        - Connection pool status
        """
        start = time.time()
        
        try:
            # Simple query to test connection
            result = await db.execute(text("SELECT 1"))
            result.scalar()
            
            query_time = (time.time() - start) * 1000  # ms
            
            # Determine status based on query time
            if query_time < 100:
                status = HealthStatus.HEALTHY
            elif query_time < 500:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY
            
            return {
                "status": status,
                "message": "Database connection successful",
                "query_time_ms": round(query_time, 2),
                "database_url": self._mask_password(settings.DATABASE_URL),
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"Database connection failed: {str(e)}",
                "query_time_ms": None,
            }
    
    async def _check_disk_space(self) -> Dict[str, Any]:
        """
        Check disk space availability.
        
        Warning: <20% free
        Critical: <10% free
        """
        try:
            import psutil
            
            disk = psutil.disk_usage("/")
            percent_used = disk.percent
            free_gb = disk.free / (1024 ** 3)
            
            # Determine status
            if percent_used < 80:
                status = HealthStatus.HEALTHY
            elif percent_used < 90:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY
            
            return {
                "status": status,
                "message": f"{100 - percent_used:.1f}% free",
                "used_percent": round(percent_used, 1),
                "free_gb": round(free_gb, 2),
                "total_gb": round(disk.total / (1024 ** 3), 2),
            }
            
        except Exception as e:
            logger.error(f"Disk space check failed: {e}")
            return self._error_result(str(e))
    
    async def _check_memory(self) -> Dict[str, Any]:
        """
        Check memory usage.
        
        Warning: >80% used
        Critical: >90% used
        """
        try:
            import psutil
            
            memory = psutil.virtual_memory()
            percent_used = memory.percent
            available_gb = memory.available / (1024 ** 3)
            
            # Determine status
            if percent_used < 80:
                status = HealthStatus.HEALTHY
            elif percent_used < 90:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY
            
            return {
                "status": status,
                "message": f"{100 - percent_used:.1f}% available",
                "used_percent": round(percent_used, 1),
                "available_gb": round(available_gb, 2),
                "total_gb": round(memory.total / (1024 ** 3), 2),
            }
            
        except Exception as e:
            logger.error(f"Memory check failed: {e}")
            return self._error_result(str(e))
    
    async def _check_ai_models(self) -> Dict[str, Any]:
        """
        Check AI model availability.

        Global singleton orqali tekshiriladi — yangi instance yaratilmaydi,
        chunki yangi instance hech qachon initialized bo'lmaydi.
        """
        try:
            # Global singleton dan foydalanamiz
            from app.services.ai import yolo_service as _yolo_module
            instance = getattr(_yolo_module, '_yolo_service_instance', None)
            is_loaded = instance is not None and getattr(instance, '_initialized', False)

            model_path = Path(settings.ML_MODEL_PATH) / settings.YOLO_MODEL
            file_exists = model_path.exists()

            if is_loaded and file_exists:
                status  = HealthStatus.HEALTHY
                message = "AI models loaded and ready"
            elif file_exists:
                status  = HealthStatus.DEGRADED
                message = "Model file exists but not yet initialized"
            else:
                # Fayl yo'q — DEGRADED, UNHEALTHY emas (readiness bloklanmasin)
                status  = HealthStatus.DEGRADED
                message = f"Model file not found: {model_path}"

            return {
                "status":            status,
                "message":           message,
                "model_loaded":      is_loaded,
                "model_file_exists": file_exists,
                "model_name":        settings.YOLO_MODEL,
            }

        except Exception as e:
            logger.error(f"AI model check failed: {e}")
            return {
                "status":       HealthStatus.DEGRADED,
                "message":      f"Could not verify AI models: {str(e)}",
                "model_loaded": False,
            }
    
    def _determine_overall_status(self, checks: Dict[str, Dict[str, Any]]) -> str:
        """
        Determine overall system status from individual checks.

        Yangilangan logika:
        - Database UNHEALTHY → overall UNHEALTHY  (faqat DB kritik)
        - Boshqa komponent UNHEALTHY → overall DEGRADED (xizmat ishlayveradi)
        - Any DEGRADED → overall DEGRADED
        - All HEALTHY → overall HEALTHY
        """
        # Faqat database UNHEALTHY bo'lsa butun tizim UNHEALTHY hisoblanadi
        db_status = checks.get("database", {}).get("status")
        if db_status == HealthStatus.UNHEALTHY:
            return HealthStatus.UNHEALTHY

        # Disk, memory, AI uchun UNHEALTHY → DEGRADED ga tushiriladi
        non_db_statuses = [
            check.get("status")
            for key, check in checks.items()
            if key != "database"
        ]
        if HealthStatus.DEGRADED in non_db_statuses or HealthStatus.UNHEALTHY in non_db_statuses:
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY
    
    def _error_result(self, error: str) -> Dict[str, Any]:
        """Create error result."""
        return {
            "status": HealthStatus.UNHEALTHY,
            "message": f"Check failed: {error}",
        }
    
    def _mask_password(self, url: str) -> str:
        """Mask password in database URL for logging."""
        import re
        return re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)
    
    def get_uptime(self) -> timedelta:
        """Get application uptime."""
        return datetime.utcnow() - self._start_time


# Global instance
health_checker = HealthCheck()