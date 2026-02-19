"""
API v1 router aggregator.

Barcha endpoint routerlarni yagona routerga birlashtiradi.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    animals,
    weights,
    live,
    detection,
    pipeline,
    cameras,
    analytics,
    reports,
    export,
    registration,
    adi,        # YANGI
    alerts,     # YANGI
)

router = APIRouter(prefix="/v1")

# Mavjud routerlar
router.include_router(animals.router)
router.include_router(weights.router)
router.include_router(live.router)
router.include_router(detection.router)
router.include_router(pipeline.router)
router.include_router(cameras.router)
router.include_router(analytics.router)
router.include_router(reports.router)
router.include_router(export.router)
router.include_router(registration.router)

# YANGI — ADI moduli
router.include_router(adi.router)
router.include_router(alerts.router)
