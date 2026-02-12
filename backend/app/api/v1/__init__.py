"""
API v1 router aggregator.

Combines all v1 endpoints into a single router.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import animals, weights, live, detection, pipeline

# Create main v1 router
router = APIRouter(prefix="/v1")

# Include all endpoint routers
router.include_router(animals.router)
router.include_router(weights.router)
router.include_router(live.router)
router.include_router(detection.router)
router.include_router(pipeline.router)

# Add more routers here as we build them:
# router.include_router(health.router)
# router.include_router(cameras.router)
# etc.