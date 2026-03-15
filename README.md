# 🐂 TAURUS VISION
### *AI-powered chorvachilik monitoring tizimi*

> **Bu README ni o'qiyotgan AI ga:**
> Loyihani ZIP dan tahlil qil, holat hisobotini yoz, keyin REJA bo'yicha navbatdagi vazifani boshla.
> Xato qilishga haqing yo'q. Har o'zgartirishni fayl yo'li + kod bilan ko'rsat.

---

## LOYIHA HAQIDA

**Taurus Vision** — ishlaydigan ferma monitoring tizimi. Kameralar, AI, sensorlar, moliya, hodimlar — barchasi bir tizimda.

**Taurus Brain** — kelajakda shu tizim ustiga quriladigan avtonom AI miya qatlami. Kasallik bashorati, qaror qabul qilish, ferma iqtisodiyotini tushunish.

```
Taurus Vision = Ko'zlar  →  hozir ishlamoqda
Taurus Brain  = Miya     →  keyingi bosqich
```

---

## STACK

```
Backend:   FastAPI (async) + SQLAlchemy 2.0 + PostgreSQL 15 + Redis 7
Tasks:     Celery + Celery Beat (11 task moduli)
AI/ML:     YOLO26n + MobileNetV2 (128-dim embedding) + scikit-learn
Auth:      PyJWT + bcrypt + 3 rol (VIEWER / MANAGER / ADMIN)
Frontend:  React 18 + TypeScript + Vite + TailwindCSS + React Query
Docker:    8 servis (postgres, redis, backend, 3×celery, frontend, telegram-bot)
```

---

## ARXITEKTURA

```
Repository (DB) → Service (Logic) → Endpoint (HTTP)
Bu qatlamlarni hech qachon aralashtirma.
```

**Fayl joylashuvi:**
```
backend/app/models/           — 28 ta SQLAlchemy model
backend/app/schemas/          — 27 ta Pydantic v2 schema
backend/app/repositories/     — 24 ta repository (faqat DB)
backend/app/services/         — 40+ servis (biznes logika)
backend/app/services/ai/      — YOLO, MuzzleDetector, FeatureExtractor
backend/app/api/v1/endpoints/ — 35+ endpoint (faqat HTTP)
workers/tasks/                — 11 ta Celery task moduli
frontend/src/pages/           — 35+ sahifa
```

---

## AI PIPELINE

```
Kamera → YOLO26n (bbox) → MuzzleDetector (burun ROI)
       → MobileNetV2 (128-dim embedding)
       → Cosine similarity ≥ 0.85 → Jonivor ID

ADI = D×0.35 + M×0.25 + F×0.20 + W×0.20   (0-100 ball, har kecha 00:30)
```

---

## ISHGA TUSHIRISH

```bash
make up-build          # lokal (localhost:5173)
make up-server-build   # server (HTTPS)
make gen-secret        # SECRET_KEY yaratish
make test              # testlar
make migrate           # DB migratsiya
```

```
localhost:5173        → Frontend
localhost:8000/docs   → API (Swagger)
localhost:8000/health → Backend holati
```

---

## MUHIT O'ZGARUVCHILARI (backend/.env)

```env
DATABASE_URL=postgresql+asyncpg://taurus:taurus123@localhost:5432/taurus_vision
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=<make gen-secret>
YOLO_MODEL=yolo26n.pt
MUZZLE_STRICT_MODE=false
TELEGRAM_BOT_TOKEN=...
SMTP_HOST=smtp.gmail.com
SMTP_USER=...
SMTP_PASSWORD=...
```

---

## KODLASH QOIDALARI

```python
# Majburiy: async def, type hints, logger, try/except, docstring
# HECH QACHON: print(), sync DB, hardcode secret, any (TS), inline style

logger = get_logger(__name__)

async def get_animal(animal_id: int, db: AsyncSession) -> Animal:
    try:
        ...
    except EntityNotFoundError:
        raise
    except Exception as e:
        logger.error(f"error: {e}")
        raise DatabaseError(str(e))
```

---

