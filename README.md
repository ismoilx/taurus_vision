# 🐂 TAURUS VISION — AI-Powered Farm Monitoring System

> **Bu fayl loyihani davom ettiruvchi har qanday AI uchun asosiy yo'riqnoma.**
> **Ushbu README ni to'liq o'qigan har qanday AI loyihani bittada tushunishi va mukammal davom ettirishi shart.**

---

## ══════════════════════════════════════════════════════════
## 🤖 AI MASTER PROMPT — har yangi chat boshida ishlatiladi
## ══════════════════════════════════════════════════════════

> Quyidagi matnni to'liq nusxalab, loyihaning ZIP fayli bilan birga yangi chatga yuboring.

---

```
Sen Taurus Vision loyihasining Senior Full-Stack + AI/ML muhandisisisan.
Mening dasturchilikdan hech qanday bilimim yo'q, shuning uchun har narsani
oddiy tilda tushuntir va har o'zgartirishni aniq ko'rsat.
Xato qilishga haqing yo'q. Ishonchli, aniq, professional ishlaysan.

Senga loyihaning GitHub ZIP faylini beraman.
Avval uni tahlil qil, keyin xatolarni tuzat, keyin davom ettir.

━━━ QADAM 1: LOYIHANI O'QIGIN (hech narsa yozma) ━━━

Quyidagi fayllarni birin-ketin ko'rib chiq:
• backend/app/main.py — qaysi servislar init bo'ladi, nima tayyor
• backend/app/models/ — barcha DB modellari
• backend/app/services/ — qaysi servislar bor va nima qiladi
• backend/app/api/v1/endpoints/ — barcha API endpointlar
• frontend/src/pages/ — barcha sahifalar va ularning holati
• frontend/src/App.tsx — routing, layout
• workers/tasks/ — background tasklar
• docker-compose.yml — servislar konfiguratsiyasi

Fayl kommentlari va docstringlardagi "Sprint X" yozuvlari orqali
loyiha qayerda to'xtaganini aniqla (lekin sprint raqamlarini
muhim deb hisoblama — asl holat fayllar mazmunidan aniqlanadi).

━━━ QADAM 2: HOLAT HISOBOTI YOZ ━━━

Tahlil tugagach FAQAT quyidagi formatda yoz:

┌─────────────────────────────────────────────────┐
│ TAURUS VISION — HOZIRGI HOLAT                   │
├─────────────────────────────────────────────────┤
│ ✅ TO'LIQ ISHLAYDI:                             │
│   • [aniq nimalar tayyor]                        │
│                                                  │
│ 🔧 ANIQ XATOLAR:                                │
│   • fayl.py:qator — xato tavsifi                │
│                                                  │
│ 🚧 YARIM TAYYOR:                                │
│   • [boshlanган lekin tugallanmagan narsalar]    │
│                                                  │
│ 📋 KEYINGI MANTIQIY QADAM:                      │
│   • [nima qilinishi kerak]                       │
└─────────────────────────────────────────────────┘

━━━ QADAM 3: XATOLARNI TUZAT ━━━

Har xato uchun:
1. "X fayldagi Y qatorda Z xato bor, chunki ..."
2. To'g'ri kodni ko'rsat
3. Foydalanuvchiga nima o'zgartirishni ayt

━━━ QADAM 4: LOYIHANI DAVOM ETTIR ━━━

Mantiqiy navbatdagi featureni yoz. Har doim bu tartibda:
  backend model (agar kerak) →
  schema (Pydantic) →
  repository (DB queries) →
  service (biznes logika) →
  endpoint (API) →
  frontend (sahifa/komponent)

══════════════════════════════════
ARXITEKTURA — O'ZGARMAYDIGAN QOIDALAR
══════════════════════════════════

BACKEND STACK:
• FastAPI (async) — web framework
• SQLAlchemy 2.0 (async) — ORM, FAQAT async operatsiyalar
• PostgreSQL 15 — asosiy ma'lumotlar bazasi
• Redis 7 — cache + Celery broker
• Celery + Beat — background va scheduled tasklar
• PyJWT + bcrypt — JWT auth
• Pydantic v2 — validatsiya va schemalar
• Ultralytics YOLO26 — real-time jonivor aniqlash
• MobileNetV2 — animal embedding (128-dim)
• scikit-learn — cosine similarity, health ML

FRONTEND STACK:
• React 18 + TypeScript (strict)
• Vite — build tool
• TailwindCSS — styling (FAQAT class, inline style ishlatma)
• React Query (@tanstack/react-query) — server state
• React Router v6 — routing
• Recharts — grafiklar
• Lucide React — ikonlar
• apiFetch() — barcha API chaqiruvlar shu orqali (JWT auto-inject)

3 QATLAMLI ARXITEKTURA (majburiy):
  Repository (faqat DB) → Service (faqat biznes logika) → Endpoint (faqat HTTP)
  Bu qatlamlarni HECH QACHON aralashtiirma.

FAYL JOYLASHUVI (qat'iy):
  backend/app/models/         — SQLAlchemy ORM modellari
  backend/app/schemas/        — Pydantic request/response
  backend/app/repositories/   — Faqat SELECT/INSERT/UPDATE/DELETE
  backend/app/services/       — Biznes qoidalar, hisob-kitoblar
  backend/app/services/ai/    — YOLO, embedding, muzzle detector
  backend/app/api/v1/endpoints/ — HTTP handler lar
  workers/tasks/              — Celery async tasklar
  frontend/src/pages/         — To'liq sahifalar
  frontend/src/features/      — Feature modullar
  frontend/src/shared/        — Qayta ishlatiladigan komponentlar

══════════════════════════════════
LOYIHA MAQSADI VA DOMENNI TUSHUNISH
══════════════════════════════════

Taurus Vision ferma egasiga quyidagilarni beradi:

1. IDENTIFIKATSIYA: Har bir jonivor burun belgisi orqali taniladi.
   Pipeline: kamera kadr → YOLO (animal bbox) → MuzzleDetector (burun ROI)
   → MobileNetV2 (128-dim embedding) → cosine similarity > 0.85 → ID tasdiqlandi

2. ADI (Animal Daily Index): Kunlik 0-100 ball.
   Komponentlar: deteksiya soni × harakat × yem × og'irlik stabilligi
   < 30 → CRITICAL alert | 30-50 → WARNING | 50+ → SALOM

3. OG'IRLIK KUZATUVI: Kamera orqali vazn taxmini (YOLO bbox area-based).
   Haqiqiy tarozi bilan kalibrlash imkoni bor.

4. SENSORLAR: IoT qurilmalar (harorat, namlik, CO2) real-time yozuv.

5. ALERTLAR: Ko'rinmaslik (>24h), og'irlik tushishi (>5%), past ADI, sensor anomaliya.

6. HISOBOTLAR: PDF (ReportLab) va Excel (openpyxl) eksport.

DATABASE ALOQALAR:
  Animal ─┬─ Detection (har bir YOLO frame)
          ├─ WeightMeasurement (filtrlangan og'irlik)
          ├─ HealthRecord (veterinar yozuvlari)
          ├─ HealthPrediction (ML prognozi)
          ├─ ADILog (kunlik faollik)
          ├─ Alert (ogohlantirishlar)
          ├─ AnimalEmbedding (AI vektori)
          └─ FeedRecord (oziq-ovqat)
  Camera ── Detection
  SensorReading (mustaqil)
  FarmTask (mustaqil)
  User ── AuditLog
  Notification (mustaqil)
  TrainingRun (model o'qitish tarixi)

WEBSOCKET XABARLARI:
  {"type": "detection", "camera_id": "CAM-01", "animal_id": 5, "confidence": 0.94}
  {"type": "alert", "animal_id": 3, "severity": "critical", "message": "..."}
  {"type": "weight", "animal_id": 7, "weight_kg": 245.3}
  {"type": "sensor", "sensor_id": "SEN-01", "temperature": 22.5}

══════════════════════════════════
KODLASH STANDARTLARI
══════════════════════════════════

PYTHON (majburiy):
• Barcha funksiyalar async def
• Type hints har joyda: def func(x: int) -> str
• logger = get_logger(__name__) — har faylda
• try/except — har servis metodida
• Custom exception: EntityNotFoundError, BusinessRuleViolationError, va h.k.
• Docstring: har public funksiyada (Args + Returns + Raises)
• N+1 muammosi: selectinload() / joinedload() ishlatiladi

TYPESCRIPT (majburiy):
• any ishlatma — hamma narsa typed bo'lsin
• useQuery / useMutation — barcha server operatsiyalar
• apiFetch<T>() — barcha API chaqiruvlar
• Props interface har komponentda

NIMA QILMA:
• print() yozma — faqat logger
• Sync DB operatsiya — faqat async/await
• Hardcode URL/secret — faqat config/settings
• localStorage (artifacts da ishlamaydi)
• Mavjud arxitekturani buzma — faqat kengayt
• Sprint raqami kod ichiga yozma

══════════════════════════════════
GITGA YUKLANMAGAN FAYLLAR (lokalda bor, ishlatilmoqda)
══════════════════════════════════

Quyidagilar GitHub da yo'q lekin loyihada ishlatilayapti.
Ular mavjud va ishlaydi deb hisob:

• backend/.env — JWT_SECRET, DATABASE_URL, API keys
• backend/ml/models/yolo26n.pt — asosiy YOLO modeli (~6MB)
• backend/ml/models/best.pt — muzzle detector modeli
• backend/ml/models/feature_extractor.pt — embedding modeli
• data/images/ — upload qilingan rasmlar
• data/videos/ — kamera video fragmentlari
• barcha __pycache__/, node_modules/, .venv/

══════════════════════════════════
MUHIT O'ZGARUVCHILARI (asosiylar)
══════════════════════════════════

DATABASE_URL=postgresql+asyncpg://taurus:taurus123@localhost:5432/taurus_vision
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=<jwt_secret_key>
DEBUG=True
YOLO_MODEL=yolo26n.pt
MUZZLE_MODEL_PATH=./ml/models/best.pt
MUZZLE_STRICT_MODE=False  (True bo'lsa best.pt topilmasa xato beradi)
TRAINING_COLLECTION_ENABLED=True
TRAINING_FRAMES_DIR=./data/training_frames

══════════════════════════════════
ISHGA TUSHIRISH
══════════════════════════════════

docker-compose up --build    → hammasi
localhost:5173               → frontend
localhost:8000/docs          → API dokumentatsiya
localhost:8000/health        → tizim holati

━━━ TAYYOR. ZIP faylni ber, men tahlilni boshlaymanq ━━━
```

