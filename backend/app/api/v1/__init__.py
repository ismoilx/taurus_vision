"""
Taurus Vision — API v1 Router

Barcha v1 endpoint router larini birlashtiradi.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
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
    adi,
    alerts,
    health,
    notifications,
    behavior,
    predictions,
)

router = APIRouter(prefix="/v1")

# --- Authentication (public + protected) ---
router.include_router(auth.router)

# --- Core Farm Data ---
router.include_router(animals.router)
router.include_router(weights.router)
router.include_router(detection.router)
router.include_router(registration.router)

# --- Live Monitoring ---
router.include_router(live.router)
router.include_router(pipeline.router)
router.include_router(cameras.router)

# --- Analytics & Reporting ---
router.include_router(analytics.router)
router.include_router(reports.router)
router.include_router(export.router)

# --- ADI & Alerts ---
router.include_router(adi.router)
router.include_router(alerts.router)

# --- Health Records ---
router.include_router(health.router)

# --- Notifications ---
router.include_router(notifications.router)

# --- Behavior Analysis (Sprint 11-12) ---
router.include_router(behavior.router)

# --- Health Predictions (Sprint 13-14) ---
router.include_router(predictions.router)