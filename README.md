# 🐄 Taurus Vision

**AI-powered livestock monitoring system** — Chorva mollari uchun real-vaqt kuzatuv tizimi.

YOLO11 yordamida har bir jonivorni avtomatik aniqlash, vazn hisoblash va tarixini saqlash.

---

## 🚀 Tezkor ishga tushirish

### Talablar
- Docker & Docker Compose
- Git

### 1. Klonlash
```bash
git clone https://github.com/your-org/taurus-vision.git
cd taurus-vision
```

### 2. YOLO modelini tayyorlash
```bash
# Agar yolo11n.pt.1 va yolo11n.pt.2 bo'lsa (GitHub LFS muammo):
cat backend/ml/models/yolo11n.pt.1 backend/ml/models/yolo11n.pt.2 > backend/ml/models/yolo11n.pt
```

### 3. Ishga tushirish
```bash
docker compose up -d
```

### 4. Ochish
| Xizmat | URL |
|--------|-----|
| 🌐 Frontend | http://localhost:5173 |
| 📚 API Docs | http://localhost:8000/docs |
| ❤️ Health | http://localhost:8000/health |

---

## 📋 Asosiy imkoniyatlar

- **Real-vaqt aniqlash** — YOLO11 orqali jonivorna avtomatik aniqlash
- **Vazn hisoblash** — Bounding box asosida vazn taxmin qilish
- **WebSocket** — Live feed real-vaqt yangilanadi
- **Pipeline boshqaruvi** — Start/Stop API orqali
- **Jonivor CRUD** — Qo'shish, tahrirlash, status o'zgartirish
- **Vazn tarixi** — Har bir jonivor uchun grafik

---

## 🏗️ Arxitektura

```
Frontend (React)  ←→  Backend (FastAPI)  ←→  PostgreSQL
                           ↕
                      YOLO Pipeline
                           ↕
                    SimulatedCamera / RTSP
```

**Tech stack:**
- Backend: FastAPI + SQLAlchemy 2.0 + PostgreSQL
- Frontend: React 18 + TypeScript + TailwindCSS
- AI: Ultralytics YOLO11 + OpenCV
- Infrastructure: Docker + Docker Compose

---

## 📁 Struktura

```
taurus-vision/
├── backend/          # FastAPI backend
│   ├── app/
│   │   ├── api/      # Endpoints
│   │   ├── core/     # DB, health, metrics
│   │   ├── models/   # SQLAlchemy models
│   │   ├── schemas/  # Pydantic schemas
│   │   ├── services/ # Biznes logika
│   │   └── repositories/ # DB operatsiyalari
│   ├── alembic/      # Migrations
│   └── ml/           # YOLO modeli va test video
├── frontend/         # React dashboard
│   └── src/
│       ├── features/ # Live feed
│       └── shared/   # Components, hooks, types
└── docs/             # Hujjatlar
```

---

## 🔧 Konfiguratsiya

```bash
cp backend/.env.example backend/.env
# .env faylini o'z sozlamalaringiz bilan to'ldiring
```

Asosiy sozlamalar:

| Parametr | Default | Tavsif |
|----------|---------|--------|
| `DATABASE_URL` | `postgresql://...` | PostgreSQL ulanish |
| `YOLO_MODEL` | `yolo11n.pt` | Model fayli |
| `DETECTION_CONFIDENCE` | `0.5` | Aniqlash chegarasi |
| `CAMERA_FPS` | `10` | Kadrlar/sekund |

---

## 📡 API

```
GET    /api/v1/animals/           # Jonivorlar ro'yxati
POST   /api/v1/animals/           # Yangi jonivor
GET    /api/v1/animals/{id}       # Bitta jonivor
PATCH  /api/v1/animals/{id}       # Tahrirlash
GET    /api/v1/weights/animal/{id} # Vazn tarixi

POST   /api/v1/pipeline/start     # Pipeline ishga tushirish
POST   /api/v1/pipeline/stop      # To'xtatish
GET    /api/v1/pipeline/status    # Holat

WS     /api/v1/live/ws            # WebSocket live feed
GET    /health                    # Health check
GET    /metrics                   # Prometheus metrics
```

---

## 🗺️ Yo'l xaritasi

| Phase | Sprint | Holat |
|-------|--------|-------|
| Phase 1 | 1-5: MVP | ✅ Tugallandi |
| Phase 1 | 6: Real-world test | 🔄 Jarayonda |
| Phase 2 | 7-12: Advanced features | ⏳ Rejalashtirilgan |
| Phase 3 | 13-24: Custom AI | ⏳ Rejalashtirilgan |

---

## 📄 Litsenziya

MIT License — see [LICENSE](LICENSE)