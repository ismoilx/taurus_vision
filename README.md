```Backend:
  Language: Python 3.11
  Framework: FastAPI
  ORM: SQLAlchemy 2.0
  Database: PostgreSQL 15
  Cache: Redis 7
  Queue: Celery + Redis
  
AI/ML:
  Framework: PyTorch 2.0
  Detection: Ultralytics YOLOv8
  Recognition: DeepFace / FaceNet
  Image Processing: OpenCV 4.8
  Training: PyTorch Lightning
  
Frontend:
  Phase 1: Vanilla JS + HTML/CSS
  Phase 2: React 18 + TypeScript
  Styling: TailwindCSS
  Charts: Chart.js / Recharts
  
Infrastructure:
  Containerization: Docker + Docker Compose
  Reverse Proxy: Nginx
  Process Manager: Supervisor
  Monitoring: Prometheus + Grafana
  Logging: ELK Stack (optional)
  
Storage:
  Database: PostgreSQL
  Object Storage: MinIO (rasmlar/video)
  Backup: pg_dump + cron
```

---

🗂️ **TO'LIQ FAYL STRUKTURASI**
```
```taurus-vision/
│
├── docs/                           # HUJJATLAR
│   ├── ARCHITECTURE.md            # Arxitektura tafsiloti
│   ├── API_DOCUMENTATION.md       # API hujjatlari
│   ├── SETUP_GUIDE.md             # O'rnatish qo'llanmasi
│   ├── DEPLOYMENT_GUIDE.md        # Deploy qilish
│   ├── AI_MODEL_TRAINING.md       # AI o'qitish
│   └── CONTINUATION_GUIDE.md      # Boshqa AI uchun yo'riqnoma
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI asosiy fayl
│   │   ├── config.py              # Sozlamalar
│   │   ├── dependencies.py        # Dependency injection
│   │   │
│   │   ├── core/                  # Asosiy modullar
│   │   │   ├── __init__.py
│   │   │   ├── database.py        # DB ulanish
│   │   │   ├── security.py        # Auth (keyinroq)
│   │   │   └── logging.py         # Logging config
│   │   │
│   │   ├── models/                # Database modellar
│   │   │   ├── __init__.py
│   │   │   ├── base.py            # Base model
│   │   │   ├── animal.py          # Jonivor
│   │   │   ├── detection.py       # Aniqlash log
│   │   │   ├── weight_log.py      # Vazn tarixi
│   │   │   ├── health_record.py   # Sog'lik
│   │   │   └── task.py            # Vazifalar
│   │   │
│   │   ├── schemas/               # Pydantic schemas
│   │   │   ├── __init__.py
│   │   │   ├── animal.py
│   │   │   ├── detection.py
│   │   │   └── response.py        # Umumiy javoblar
│   │   │
│   │   ├── services/              # Biznes logika
│   │   │   ├── __init__.py
│   │   │   ├── animal_service.py
│   │   │   ├── detection_service.py
│   │   │   ├── analytics_service.py
│   │   │   └── notification_service.py
│   │   │
│   │   ├── api/                   # API endpoints
│   │   │   ├── __init__.py
│   │   │   ├── deps.py            # Dependencies
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── animals.py
│   │   │       ├── detections.py
│   │   │       ├── analytics.py
│   │   │       └── health.py
│   │   │
│   │   └── utils/                 # Yordamchi funksiyalar
│   │       ├── __init__.py
│   │       ├── image_processing.py
│   │       └── validators.py
│   │
│   ├── alembic/                   # Database migrations
│   │   ├── versions/
│   │   └── env.py
│   │
│   ├── tests/                     # Testlar
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_api/
│   │   ├── test_services/
│   │   └── test_models/
│   │
│   ├── requirements.txt
│   ├── requirements-dev.txt       # Dev dependencies
│   ├── Dockerfile
│   └── .env.example
│
├── ml/                            # AI/ML Engine
│   ├── __init__.py
│   ├── config.py                  # ML sozlamalar
│   │
│   ├── detection/                 # Obyekt aniqlash
│   │   ├── __init__.py
│   │   ├── yolo_detector.py       # YOLO wrapper
│   │   └── custom_detector.py     # Custom model
│   │
│   ├── identification/            # ID berish
│   │   ├── __init__.py
│   │   ├── face_identifier.py
│   │   └── feature_extractor.py
│   │
│   ├── analysis/                  # Tahlil
│   │   ├── __init__.py
│   │   ├── health_analyzer.py     # Sog'lik tahlili
│   │   ├── behavior_analyzer.py   # Xatti-harakat
│   │   └── weight_estimator.py    # Vazn taxmin
│   │
│   ├── training/                  # Model o'qitish
│   │   ├── __init__.py
│   │   ├── train_identifier.py
│   │   ├── train_health.py
│   │   └── data_loader.py
│   │
│   ├── models/                    # Saqlangan modellar
│   │   ├── yolov8n.pt
│   │   ├── identifier_v1.pt
│   │   └── health_classifier.pt
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── preprocessing.py
│   │   └── postprocessing.py
│   │
│   ├── requirements.txt
│   └── README.md
│
├── camera/                        # Kamera service
│   ├── __init__.py
│   ├── camera_manager.py          # Kameralarni boshqarish
│   ├── stream_handler.py          # Video oqimi
│   ├── capture_service.py         # Surat olish
│   ├── config.yaml                # Kamera sozlamalari
│   └── requirements.txt
│
├── workers/                       # Background tasks
│   ├── __init__.py
│   ├── celery_app.py             # Celery config
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── detection_tasks.py
│   │   ├── analysis_tasks.py
│   │   └── notification_tasks.py
│   └── requirements.txt
│
├── frontend/
│   ├── phase1/                    # Vanilla JS versiya
│   │   ├── index.html
│   │   ├── css/
│   │   │   └── style.css
│   │   ├── js/
│   │   │   ├── app.js
│   │   │   ├── api.js
│   │   │   └── utils.js
│   │   └── assets/
│   │
│   └── phase2/                    # React versiya
│       ├── package.json
│       ├── src/
│       │   ├── App.tsx
│       │   ├── components/
│       │   ├── pages/
│       │   ├── services/
│       │   └── utils/
│       └── public/
│
├── scripts/                       # Yordamchi skriptlar
│   ├── setup_db.sh               # Database yaratish
│   ├── run_migrations.sh         # Migration
│   ├── backup_db.sh              # Backup
│   ├── deploy.sh                 # Deploy
│   └── init_models.py            # ML modellarni yuklab olish
│
├── infrastructure/                # Infrastructure
│   ├── docker/
│   │   ├── Dockerfile.backend
│   │   ├── Dockerfile.ml
│   │   ├── Dockerfile.worker
│   │   └── Dockerfile.frontend
│   │
│   ├── docker-compose.yml        # Dev muhit
│   ├── docker-compose.prod.yml   # Production
│   │
│   ├── nginx/
│   │   ├── nginx.conf
│   │   └── sites/
│   │       └── taurus-vision.conf
│   │
│   └── monitoring/
│       ├── prometheus.yml
│       └── grafana/
│           └── dashboards/
│
├── data/                          # Ma'lumotlar (gitignore)
│   ├── images/
│   ├── videos/
│   ├── models/
│   └── logs/
│
├── .github/                       # GitHub Actions
│   └── workflows/
│       ├── tests.yml
│       └── deploy.yml
│
├── .gitignore
├── README.md                      # Asosiy README
├── LICENSE
└── CHANGELOG.md
```

---

## 🗺️ **YO'L XARITASI (Batafsil)**

### **PHASE 1: FOUNDATION (Oy 1-3)**

**Sprint 1 (2 hafta): Infrastructure**
```
□ PostgreSQL setup
□ FastAPI boilerplate
□ Docker containerization
□ Git repository setup
□ Basic logging
□ Database schema v1.0