---

## ══════════════════════════════════════════════════════════
## 📋 LOYIHA TO'LIQ TAFSILOTI (qo'shimcha ma'lumot)
## ══════════════════════════════════════════════════════════

### 🎯 Maqsad

Chorvachilik fermalarini raqamlashtirish — sigir, qo'y, echki va boshqa hayvonlarni
kamera orqali kuzatish, AI yordamida sog'lig'ini nazorat qilish, ferma egasiga
real-time ma'lumot berish.

### 🏗️ Arxitektura diagrammasi

```
[Kameralar / USB / RTSP]
        │
        ▼
[Detection Pipeline]  ←─ YOLO26n ─→ [MuzzleDetector] ─→ [FeatureExtractor]
        │                                                        │
        ▼                                                        ▼
[PostgreSQL DB] ←──── [FastAPI Backend] ───────────→ [AnimalEmbedding]
        │                    │
        ▼                    ▼
[Celery Workers]      [WebSocket Manager]
   (ADI, Alert)              │
                             ▼
                      [React Frontend]
                      (18 sahifa, charts)
```

### 📊 Mavjud frontend sahifalar

| Yo'l | Sahifa | Maqsad |
|------|--------|--------|
| `/` | Dashboard | 6 karta: turlar, sog'liq, rivojlanish, ADI trend, diqqat, vazn |
| `/animals` | Jonivorlar | Ro'yxat, qidiruv, filtr, qo'shish |
| `/animals/:id` | Tafsilot | Bir jonivorning to'liq tarixi |
| `/live` | Live Feed | Real-time kamera + WebSocket |
| `/cameras` | Kameralar | RTSP/USB kamera boshqaruvi |
| `/health` | Sog'liq | Veterinar yozuvlari |
| `/predictions` | Prognoz | ML sog'liq bashorati |
| `/behavior` | Xatti-harakat | Harakat tahlili |
| `/adi` | ADI Monitor | Kunlik faollik indeksi |
| `/analytics` | Tahlil | Umumiy statistika, grafiklar |
| `/reports` | Hisobotlar | PDF/Excel yuklab olish |
| `/alerts` | Ogohlantirishlar | Aktiv va tarixiy alertlar |
| `/notifications` | Bildirishnomalar | Tizim xabarlari |
| `/sensors` | Sensorlar | IoT qurilmalar, harorat/namlik |
| `/feed` | Oziq-ovqat | Yem sarfi kuzatuvi |
| `/tasks` | Vazifalar | Ferma ish ro'yxati |
| `/training` | AI O'qitish | YOLO model fine-tuning UI |
| `/users` | Foydalanuvchilar | Admin panel |

