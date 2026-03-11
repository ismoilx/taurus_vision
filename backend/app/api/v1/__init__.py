"""
Taurus Vision — API v1 Router

Barcha v1 endpoint router larini birlashtiradi.

SPRINT 15-16 QO'SHIMCHA:
    training router qo'shildi — Custom YOLO training pipeline boshqaruvi.
    
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    sensors,
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
    training,          
    tasks,             
    feed,             
    finance,          
    integrations,     
    farms,             
    scales,           
    breeding,
    employees,
    milk,
    medicine,
    meat,
)

router = APIRouter(prefix="/v1")

# --- Authentication (public + protected) ---
router.include_router(auth.router)

# --- Core Farm Data ---
router.include_router(animals.public_router)   # Auth yo'q — rasmlar uchun
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

# --- Custom YOLO Training (Sprint 15-16) ---
router.include_router(training.router)

# --- Farm Tasks (Sprint 19-20) ---
router.include_router(tasks.router)

# --- Feed Management (Sprint 20) ---
router.include_router(feed.router)

# --- Finance Module (Q4) ---
router.include_router(finance.router)

# --- External Integrations (Q5) ---
router.include_router(integrations.router)

# --- Multi-Farm (Q3) ---
router.include_router(farms.router)

# --- Scale Integration (Q7) ---
router.include_router(scales.router)

# --- IoT Sensors ---
router.include_router(sensors.router)

# --- Nasl va Zotchilik (Sprint 25-26) ---
router.include_router(breeding.router)

# --- Xodimlar va Vazifalar ---
router.include_router(employees.router)

# --- Sut Ishlab Chiqarish ---
router.include_router(milk.router)

# --- Dori-Darmon Ombori ---
router.include_router(medicine.router)

# --- Go'sht Ishlab Chiqarish ---
router.include_router(meat.router)