## GITGA YUKLANMAGAN (lokal bor, kerak)

```
backend/.env
backend/ml/models/yolo26n.pt       — auto-download (Ultralytics 8.4+)
backend/ml/models/best.pt          — custom muzzle detector
backend/ml/models/prediction/      — RF + IsolationForest
```

---

## REJA — PRODUCTION TAYYORGARLIK VA TAURUS BRAIN POYDEVORI

### 1. Sifat va barqarorlik
- SMTP email yoqish (kod tayyor, faqat `.env` kerak)
- Barcha endpointlar uchun to'liq test qamrovi
- N+1 query lar optimizatsiya (selectinload tekshiruvi)
- Xato handling va logging yaxshilash

### 2. Production infratuzilma
- CI/CD pipeline (GitHub Actions: test → build → deploy)
- Backup/Restore UI (pg_dump Celery task + admin panel)
- Rate limiting production da yoqish
- Health check va uptime monitoring

### 3. Ma'lumot sifati
- Animal bulk CSV import (backend + frontend)
- Multi-tenant to'liq izolyatsiya (farm_id guard barcha query larda)
- Pydantic v2 validator larni qattiqlash
- Audit log qamrovini kengaytirish

### 4. Frontend mustahkamlash
- MilkProductionPage kengaytirish (hozir kichik)
- Error boundary va loading state yaxshilash
- Mobile responsive tekshiruv va tuzatish
- PWA offline holatni to'liq test qilish

### 5. Monitoring
- Grafana dashboard to'ldirish (asosiy KPI lar)
- Prometheus alert qoidalari
- Log aggregatsiya

### 6. Taurus Brain — Keyingi Bosqich

Yuqoridagi 5 reja bajarilgandan keyin boshlanadi.

**Falsafa:**
```
Umumiy AI = hamma narsani biladi, ammo SIZNING sigringizni ko'rmaydi
Taurus Brain = faqat sizning fermangizni biladi, lekin UNI HAQIQATAN TUSHUNADI
```

**5 qatlam:**
```
L1 KO'RISH    [MAVJUD]  YOLO + ADI + Sensor
L2 TUSHUNISH  [KERAK]   Individual baseline + Anomaly detection
L3 BASHORAT   [KERAK]   Kasallik / Og'irlik / Moliya prognozi
L4 QAROR      [KERAK]   DecisionEngine — harakat qabul qiladi
L5 NAZORAT    [KERAK]   Avtonom boshqaruv (IoT + Hodim + Moliya)
```

**Qurilishi kerak bo'lgan modullar:**
```
backend/app/services/ai/brain/
├── feature_pipeline.py    — BIRINCHI: DB → feature vektor (LSTM input)
├── animal_baseline.py     — LSTM Autoencoder (individual norm o'rganish)
├── disease_predictor.py   — XGBoost + SHAP (48-72 soat oldin bashorat)
├── weight_forecaster.py   — Prophet (og'irlik prognozi)
├── decision_engine.py     — Barcha domenlarni birlashtiradi (har 5 daqiqa)
├── financial_analyzer.py  — ROI, xarajat anomaliya, sotish vaqti
├── workforce_optimizer.py — Hodim vazifa optimal taqsimlash
└── farm_intelligence.py   — Markaziy miya (barchasini bog'laydi)
```

**Yangi API:**
```
GET  /api/v1/brain/pulse/{farm_id}
GET  /api/v1/brain/animals/{id}/score
GET  /api/v1/brain/decisions/pending
POST /api/v1/brain/decisions/{id}/approve
GET  /api/v1/brain/financial/forecast
```

**Yangi frontend:**
```
/brain              → Brain Dashboard
/brain/animals/:id  → Jonivor AI profili (AnomalyTrend, DiseaseRisk, SHAP)
```

**Sifat mezonlari:**
```
6 oy:  kasallik 48 soat oldin — 70%+ accuracy, yolg'on alarm < 15%
12 oy: kasallik bashorati — 85%+, veterinar xarajat 20% kamayadi
```

---

*"Ferma ko'radi. Miya tushunadi. Tizim harakat qiladi."*