Deliverable: Ishlaydigan API skeleton
```

**Sprint 2 (2 hafta): Core ML**
```
□ YOLO integration
□ Animal detection pipeline
□ Image preprocessing
□ Basic identification
□ Model storage setup

Deliverable: Jonivorni aniqlash ishlaydi
```

**Sprint 3 (2 hafta): Backend API v1**
```
□ Animal CRUD operations
□ Detection logging
□ API endpoints
□ Database migrations
□ Unit tests

Deliverable: REST API ishlaydi
```

**Sprint 4 (2 hafta): Basic Frontend**
```
□ HTML/CSS/JS interface
□ Animal list view
□ Detection history
□ Basic statistics
□ API integration

Deliverable: Web dashboard ishlaydi
```

**Sprint 5 (2 hafta): Integration & Testing**
```
□ Camera integration
□ End-to-end testing
□ Bug fixing
□ Documentation
□ Deployment setup

Deliverable: MVP TAYYOR ✅
```

**Sprint 6 (2 hafta): Real-world testing**
```
□ Test fermada deploy
□ Data collection
□ Performance tuning
□ User feedback

Deliverable: Production-ready v1.0
```

---

### **PHASE 2: ENHANCEMENT (Oy 4-6)**

**Sprint 7-8 (4 hafta): Advanced Features**
```
□ Weight estimation
□ Search & filtering
□ Advanced analytics
□ Export functionality
□ React frontend start

