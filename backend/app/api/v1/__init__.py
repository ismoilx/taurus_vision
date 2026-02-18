"""
API v1 router aggregator.

Combines all v1 endpoints into a single router.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    animals,
    weights,
    live,
    detection,
    pipeline,
    cameras,
    analytics,  # Sprint 3 - Analytics endpoints
    reports,    # Sprint 3 - Report generation (PDF)
    export,     # Sprint 3 - Data export (CSV, Excel)
    registration,  # Sprint 2 - Muzzle identification
)

# Create main v1 router
router = APIRouter(prefix="/v1")

# Include all endpoint routers
router.include_router(animals.router)
router.include_router(weights.router)
router.include_router(live.router)
router.include_router(detection.router)
router.include_router(pipeline.router)
router.include_router(cameras.router)

# Sprint 3 - New routers
router.include_router(analytics.router)
router.include_router(reports.router)
router.include_router(export.router)

# Sprint 2 - Identification
router.include_router(registration.router)

# Future routers:
# router.include_router(health.router)
# router.include_router(tasks.router)
# router.include_router(alerts.router)