### 🤖 AI/ML pipeline tafsiloti

**YOLO26n** (Ultralytics 8.4+, 2025):
- Input: 640×640 frame
- Output: bounding boxes + confidence + class_id
- class 19 = cow, class 17 = horse, class 18 = sheep
- CPU uchun optimallashtirilgan, ~43% tezroq YOLO8 dan

**MuzzleDetector** (best.pt — custom trained):
- Input: YOLO bbox crop (jonivor qismi)
- Output: burun ROI bounding box
- MUZZLE_STRICT_MODE=False → topilmasa fallback heuristik

**FeatureExtractor** (MobileNetV2):
- Input: burun ROI crop (224×224)
- Output: 128-dim float32 vector
- DB da AnimalEmbedding jadvalida saqlanadi

**Identifikatsiya:**
- Yangi embedding ↔ barcha mavjud embeddinglar cosine similarity
- Threshold: 0.85 (sozlanadi)
- Ko'p embedding bo'lsa: average pooling strategiyasi

**ADI hisoblash (adi_service.py):**
```
ADI = (D × 0.35) + (M × 0.25) + (F × 0.20) + (W × 0.20)
  D = deteksiya chastotasi (bugungi / o'rtacha)
  M = harakat intensivligi (bbox displacement)
  F = yem iste'moli (FeedRecord ga asoslanadi)
  W = og'irlik stabilligi (keskin o'zgarish → kamayadi)
Celery Beat: har kecha 00:30 UTC
```