Deliverable: Advanced dashboard
```

**Sprint 9-10 (4 hafta): Multi-camera**
```
□ Multiple camera support
□ Camera management UI
□ Stream optimization
□ Load balancing

Deliverable: Scalable camera system
```

**Sprint 11-12 (4 hafta): Health Monitoring**
```
□ Behavior analysis
□ Health indicators
□ Alert system
□ Notification service

Deliverable: Health monitoring system
```

---

### **PHASE 3: AI INTELLIGENCE (Oy 7-12)**

**Sprint 13-16 (8 hafta): Custom AI Training**
```
□ Data collection & labeling
□ Custom model training
□ Health prediction
□ Behavior classification
□ Model optimization

Deliverable: Custom AI models
```

**Sprint 17-20 (8 hafta): Automation**
```
□ Task management system
□ Automated alerts
□ Feed management
□ IoT integration (sensors)

Deliverable: Semi-automated farm
```

**Sprint 21-24 (8 hafta): Advanced Analytics**
```
□ Predictive analytics
□ Trend analysis
□ Reporting system
□ Data visualization

Deliverable: Business intelligence
```

---

## 📊 **MILESTONE TRACKER**
```
Milestone 1: MVP (3 oy)
├── Jonivorni aniqlash ✅
├── Database saqlash ✅
├── API ✅
├── Basic dashboard ✅
└── 1 kamera ishlaydi ✅

Milestone 2: Production v1 (6 oy)
├── Multi-camera ✅
├── Search & filter ✅
├── Weight tracking ✅
├── React dashboard ✅
└── 100+ jonivor support ✅

Milestone 3: AI-Powered (12 oy)
├── Custom AI models ✅
├── Health prediction ✅
├── Automated alerts ✅
├── Task automation ✅
└── 1000+ jonivor support ✅




# TAURUS VISION - CONTINUATION GUIDE

## PROJECT OVERVIEW
Taurus Vision - chorvachilik fermasini raqamlashtirish tizimi.
Jonivorlarni AI orqali tanish, monitoring, health tracking.

## CURRENT STATE
- Phase: [1/2/3]
- Last completed sprint: [Sprint #]
- Working features: [ro'yxat]
- In progress: [nima ustida ishlanmoqda]

## ARCHITECTURE
[ARCHITECTURE.md linkini ko'ring]
- Backend: FastAPI + PostgreSQL
- ML: PyTorch + YOLO
- Frontend: React
- Pattern: Layered Architecture

## CODE STANDARDS
- Python: PEP 8, type hints
- Git: Conventional commits
- Tests: pytest, 80%+ coverage
- Docs: Docstrings har joyda

## SETUP INSTRUCTIONS
1. Clone repo
2. `docker-compose up`
3. Run migrations
4. Load ML models
[Batafsil SETUP_GUIDE.md da]

## CURRENT TASKS
Kanban board: [link]
Priority:
1. [Task 1]
2. [Task 2]

## KNOWN ISSUES
- [Issue 1]
- [Issue 2]

## NEXT STEPS
According to roadmap:
- [Keyingi sprint vazifasi]

## CONTACT
Owner: [Sen]
GitHub: [repo link]
Docs: [hujjat link]


# CODE STYLE EXAMPLE

"""
Module docstring - har bir faylda
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Animal
from app.schemas import AnimalCreate, AnimalResponse


class AnimalService:
    """
    Animal management service.
    
    Handles all business logic related to animals.
    """
    
    def __init__(self, db: Session):
        """
        Initialize service.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def create_animal(
        self, 
        data: AnimalCreate
    ) -> AnimalResponse:
        """
        Create new animal record.
        
        Args:
            data: Animal creation data
            
        Returns:
            Created animal object
            
        Raises:
            ValueError: If tag_id already exists
            
        Example:
            >>> service = AnimalService(db)
            >>> animal = service.create_animal(
            ...     AnimalCreate(tag_id="JNV-001")
            ... )
        """
        # Check duplicate
        existing = self.db.query(Animal).filter(
            Animal.tag_id == data.tag_id
        ).first()
        
        if existing:
            raise ValueError(f"Animal {data.tag_id} already exists")
        
        # Create
        animal = Animal(**data.dict())
        self.db.add(animal)
        self.db.commit()
        self.db.refresh(animal)
        
        return AnimalResponse.from_orm(animal)
    
    # Type hints hamma joyda
    # Docstrings hamma funksiyada
    # Error handling
    # Clear variable names
