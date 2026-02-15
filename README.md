# 🐂 Taurus Vision - AI-Powered Livestock Monitoring System

> Real-time animal detection, identification, and health monitoring using computer vision and AI.

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![Python](https://img.shields.io/badge/python-3.11-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688)
![Docker](https://img.shields.io/badge/docker-ready-2496ED)

---

## 📋 Overview

Taurus Vision is a cutting-edge livestock monitoring system that uses AI to:
- 🎥 Detect and track animals in real-time
- ⚖️ Estimate weight automatically
- 📊 Monitor health indicators
- 🔔 Send alerts for anomalies
- 📈 Provide analytics and insights

**Target Market:** Large and medium-sized farms in Uzbekistan and Central Asia.

---

## 🏗️ Architecture
```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Cameras   │────▶│   Backend    │────▶│  Database   │
│  (RTSP/USB) │     │   (FastAPI)  │     │ (PostgreSQL)│
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  AI Engine   │
                    │  (YOLOv11)   │
                    └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   Frontend   │
                    │   (React)    │
                    └──────────────┘
```

**Tech Stack:**
- Backend: FastAPI + SQLAlchemy + PostgreSQL
- AI/ML: PyTorch + Ultralytics YOLOv11
- Frontend: React 18 + TypeScript + TailwindCSS
- Infrastructure: Docker + Docker Compose

---

## 🚀 Quick Start (5 minutes)

### Prerequisites

- Docker & Docker Compose installed
- 8GB+ RAM
- 20GB+ disk space

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/taurus-vision.git
cd taurus-vision
```

### 2. Setup Environment
```bash
# Copy environment template
cp backend/.env.example backend/.env

# Edit if needed (defaults work for development)
nano backend/.env
```

### 3. Start Services
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

### 4. Access Application

- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

---

## 📦 Project Structure
```
taurus-vision/
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/            # API endpoints
│   │   ├── core/           # Core functionality
│   │   ├── models/         # Database models
│   │   ├── services/       # Business logic
│   │   └── schemas/        # Pydantic schemas
│   ├── alembic/            # Database migrations
│   ├── ml/                 # ML models
│   └── requirements.txt    # Python dependencies
│
├── frontend/               # React application
│   ├── src/
│   │   ├── features/      # Feature modules
│   │   ├── shared/        # Shared components
│   │   └── App.tsx        # Main app
│   └── package.json       # Node dependencies
│
├── docker-compose.yml     # Docker orchestration
└── README.md             # This file
```

---

## 🛠️ Development

### Backend Development
```bash
# Enter backend container
docker-compose exec backend bash

# Run tests
pytest

# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Format code
black app/
```

### Frontend Development
```bash
# Enter frontend container
docker-compose exec frontend sh

# Install new package
npm install package-name

# Run linter
npm run lint
```

### Database Access
```bash
# Connect to database
docker-compose exec postgres psql -U taurus -d taurus_vision

# Backup database
docker-compose exec postgres pg_dump -U taurus taurus_vision > backup.sql

# Restore database
docker-compose exec -T postgres psql -U taurus taurus_vision < backup.sql
```

---

## 📊 API Endpoints

### Core Endpoints

- `GET /` - API info
- `GET /health` - Health check
- `GET /health/ready` - Readiness probe
- `GET /health/live` - Liveness probe
- `GET /metrics` - Prometheus metrics
- `GET /docs` - Swagger UI

### Animals

- `GET /api/v1/animals/` - List animals
- `POST /api/v1/animals/` - Create animal
- `GET /api/v1/animals/{id}` - Get animal
- `PUT /api/v1/animals/{id}` - Update animal
- `DELETE /api/v1/animals/{id}` - Delete animal

### Detection Pipeline

- `GET /api/v1/pipeline/status` - Pipeline status
- `POST /api/v1/pipeline/start` - Start pipeline
- `POST /api/v1/pipeline/stop` - Stop pipeline

### Live Feed

- `WS /api/v1/live/ws` - WebSocket for real-time updates

**Full API documentation:** http://localhost:8000/docs

---

## 🧪 Testing
```bash
# Run all tests
docker-compose exec backend pytest

# Run with coverage
docker-compose exec backend pytest --cov=app --cov-report=html

# Run specific test file
docker-compose exec backend pytest tests/test_api/test_animals.py

# View coverage report
open backend/htmlcov/index.html
```

---

## 🔒 Security

**Production Checklist:**

- [ ] Change default passwords in `.env`
- [ ] Generate secure `SECRET_KEY`
- [ ] Enable HTTPS (SSL/TLS)
- [ ] Configure firewall rules
- [ ] Enable rate limiting
- [ ] Setup log monitoring
- [ ] Configure backup schedule

**Security Features:**
- ✅ Security headers (X-Frame-Options, CSP, etc.)
- ✅ CORS protection
- ✅ Request logging
- ✅ Error handling
- ⏳ JWT authentication (Sprint 3)
- ⏳ API rate limiting (Sprint 5)

---

## 📈 Monitoring

### Health Checks
```bash
# Comprehensive health check
curl http://localhost:8000/health

# Kubernetes readiness
curl http://localhost:8000/health/ready

# Kubernetes liveness
curl http://localhost:8000/health/live
```

### Metrics
```bash
# Prometheus metrics
curl http://localhost:8000/metrics
```

### Logs
```bash
# View logs
docker-compose logs -f backend

# View specific log file
docker-compose exec backend cat data/logs/app.log
```

---

## 🐛 Troubleshooting

### Database connection failed
```bash
# Check database is running
docker-compose ps postgres

# Check database logs
docker-compose logs postgres

# Restart database
docker-compose restart postgres
```

### Frontend not loading
```bash
# Check frontend logs
docker-compose logs frontend

# Rebuild frontend
docker-compose up --build frontend
```

### AI model not loading
```bash
# Check model file exists
docker-compose exec backend ls -lh ml/models/

# Download model manually
docker-compose exec backend wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolo11n.pt -O ml/models/yolo11n.pt
```

---

## 🗺️ Roadmap

- [x] **Phase 1 - Foundation** (3 months)
  - [x] Sprint 1: Infrastructure ✅
  - [ ] Sprint 2: Core ML
  - [ ] Sprint 3: Backend API
  - [ ] Sprint 4: Basic Frontend
  - [ ] Sprint 5: Integration & Testing
  - [ ] Sprint 6: Real-world Testing

- [ ] **Phase 2 - Enhancement** (3 months)
  - Advanced features
  - Multi-camera support
  - Health monitoring

- [ ] **Phase 3 - AI Intelligence** (6 months)
  - Individual animal identification
  - Predictive health analytics
  - Automation

**Current Status:** Sprint 1 Complete (100%) ✅

---

## 👥 Team

- **Lead Developer:** Ismoil
- **Project:** Taurus Vision
- **Location:** Uzbekistan

---

## 📄 License

Copyright © 2026 Taurus Vision. All rights reserved.

---

## 🤝 Support

For support, email: support@taurusvision.uz

---

**Built with ❤️ in Uzbekistan 🇺🇿**