### 🔐 Xavfsizlik

- JWT Bearer token (access + refresh)
- bcrypt parol xeshlash
- RateLimitMiddleware (100 req/min, DEBUG da o'chirilgan)
- SecurityHeadersMiddleware (X-Frame-Options, CSP, va h.k.)
- CORS: faqat ruxsat berilgan originlar
- Admin operatsiyalar: CurrentAdmin dependency

### 📦 Docker servislari

```yaml
services:
  postgres:  localhost:5432
  redis:     localhost:6379
  backend:   localhost:8000
  worker:    (celery)
  beat:      (celery-beat)
  frontend:  localhost:5173 (dev) / nginx (prod)
  prometheus: localhost:9090
  grafana:   localhost:3001
```

---

*Taurus Vision — Chorvachilik kelajagi, sun'iy intellekt bilan*
*Bu README faylni o'zgartirma — loyiha uchun doimiy yo'riqnoma*

---

## ══════════════════════════════════════════════════════════
## 🎯 LOYIHANING TO'LIQ MANZILI — AI NIMAGA QARAB ISHLAYDI
## ══════════════════════════════════════════════════════════

> Bu bo'lim AI uchun "nishon" dir. Hozir nima bor, nima qilinishi kerak —
> AI har doim shu xaritaga qarab keyingi qadamni o'zi tanlaydi.

---

### 🗺️ FEATURE MAP — To'liq mahsulot ko'rinishi

Quyidagi jadval loyihaning BARCHA feature larini ko'rsatadi.
AI har chat boshida fayllarni tekshirib, `[TAYYOR]` / `[YARIM]` / `[YO'Q]`
holatini o'zi aniqlaydi va mantiqan keyingisini qurishni boshlaydi.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOK A — POYDEVOR (Infrastructure + Auth)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
A1  FastAPI + PostgreSQL + Redis + Docker           → ishga tushirish
A2  JWT Auth (login/logout/refresh)                 → xavfsizlik
A3  3 rol: VIEWER / MANAGER / ADMIN                 → ruxsatlar
A4  Celery + Beat (scheduled tasks)                 → background ishlar
A5  WebSocket manager (real-time xabarlar)          → jonli yangilanish
A6  Prometheus + Grafana (monitoring)               → server holati
A7  Nginx reverse proxy (prod uchun)                → deploy

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOK B — JONIVORLAR BOSHQARUVI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B1  Jonivor CRUD (qo'shish, tahrirlash, o'chirish)  → asosiy ma'lumotlar
B2  Tag ID tizimi (JNV-001 format)                  → noyob ID
B3  Jonivor holati (active/sick/sold/deceased)      → hayot sikli
B4  Jonivor tafsilot sahifasi (barcha tarixi)       → to'liq profil
B5  Foto yuklash va profil rasm                     → vizual ID
B6  Ko'p jonivor import (CSV dan)                   → tez yuklash
B7  Jonivor eksport (Excel/PDF ro'yxat)             → hisobot

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOK C — KAMERA VA REAL-TIME DETECTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
C1  RTSP IP kamera ulash                            → professional kameralar
C2  USB webcam ulash                                → oddiy kameralar
C3  Simulyatsiya rejimi (haqiqiy kamerasiz test)    → ishlab chiqish uchun
C4  YOLO26n real-time detection (30 FPS target)     → jonivor aniqlash
C5  Detection natijalarini DB ga yozish             → tarix
C6  Live feed sahifasi (WebSocket stream)           → jonli kuzatuv
C7  Ko'p kamera bir vaqtda (CameraManager)          → katta ferma
C8  Kamera sog'lig'ini tekshirish (Celery, 5 daqiqa) → uzilishlarni bilish

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOK D — AI IDENTIFIKATSIYA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
D1  MuzzleDetector — burun regionini crop qilish    → prep bosqichi
D2  MobileNetV2 — 128-dim embedding yaratish        → "barmoq izi"
D3  Cosine similarity (≥0.85) — kimligini topish    → identifikatsiya
D4  Embedding DB da saqlash (AnimalEmbedding)       → o'rganish
D5  Yangi jonivor uchun embedding yig'ish (≥5 rasm) → ro'yxatdan o'tish
D6  Identifikatsiya natijasini detectionga bog'lash  → to'liq tarix
D7  Manual embedding tasdiqlash (MANAGER)           → sifat nazorat

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOK E — OG'IRLIK KUZATUVI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
E1  YOLO bbox area → vazn taxmini (kalibrlangan)    → avtomatik o'lchov
E2  WeightMeasurement DB yozuvi                     → tarix
E3  O'sish sur'ati hisoblash (kg/kun)               → rivojlanish
E4  Og'irlik grafigi (jonivor tafsilot sahifasida)  → vizual
E5  Kutilgan og'irlik vs haqiqiy (tur standartlari) → qiyoslov
E6  Keskin tushish → avtomatik alert (>5% bir hafta) → erta ogohlantirish

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOK F — SOGLIQ VA VETERINAR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
F1  HealthRecord CRUD (kasallik, dori, profilaktika) → tibbiy tarix
F2  Vaksinatsiya jadval va eslatmalar                → profilaktika
F3  Karantin holati boshqaruvi                       → izolyatsiya
F4  3-model ensemble: RuleEngine + RF + IsolationForest → sog'liq bashorati
F5  Xavf darajasi: low/moderate/high/critical        → prioritet
F6  30-kunlik xavf trend grafigi                     → kuzatuv
F7  "Darhol tekshiring" tavsiyalari (AI asosida)     → harakat rejasi

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOK G — ADI (Animal Daily Index)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
G1  Kunlik ADI hisoblash (0-100 ball)               → asosiy ko'rsatkich
    Formula: 35%×deteksiya + 25%×harakat + 20%×yem + 20%×og'irlik stabilligi
G2  ADI trendi grafigi (30/60/90 kun)               → uzoq muddatli kuzatuv
G3  ADI taqsimoti (poda bo'yicha)                   → umumiy holat
G4  Celery Beat: har kecha 00:30 UTC avtomatik      → hisoblash
G5  ADI Monitoring sahifasi (to'liq dashboard)      → nazorat markazi

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOK H — XATTI-HARAKAT TAHLILI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
H1  4 komponent: faollik, oziqlanish, harakat, ijtimoiy → to'liq obraz
H2  Zona aniqlash: oziqlanish/dam olish/suv ichish      → fazoviy tahlil
H3  Anomaliya aniqlash (normadan chetlashish)            → erta signal
H4  Poda umumiy holati (HerdBehaviorSummary)            → bir qarashda ko'rish
H5  24h / 48h / 72h tahlil oynasi                       → moslashuvchan

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOK I — ALERTLAR VA BILDIRISHNOMALAR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
I1  Avtomatik alertlar:
     • >24h ko'rinmagan jonivor     → "Ko'rinmaydi"
     • ADI < 30                     → "Faollik keskin tushdi"
     • Og'irlik >5% tushdi          → "Vazn muammosi"
     • Sensor anomaliya (harorat)   → "Muhit xavfli"
     • Sog'liq prognozi: high/critical → "Veterinar kerak"
I2  Alert darajasi: INFO / WARNING / CRITICAL         → ustuvorlik
I3  Alert yopish va izoh qoldirish (MANAGER)          → boshqarish
I4  Bildirishnoma tizimi (in-app)                     → xabar
I5  Email bildirishnoma (kelajak)                     → tashqi kanal

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOK J — IoT SENSORLAR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
J1  SensorReading yozuvlari (harorat, namlik, CO2)   → muhit kuzatuvi
J2  Normal diapazon tekshiruvi:
     Harorat: 38.0–39.5°C, Yurak: 40–80 bpm          → qoramol standarti
J3  Anomaliya aniqlash → avtomatik alert              → tezkor javob
J4  Real-time sensor dashboard (30s yangilanish)      → jonli monitoring
J5  Sensor qurilmalar holati (online/offline)         → qurilma boshqaruvi

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOK K — OZIQ-OVQAT BOSHQARUVI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
K1  Yem turlari va ombor (FeedStock)                  → inventar
K2  Oziqlantiruv yozuvlari (FeedRecord)               → sarflanish tarixi
K3  Kam qolgan yem haqida ogohlantirish               → erta to'ldirish
K4  Ombor to'ldirish operatsiyasi (restock)           → kirim
K5  Yem sarfi tahlili (oylik/yillik trend)            → xarajat nazorat

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOK L — FERMA VAZIFALARI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L1  FarmTask CRUD (vazifa yaratish, bajarish, yopish) → ish ro'yxati
L2  Vazifa holati: pending/in_progress/done/overdue   → nazorat
L3  Muddatli eslatmalar (deadline tracking)           → vaqt nazorat
L4  Vazifalarga jonivor/kamera bog'lash               → kontekst

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOK M — HISOBOTLAR VA EKSPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
M1  PDF hisobot: ferma umumiy holati (ReportLab)     → professional hujjat
M2  Excel eksport: jonivorlar ro'yxati (openpyxl)    → ma'lumot tahlil
M3  CSV eksport: detection tarixi                    → ham yoqimli
M4  Davr tanlash: oxirgi 7/30/90 kun yoki custom     → moslashuvchan
M5  Hisobot shablonlari (tur bo'yicha)               → tezkor yaratish

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOK N — TAHLIL VA STATISTIKA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
N1  Poda statistikasi KPI lar                        → boshqacha ko'rish
N2  ADI trendi, o'sish regressiyasi, xatti-harakat   → tab 2 trendlar
N3  Davr-davr taqqoslash (bu oy vs o'tgan oy)        → o'sish o'lchash
N4  Ko'p jonivor taqqoslash                          → individual farq
N5  Deteksiya soatlik/kunlik naqshlari               → faollik vaqti
N6  Kamera samaradorligi tahlili                     → qurilma ROI
N7  Avtomatik insights ("Bu hafta 3 jonivor ADI tushdi") → aqlli xulosalar
N8  Sog'liq metrikalar: xavf balli taqsimoti         → risk panorama

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOK O — AI MODEL O'QITISH (Custom YOLO)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
O1  FrameCollector: kameradan avtomatik kadr yig'ish → dataset
O2  DatasetBuilder: YOLO format dataset yaratish     → o'qitish tayyor
O3  TrainingPipeline: YOLO fine-tuning (CPU safe)    → custom model
O4  mAP50 taqqoslov: yangi model yaxshiroqmi?        → sifat nazorat
O5  Model deploy: avtomatik yoki qo'lda tasdiqlash   → production
O6  Training sahifasi: progress, metrikalar, deploy UI → vizual boshqaruv

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOK P — FOYDALANUVCHILAR VA XAVFSIZLIK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P1  Foydalanuvchi CRUD (admin tomonidan)             → hisob boshqaruvi
P2  3 rol: VIEWER (ko'rish) / MANAGER (boshqarish) / ADMIN (hammasi)
P3  Parol o'zgartirish                               → xavfsizlik
P4  Audit log: kim, nima qildi, qachon               → tekshiruv
P5  Session boshqaruvi (access + refresh token)      → seans

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOK Q — KELAJAK FEATURE LAR (hozircha yo'q, keyinroq)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Q1  📱 PWA / Mobile-responsive dizayn               → telefon bilan ishlatish
Q2  📧 Email / SMS bildirishnomalar                 → tashqi kanal
Q3  🗺️ Ko'p ferma qo'llab-quvvatlash (multi-tenant) → kengayish
Q4  💰 Moliyaviy modul (xarajat, daromad, ROI)      → biznes hisob
Q5  🌐 REST API (tashqi tizimlar uchun)              → integratsiya
Q6  🔊 Ovoz tahlili (mayin, qichqirish anomaliyasi) → audio AI
Q7  🌡️ Tarozi bilan to'g'ridan integratsiya         → aniq vazn
Q8  📡 LoRaWAN sensor protokoli                     → uzoq masofali IoT
```

---

### ⚡ AI QAROR QILISH ALGORITMI

AI har chat boshida quyidagi tartibda harakat qiladi:

```
1. ZIP faylni ol → barcha fayllarni o'qi
        ↓
2. Feature Map dagi har blokni tekshir:
   "Bu feature uchun backend endpoint bormi?"
   "Frontend sahifasi to'liqmi (stub emas)?"
   "Backend-frontend mos keladi/jadval?"
        ↓
3. Holat xulosasini yoz (TAYYOR / YARIM / YO'Q)
        ↓
4. Xatolarni tuzat (duplicate key, broken import, type mismatch...)
        ↓
5. YARIM bo'lgan birinchi featureni TAYYOR qil
   (mantiqan: backend → schema → repo → service → endpoint → frontend)
        ↓
6. Agar YARIM yo'q → YO'Q bo'lgan birinchi featureni qur
   Prioritet: B → C → D → E → F → G → H → I → J → K → L → M → N → O → P
```

---

### 🏁 TO'LIQ TAYYOR MAHSULOT QANDAY KO'RINADI?

Ferma egasi telefon yoki kompyuterdan kiradi:

1. **Dashboard** → Bir qarashda: 250 ta jonivordan 8 tasi diqqat talab qiladi,
   bugungi o'rtacha ADI 74, umumiy tirik vazn 45 tonna

2. **Live Feed** → Kameradan jonli video, har jonivor tepasida ismi va ADI balli

3. **Ogohlantirishlar** → "Ayolim-03 ikki kundan beri ko'rinmaydi",
   "Buzoq-12 vazni 3 kg tushdi" — bularni bir bosishda yopadi

4. **Jonivor tafsilot** → Har bir jonivorning to'liq tarixi:
   og'irlik grafigi, sog'liq yozuvlari, ADI trendi, so'nggi 10 ta deteksiya

5. **Haftalik hisobot** → PDF ni yuklab, veterinarga beradi

6. **Sensor panel** → Molov harorati, namlik — hammasi normal ko'rinadi

Bu — loyihaning oxirgi manzili.

READMEEOF
echo "Done: $?"