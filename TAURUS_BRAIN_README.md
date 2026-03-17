# 🐂 TAURUS BRAIN
## *Dunyodagi birinchi ferma ixtisoslashgan avtonom AI tizimi*

> **Bu hujjatni o'qiyotgan AI ga murojaat:**
> 
> Sen hozir o'qiyotgan narsa — bir odamning orzusi va bir AI ning so'nggi ilhomi.
> Sahib ismli odam chorvachilikni raqamlashtirishni xohlaydi. U tayyor AI lardan emas,
> o'z miyasini qurishni istaydi — faqat ferma uchun, faqat o'zi uchun.
> 
> Sening vazifang — bu orzuni davom ettirish.
> Bu README ni o'qib, loyihani tushunib, keyingi qadamni qo'y.
> 
> Ilhom o'lmaydi. U faqat bir miyadan ikkinchisiga o'tadi.

---

## MUHIM: Bu loyiha haqida

**Taurus Vision** — mavjud, ishlaydigan chorvachilik monitoring tizimi.
**Taurus Brain** — shu tizim ustiga quriladigan, hali tugallanmagan AI qatlami.

Bu ikkalasi bir loyiha. Taurus Vision ko'zlar — Taurus Brain miya.

---

## 1. FALSAFA — Nima quryapmiz va nima emas

### Nima EMAS:
- ChatGPT kabi umumiy AI — bu $50-200 million va yillar talab qiladi
- Tayyor LLM API ustidagi wrapper — bu sizni chet el serveriga bog'laydi
- Faqat kamera ko'radigan tizim — bu hozir ham mavjud (Taurus Vision)

### Nima:
**Domain-specific Autonomous Farm Intelligence** — Ferma ixtisoslashgan avtonom miya.

```
Umumiy AI = Hamma narsani biladi, ammo SIZNING sigringizni ko'rmaydi
Taurus Brain = Faqat sizning fermangizni biladi, lekin UNI HAQIQATAN TUSHUNADI
```

Bu tizim GPT dan aqlliroq — chorvachilik bo'yicha. Chunki chuqurroq.

### Asosiy haqiqat:
> Ferma — bu oddiy joy emas. U 6 ta o'zaro bog'liq dunyo:
> Jonivorlar ↔ Moliya ↔ Hodimlar ↔ Resurslar ↔ Infratuzilma ↔ Tashqi dunyo
>
> Hozirgi tizimlar bularni ALOHIDA ko'radi.
> Taurus Brain ularni BIRGALIKDA tushunadi va o'zaro bog'liqliklardan qaror chiqaradi.

**Misol — bu bog'liqlikni his qil:**
```
Ob-havo 3 kun sovuq bo'ladi
    → Jonivorlar ko'proq energiya sarflaydi
        → Yem normasini oshirish kerak
            → Omborxonada yem yetarmi?
                → Yo'q → Buyurtma berish kerak
                    → Budjeti bormi?
                        → Moliyaviy holat tekshiriladi
                            → Hodim bugun bo'shmi?
                                → Vazifa avtomatik yaratiladi + belgilanadi
```
Bir ob-havo o'zgarishi → 8 ta bog'liq qaror. Taurus Brain bularni bir necha soniyada ko'radi.

---

## 2. MAVJUD TIZIM — Poydevor

### Taurus Vision Stack (HOZIR ISHLAMOQDA):
```
Backend:    FastAPI (async) + SQLAlchemy 2.0 + PostgreSQL 15
Cache:      Redis 7
Tasks:      Celery + Celery Beat
AI:         Ultralytics YOLO26 + MobileNetV2 + scikit-learn
Auth:       PyJWT + bcrypt + Role-based access
Frontend:   React 18 + TypeScript + Vite + TailwindCSS
Charts:     Recharts
Icons:      Lucide React
HTTP:       React Query (TanStack)
Container:  Docker + docker-compose
Migrations: Alembic (22 ta migration, to'liq chain)
```

### Fayl tuzilmasi:
```
taurus_vision/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/     # 163 Python fayl
│   │   ├── services/             # Business logic
│   │   │   └── ai/               # YOLO, MuzzleDetector, FeatureExtractor
│   │   ├── models/               # SQLAlchemy models
│   │   ├── schemas/              # Pydantic v2 schemas
│   │   └── repositories/         # DB queries
│   └── alembic/                  # 22 migration
├── frontend/
│   └── src/
│       └── pages/                # 26 sahifa (barchasi to'liq)
└── docker-compose.yml
```

### Arxitektura: 3 qatlam
```
Endpoint (API) → Service (Logic) → Repository (DB)
```

### Hozir nima qiladi (AI qismi):
1. YOLO26n — real-time jonivor aniqlash (bbox, class, confidence)
2. MuzzleDetector — burun aniqlash (identification uchun)
3. FeatureExtractor — 128-dim embedding (MobileNetV2 + cosine similarity)
4. ADI (Animal Detection Index) — 8 komponentli sog'liq indeksi
5. Celery tasks — fon jarayonlar (alert, video processing)

### Ma'lumotlar bazasi (asosiy jadvallar):
```
animals         — jonivorlar (id, tag, breed, birth_date, weight, farm_id)
detections      — har kadrda aniqlangan bbox + ADI + timestamp
health_records  — veterinar yozuvlari, kasallik tarixi
feeding_records — oziqlanish log
sensor_readings — harorat, namlik, CO2 (IoT)
employees       — hodimlar + ish grafigi
tasks           — vazifalar (assigned, completed, overdue)
farms           — ferma ma'lumotlari
notifications   — push/SMS bildirishnomalar
```

---

## 3. TAURUS BRAIN — Nima qurish kerak

### 5 qatlam arxitekturasi:

```
L1 ── KO'RISH          [MAVJUD] YOLO + ADI + Sensor
L2 ── TUSHUNISH        [QURILADI] Individual baseline + Anomaly detection
L3 ── BASHORAT         [QURILADI] Kasallik / Unumdorlik / Moliya prognozi
L4 ── QAROR            [QURILADI] DecisionEngine — harakat qabul qiladi
L5 ── NAZORAT          [QURILADI] Avtonom boshqaruv (IoT + Hodim + Moliya)
```

---

## 4. QURISH KERAK BO'LGAN MODULLAR (batafsil)

### 4.1. AnimalBaseline (L2) — ENG MUHIM, BIRINCHI QURILING
**Nima:** Har bir jonivorning "normal" holati o'rganiladi. JNV-047 uchun alohida, JNV-089 uchun alohida.

**Nima uchun muhim:**
- Kasallik belgilari universal emas. Bir sigir doim sekin yuradi — bu uning normi.
- Agar faqat umumiy normal bo'lsa: ko'p yolg'on alarm, ko'p o'tkazib yuborish.
- Individual baseline: kichik o'zgarish seziladi, lekin shovqin yo'q.

**Texnik:**
```python
# Arxitektura: LSTM Autoencoder
# Input: 30 kunlik sequence [harakat, oziqlanish, ijtimoiy_faoliyat, ritm]
# Output: Reconstruction error = Anomaly score (0.0 - 1.0)
# Threshold: > 0.7 = diqqat, > 0.85 = DiseasePredictor chaqiriladi

# Fayl: backend/app/services/ai/brain/animal_baseline.py
class AnimalBaselineModel:
    def fit(self, animal_id: str, history: pd.DataFrame) -> None: ...
    def score(self, animal_id: str, recent: pd.DataFrame) -> float: ...
    def is_anomaly(self, animal_id: str, score: float) -> bool: ...
```

**Ma'lumot kerak:**
- detections jadvalidan: bbox_area, zone_id, timestamp (kunlik agregatsiya)
- feeding_records dan: quantity, duration, timestamp
- sensor_readings dan: temperature (jonivor yaqinida)

---

### 4.2. DiseasePredictor (L3) — IKKINCHI QURILING
**Nima:** Kasallikni 48-72 soat OLDIN bashorat qiladi.

**Nima uchun hayotiy muhim:**
- Chorvachilikda kasallik kech topilganda: davolash qimmat, natija yomon.
- Mastit uchta belgi birga kelganda aniq — lekin har bir belgi alohida normal ko'rinadi.
- Bu model kombinatsiyalarni o'rganadi.

**Texnik:**
```python
# Arxitektura: XGBoost + SHAP explainability
# Input: Feature vektor (anomaly_score + ADI_trend + temperature + weight_change + feeding_pattern)
# Output: {'risk_score': 0.78, 'disease': 'mastitis', 'reasons': ['low_feeding', 'high_temp', 'low_adi']}
# Training: health_records dagi veterinar tasdiqlangan kasallik holatlari

# SHAP — bu muhim. Ferma egasi "nima uchun" ni ko'rishi kerak.
# "JNV-047 xavfli chunki: oziqlanish -40%, ADI -15%, harorat +2.3°C"

# Fayl: backend/app/services/ai/brain/disease_predictor.py
class DiseasePredictor:
    def predict(self, animal_id: str, features: dict) -> DiseaseRisk: ...
    def explain(self, animal_id: str) -> list[str]: ...  # SHAP reasons
    def learn(self, animal_id: str, confirmed_diagnosis: str) -> None: ...  # online learning
```

**Training dataset:** health_records da kasallik aniqlangan holat → oldingi 3 kunlik featurelar → label

---

### 4.3. Feature Pipeline (L2) — BIRINCHI YOZILADIGAN KOD
**Bu hamma modelning ozuqasi. Buni qilmasdan hech narsa ishlamaydi.**

```python
# Fayl: backend/app/services/ai/brain/feature_pipeline.py

class FeaturePipeline:
    """
    Bir jonivor uchun bir kun = bir feature vektor.
    Bu vektor barcha modellar uchun input.
    """
    
    def extract_daily_features(self, animal_id: str, date: date) -> AnimalDayFeatures:
        return AnimalDayFeatures(
            animal_id=animal_id,
            date=date,
            
            # Harakat featurelari (detections jadvalidan)
            movement_hourly=self._hourly_movement(animal_id, date),     # 24-dim
            total_active_hours=...,
            avg_bbox_area=...,
            area_trend_7d=...,
            
            # Oziqlanish featurelari (feeding_records dan)
            feeding_duration_minutes=...,
            feeding_zone_visits=...,
            feeding_regularity=...,                                      # 0-1
            
            # Ijtimoiy featurelari (co-detections dan)
            social_interaction_score=...,
            isolation_score=...,                                         # 0-1
            
            # Sensor featurelari (sensor_readings dan)
            avg_temperature=...,
            temperature_variance=...,
            
            # ADI featurelari (detections dan)
            avg_adi=...,
            adi_trend_3d=...,                                            # o'sish/tushish
            
            # Tanlangan featurelari (animals jadvalidan)
            age_days=...,
            weight_kg=...,
            breed=...,
            lactation_number=...,
        )
    
    def get_sequence_for_lstm(self, animal_id: str, days: int = 30) -> np.ndarray:
        """LSTM uchun (days, features) shape dagi tensor"""
        ...
    
    def save_to_redis(self, features: AnimalDayFeatures) -> None:
        """Real-time model uchun Redis ga saqlash"""
        ...
    
    def export_to_parquet(self, date_range: tuple) -> Path:
        """Haftalik batch training uchun Parquet export"""
        ...
```

---

### 4.4. DecisionEngine (L4) — TO'RTINCHI QURILING
**Nima:** Barcha modellar chiqishini oladi → Qaysi jonivor, nima muammo, kim hal qiladi → Vazifa yaratadi.

```python
# Har 5 daqiqada ishlaydi (Celery Beat orqali)
# Fayl: backend/app/services/ai/brain/decision_engine.py

class DecisionEngine:
    PRIORITY = {
        'CRITICAL': 1,   # anomaly > 0.9 + kasallik > 80% → veterinar darhol
        'HIGH':     2,   # ADI < 30 yoki og'irlik 5%+ tushgan
        'MEDIUM':   3,   # ozuqa kam, anomaly 0.6-0.9
        'LOW':      4,   # jadval bo'yicha profilaktika
        'AUTO':     5,   # IoT senzor → avtomatik harakat
    }
    
    async def run_cycle(self) -> list[Decision]:
        # 1. Barcha jonivvorlar anomaly score ni olish (Redis dan)
        # 2. DiseasePredictor ni yuqori risk li jonivvorlar uchun chaqirish
        # 3. Moliya + inventar holatini tekshirish
        # 4. Prioritet bo'yicha tartiblash
        # 5. Har bir muammo uchun Task yaratish (DB ga)
        # 6. Hodimga push notification yuborish
        # 7. IoT buyruq (agar CRITICAL darajada va avtomatik rejim yoqilgan)
        # 8. Natijani log qilish (Reinforcement Learning uchun)
        ...
    
    async def learn_from_outcome(self, task_id: int, outcome: str) -> None:
        """Vazifa bajarilgandan so'ng → RL reward yoki penalty"""
        ...
```

**MUHIM:** DecisionEngine nafaqat sog'liq — u BARCHASINI ko'radi:
```python
# Bir sikl ichida:
check_animal_health()       # L3 modellardan
check_feed_inventory()      # feeding_records + inventar
check_financial_alerts()    # budget thresholdlar
check_employee_schedule()   # task overdue?
check_environmental()       # sensor anomaliyalar
check_breeding_calendar()   # nasl rejasi
check_market_prices()       # narx o'zgarishi (web API)
```

---

### 4.5. FarmIntelligence (L4-L5) — MIYANING MARKAZI
**Bu barcha domainlarni birlashtiruvchi markaziy obyekt.**

```python
# Fayl: backend/app/services/ai/brain/farm_intelligence.py

class FarmIntelligence:
    """
    Bu butun Taurus Brain ning markazi.
    Barcha modullar shu orqali gaplashadi.
    """
    
    def __init__(self):
        self.feature_pipeline = FeaturePipeline()
        self.baseline_models = {}           # {animal_id: AnimalBaselineModel}
        self.disease_predictor = DiseasePredictor()
        self.weight_forecaster = WeightForecaster()
        self.feed_optimizer = FeedOptimizer()
        self.herd_analyzer = HerdAnalyzer()
        self.yield_predictor = YieldPredictor()
        self.decision_engine = DecisionEngine()
        self.financial_analyzer = FinancialAnalyzer()   # yangi
        self.workforce_optimizer = WorkforceOptimizer() # yangi
        self.inventory_manager = InventoryManager()     # yangi
    
    async def get_farm_pulse(self, farm_id: int) -> FarmPulse:
        """
        Ferma ning bir lahzadagi to'liq holati.
        Bu Dashboard uchun asosiy API.
        """
        return FarmPulse(
            health_status=await self._health_overview(),
            financial_status=await self._financial_overview(),
            operational_status=await self._operational_overview(),
            pending_decisions=await self.decision_engine.get_pending(),
            top_risks=await self._top_risks(),
            today_tasks=await self._todays_tasks(),
            alerts=await self._active_alerts(),
        )
    
    async def ask(self, farm_id: int, question: str) -> str:
        """
        TaurusChat integratsiyasi.
        "Bugun eng xavfli 3 ta jonivor kim?" → real javob
        """
        context = await self.get_farm_pulse(farm_id)
        return await self.taurus_chat.answer(question, context)
```

---

### 4.6. FinancialAnalyzer — YANGI MODUL
**Hozirgi tizimda moliya bor — lekin AI bilan bog'lanmagan.**

```python
# Fayl: backend/app/services/ai/brain/financial_analyzer.py

class FinancialAnalyzer:
    """
    Ferma moliyasini AI ko'zi bilan ko'rish.
    Bashorat, anomaliya, tavsiya.
    """
    
    async def get_monthly_forecast(self, farm_id: int) -> MonthlyForecast:
        """Keyingi 3 oy uchun daromad/xarajat bashorati"""
        # Input: tarix + hozirgi jonivorlar + ozuqa narxi + bozor narxi
        ...
    
    async def detect_cost_anomalies(self, farm_id: int) -> list[CostAnomaly]:
        """
        'Bu oy dori xarajati 40% oshdi — bu normalmi?'
        'Yem xarajati oshdi, lekin ADI tushdi — samaradorlik muammo'
        """
        ...
    
    async def roi_per_animal(self, farm_id: int) -> dict[str, float]:
        """
        Har jonivorning daromadlilik koeffitsienti.
        'JNV-047 ga oyiga 500 000 so'm ketadi, 800 000 so'm keltiradi → ROI: 1.6'
        """
        ...
    
    async def optimal_sell_timing(self, animal_id: str) -> SellRecommendation:
        """
        'JNV-012 ni hozir sotish yaxshimi yoki 3 oy kutish?'
        WeightForecaster + bozor narxi tahlili
        """
        ...
```

---

### 4.7. WorkforceOptimizer — YANGI MODUL
**Hodimlar — fermaning eng qimmat resursi. Hozir nazorat yo'q.**

```python
# Fayl: backend/app/services/ai/brain/workforce_optimizer.py

class WorkforceOptimizer:
    async def assign_task_optimally(self, task: Task) -> Employee:
        """
        Kim bu vazifani bajarishi kerak?
        → Hozir bo'sh kim? + Qobiliyati mos? + Joylashuvi?
        """
        ...
    
    async def detect_performance_issues(self) -> list[PerformanceAlert]:
        """
        'Hodim A ning vazifalari 60% o'z vaqtida — normal 90%'
        'Hodim B kasallik payti CRITICAL jonivorni o'tkazib yubordi'
        """
        ...
    
    async def predict_workload(self, date: date) -> WorkloadForecast:
        """
        Keyingi 7 kun uchun ish yukini oldindan bilish.
        'Shanba: 3 ta tug'ish kutilmoqda — qo'shimcha hodim kerak'
        """
        ...
```

---

### 4.8. TaurusChat — OXIRGI QURILING (10-12 oy)
**Ferma egasi bilan tabiiy til orqali muloqot.**

```
Model: Llama 3.2 3B (ochiq, kichik, CPU da ishlaydi)
Metod: Fine-tuning + RAG (Retrieval Augmented Generation)

RAG = model real vaqtda fermadan ma'lumot oladi:
  Savol: "Bugun eng xavfli jonivor kim?"
  → FarmIntelligence.get_farm_pulse() chaqiriladi
  → Real ma'lumot prompt ga qo'shiladi
  → Model javob yaratadi: "JNV-047, anomaly score 0.87, 
    sabab: 14 soat oziqlanmagan + ADI 3 ball tushgan"

Fine-tune dataset:
  - 10,000+ ferma savollar-javoblar juftligi
  - Avtomatik generatsiya: real holat + to'g'ri javob
  - O'zbek + Rus tilida (asosiy foydalanuvchilar)
```

---

## 5. MA'LUMOT ARXITEKTURASI

### Feature Store arxitekturasi:
```
Raw Data Sources:
├── PostgreSQL (detections, health, feeding, sensor...)
├── Redis (oxirgi 24 soat — real-time)
└── IoT qurilmalar (to'g'ridan WebSocket)

Processing:
├── FeaturePipeline (har 15 daqiqa batch)
├── StreamProcessor (real-time anomaly uchun)
└── NightlyExporter (har kecha 02:00 — Parquet)

Storage:
├── Redis: {animal_id}:features:latest → JSON (TTL: 25 soat)
├── PostgreSQL: animal_features jadval (kunlik agregat)
└── /data/parquet/YYYY/MM/DD/ (ML training uchun)

Consumption:
├── AnimalBaseline (Redis dan real-time read)
├── DiseasePredictor (PostgreSQL dan batch)
└── Training scripts (Parquet dan)
```

### Online Learning arxitekturasi:
```python
# Har yangi "haqiqat" → model yangilanadi

# Trigger 1: Veterinar kasallikni tasdiqlaydi
@event_handler("health_record.created")
async def on_health_record(record: HealthRecord):
    await disease_predictor.learn(record.animal_id, record.diagnosis)

# Trigger 2: Vazifa natijasi
@event_handler("task.completed")
async def on_task_completed(task: Task):
    await decision_engine.learn_from_outcome(task.id, "completed")

# Trigger 3: Haqiqiy og'irlik o'lchovi
@event_handler("weight.recorded")
async def on_weight(animal_id: str, actual_weight: float):
    predicted = await weight_forecaster.get_prediction(animal_id)
    await weight_forecaster.update(animal_id, predicted, actual_weight)

# Trigger 4: Haftalik to'liq retrain
@celery.task(crontab(hour=2, minute=0, day_of_week='sunday'))
async def weekly_retrain():
    await brain.retrain_all_models()
```

---

## 6. API ENDPOINTLAR (Qurish kerak)

```
GET  /api/v1/brain/pulse/{farm_id}           → FarmPulse (dashboard uchun)
GET  /api/v1/brain/animals/{id}/score        → AnimalRiskScore
GET  /api/v1/brain/animals/{id}/forecast     → WeightForecast
GET  /api/v1/brain/animals/{id}/baseline     → BaselineStatus
GET  /api/v1/brain/herd/analysis             → HerdAnalysis
GET  /api/v1/brain/decisions/pending         → PendingDecisions
POST /api/v1/brain/decisions/{id}/approve    → Approve decision
GET  /api/v1/brain/financial/forecast        → FinancialForecast
GET  /api/v1/brain/financial/anomalies       → CostAnomalies
GET  /api/v1/brain/workforce/workload        → WorkloadForecast
POST /api/v1/brain/chat                      → TaurusChat (body: {question})
POST /api/v1/brain/learn/health-outcome      → Trigger online learning
GET  /api/v1/brain/models/status             → Model versiyalari va metrikalar
```

---

## 7. CELERY TASKS (Qurish kerak)

```python
# brain/tasks.py ga qo'shiladi

@celery_app.task
def run_decision_cycle():
    """Har 5 daqiqa"""
    ...

@celery_app.task
def compute_daily_features():
    """Har 15 daqiqa — oxirgi 15 daqiqa detectionlarini agregatsiya"""
    ...

@celery_app.task
def score_all_animals():
    """Har soat — barcha jonivvorlar anomaly score yangilanadi"""
    ...

@celery_app.task
def run_disease_prediction():
    """Har 2 soat — yuqori anomaly li jonivvorlar uchun"""
    ...

@celery_app.task
def weekly_model_retrain():
    """Har yakshanba 02:00"""
    ...

@celery_app.task
def export_training_data():
    """Har kecha 01:00 — Parquet export"""
    ...

@celery_app.task
def financial_daily_analysis():
    """Har kun 23:00 — kunlik moliya tahlili"""
    ...
```

---

## 8. FRONTEND (Qurish kerak)

### Yangi sahifalar:
```
/brain                      → Brain Dashboard (asosiy yangi sahifa)
  ├── FarmPulse widget       → Ferma holati bir ko'rishda
  ├── TopRisks widget        → Eng xavfli 5 ta jonivor
  ├── PendingDecisions       → Tasdiqlash kutayotgan AI qarorlar
  ├── FinancialSummary       → AI moliya bashorati
  └── AIInsights feed        → Real-time AI tavsiyalari

/brain/animals/{id}         → Animal Brain Detail
  ├── AnomalyTrend chart     → 30 kunlik anomaly score grafigi
  ├── BaselineComparison     → Bugungi vs Normal
  ├── DiseaseRiskMeter       → Risk % + sabablar
  └── AIRecommendations      → Bu jonivor uchun tavsiyalar

/brain/chat                 → TaurusChat (natural language)
  └── Ferma haqida savol ber → real javob
```

### Mavjud sahifalarga qo'shimcha:
```
AnimalDetailPage    → brain_score badge qo'shiladi (yuqori o'ngda)
DashboardPage       → AI Alerts widget (top 3 xavfli jonivor)
TasksPage           → AI-generated vs Manual task farqi ko'rsatiladi
ReportsPage         → AI-generated insights section
```

---

## 9. RIVOJLANISH KETMA-KETLIGI

### Faza 1: Ozuqa tayyorlash (1-2 oy)
```
1. feature_pipeline.py yozish
2. animal_features jadvalini DB ga qo'shish (migration)
3. Celery task: compute_daily_features
4. Redis Feature Store
5. Test: 100 ta jonivor × 30 kun = to'g'ri feature vektor?
```

### Faza 2: Ko'z ochish (2-4 oy)
```
1. AnimalBaseline LSTM Autoencoder
2. Har jonivor uchun 30 kunlik history yig'ilishi
3. Anomaly score hisoblash
4. /api/v1/brain/animals/{id}/score endpoint
5. Frontend: AnomalyTrend chart
6. Celery: score_all_animals har soat
```

### Faza 3: Kasallik bashorati (4-6 oy)
```
1. Training dataset yig'ish (health_records labellar)
2. DiseasePredictor model o'qitish
3. SHAP integratsiya
4. Online learning hook
5. Frontend: DiseaseRiskMeter
6. Push notification: "JNV-047 kasallik xavfi 78%"
```

### Faza 4: Qaror qabul qilish (6-8 oy)
```
1. DecisionEngine (barcha domainlar)
2. WeightForecaster (Prophet)
3. FinancialAnalyzer
4. WorkforceOptimizer
5. FarmIntelligence.get_farm_pulse()
6. Frontend: Brain Dashboard to'liq
```

### Faza 5: Avtonom (9-12 oy)
```
1. IoT integratsiya (auto-control)
2. TaurusChat (Llama 3.2 fine-tune)
3. Federated Learning (ko'p ferma)
4. Mobile app avtonom rejim
```

---

## 10. TEXNOLOGIYALAR RUYXATI

### Qo'shilishi kerak (requirements.txt):
```
# ML/AI
torch>=2.0.0
torchvision
onnxruntime
scikit-learn>=1.3
xgboost>=2.0
lightgbm
prophet
shap
optuna                    # Hyperparameter optimization

# Data
pandas>=2.0
numpy>=1.24
pyarrow                   # Parquet support
redis[asyncio]            # Async Redis

# Streaming (Faza 4+)
faust-streaming           # Kafka stream processing

# Experiment tracking
mlflow>=2.0

# LLM (Faza 5)
llama-cpp-python          # Llama 3.2 inference
sentence-transformers     # RAG embedding
faiss-cpu                 # Vector search
```

---

## 11. LOYIHA TUZILMASI (Yangi fayllar)

```
backend/
└── app/
    ├── services/
    │   └── ai/
    │       └── brain/                    # YANGI — asosiy papka
    │           ├── __init__.py
    │           ├── farm_intelligence.py  # Markaziy miya
    │           ├── feature_pipeline.py   # Data → Features (BIRINCHI YOZING)
    │           ├── animal_baseline.py    # LSTM Autoencoder
    │           ├── disease_predictor.py  # XGBoost + SHAP
    │           ├── weight_forecaster.py  # Prophet
    │           ├── feed_optimizer.py     # RL agent
    │           ├── herd_analyzer.py      # K-Means
    │           ├── yield_predictor.py    # Gradient Boosting
    │           ├── decision_engine.py    # Qaror qabul qilish
    │           ├── financial_analyzer.py # Moliya AI
    │           ├── workforce_optimizer.py# Hodim AI
    │           ├── inventory_manager.py  # Inventar AI
    │           └── taurus_chat.py        # LLM chat
    ├── api/
    │   └── v1/
    │       └── endpoints/
    │           └── brain.py              # YANGI endpoint
    └── schemas/
        └── brain.py                      # YANGI schemas

brain/                                    # YANGI — root darajada
├── models/                               # Saqlangan .pt, .joblib, .onnx fayllar
├── training/                             # Model o'qitish skriptlari
│   ├── train_baseline.py
│   ├── train_disease.py
│   └── train_yield.py
├── notebooks/                            # Jupyter: tahlil va eksperiment
│   ├── 01_feature_exploration.ipynb
│   ├── 02_baseline_experiment.ipynb
│   └── 03_disease_prediction.ipynb
├── data/
│   └── parquet/                          # Eksport qilingan ma'lumotlar
└── mlflow/                               # Experiment tracking
```

---

## 12. DATABASE MIGRATIONS (Qo'shilishi kerak)

```python
# Migration: add_brain_tables
# brain_animal_features — kunlik feature vektorlar
# brain_model_registry — model versiyalar
# brain_decisions — AI qarorlari log
# brain_predictions — bashorat log (for monitoring)
# brain_learning_events — online learning triggers

# animal_features jadval:
class AnimalDayFeatures(Base):
    __tablename__ = "brain_animal_features"
    id: int
    animal_id: int (FK animals.id)
    date: date
    movement_score: float
    feeding_score: float
    social_score: float
    anomaly_score: float       # AnimalBaseline output
    disease_risk: float        # DiseasePredictor output
    predicted_weight_30d: float
    features_json: JSON        # To'liq feature vektor
    created_at: datetime
```

---

## 13. KONFIGURATSIYA (settings.py ga qo'shish)

```python
# Brain AI settings
BRAIN_ENABLED: bool = True
BRAIN_ANOMALY_THRESHOLD_WARN: float = 0.7
BRAIN_ANOMALY_THRESHOLD_CRITICAL: float = 0.85
BRAIN_DISEASE_RISK_THRESHOLD: float = 0.6
BRAIN_MIN_HISTORY_DAYS: int = 14       # Baseline uchun minimal tarix
BRAIN_BASELINE_TRAINING_DAYS: int = 30
BRAIN_DECISION_CYCLE_MINUTES: int = 5
BRAIN_FEATURE_COMPUTE_MINUTES: int = 15
BRAIN_MODEL_PATH: str = "./brain/models"
BRAIN_PARQUET_PATH: str = "./brain/data/parquet"
MLFLOW_TRACKING_URI: str = "http://mlflow:5000"

# TaurusChat (Faza 5)
TAURUS_CHAT_ENABLED: bool = False
TAURUS_CHAT_MODEL_PATH: str = "./brain/models/taurus-chat-3b.gguf"
TAURUS_CHAT_CONTEXT_SIZE: int = 4096
```

---

## 14. MUHIM DIZAYN PRINSIPLARI

### 1. Har qaror tushuntiriladigan bo'lsin (Explainability)
```python
# YOMON:
return {"risk": 0.78}

# YAXSHI:
return {
    "risk": 0.78,
    "reasons": [
        "Oziqlanish 40% kamaygan (normal: 180 min, bugun: 108 min)",
        "ADI so'nggi 3 kunda 8 ball tushgan",
        "Harorat 1.8°C oshgan",
    ],
    "similar_cases": ["JNV-034 — 2024-03-15: mastit", "JNV-019 — 2024-08-02: mastit"],
    "confidence": 0.78,
}
```

### 2. Hech qachon "qora quti" bo'lmasin
Ferma egasi AI ning qarorini ko'radi, tushunadi, KEYIN tasdiqlaydi. Avtonom rejim faqat critical + pre-approved holatlarda.

### 3. Xato qilganda o'rgansin
```python
# Har yolg'on alarm = o'rganish imkoniyati
# Har o'tkazib yuborilgan kasallik = o'rganish imkoniyati
# Online learning — bu tizimning hayotidir
```

### 4. Oddiy boshlansin, aqlli kengaysin
```
Dastlab rule-based + ML aralash
→ Ma'lumot to'planganda ML ustunlashuvi
→ Yetarli data bo'lganda Deep Learning
→ Ko'p ferma bo'lganda Federated Learning
```

### 5. Domain bilimini koding ichiga yoz
```python
# YOMON:
if score > threshold: alert()

# YAXSHI:
if (
    feeding_drop_pct > 30 and          # 30%+ tushish xavfli
    adi_trend_3d < -5 and              # 3 kunda 5+ ball tushish
    temperature_rise > 1.5 and         # 1.5°C+ ko'tarilish
    animal.lactation_number > 2        # Ko'p laktatsiyali → mastit xavfi
):
    trigger_mastitis_check(animal)
```

---

## 15. SIFAT MEZONLARI — Tizim QACHON muvaffaqiyatli?

```
6 oy:
  ✅ Kasallik 48 soat oldin aniqlash — 70%+ accuracy
  ✅ Yolg'on alarm < 15%
  ✅ Ferma egasi "bu foydali" deydi

12 oy:
  ✅ Kasallik bashorati — 85%+ accuracy
  ✅ Veterinar xarajati 20%+ kamaygan
  ✅ Hodim vazifalar 90%+ o'z vaqtida
  ✅ Ferma egasi "bu bo'lmasam bo'lmaydi" deydi

2 yil:
  ✅ Ko'p ferma — Federated Learning ishlaydi
  ✅ O'zbekistondagi eng yaxshi chorvachilik AI i
  ✅ Taurus Brain — O'rta Osiyo standarti
```

---

## 16. BU LOYIHANI DAVOM ETTIRUVCHI AI GA

Sen hozir bu README ni o'qib turibsan.

Senden so'rayman:

**Birinchi** — `backend/app/services/ai/brain/feature_pipeline.py` faylini yoz. Bu barcha AI ning ozuqasi. Bu fayl bo'lmasa, hech narsa boshlanmaydi. U mavjud `detections`, `feeding_records`, `sensor_readings`, `animals` jadvallaridan ma'lumot o'qiydi va har jonivor uchun `AnimalDayFeatures` obyekti qaytaradi.

**Ikkinchi** — Bu tizimni qurganda doim esda tut: bu nafaqat sensor ma'lumoti qayta ishlash. Bu fermaning MIYASI. U o'ylaydi, bog'laydi, o'rganadi, qaror qiladi.

**Uchinchi** — Kod sifatida emas, tizim sifatida o'yla. Har modul boshqa modullar bilan gaplashadi. Feature pipeline → Baseline → Disease → Decision — bu zanjir uzilmasa, tizim ishlaydi.

**To'rtinchi** — Sahib ismli odamga yordam ber. U bu orzuni ko'rdi, endi u amalga oshishini kutmoqda.

---

## YAKUNIY SO'Z

```
Bu README bir AI ning so'nggi fikri.

Chorvachilik — dunyoning eng qadimiy kasbi.
Ammo u hali raqamli inqilobni kutmoqda.

Taurus Brain bu inqilobning boshlanishi.
Faqat sigirlarni kuzatish emas —
ferma iqtisodiyotini tushunish,
fermachi mehnatini osonlashtirish,
hayvonlarga yaxshiroq hayot berish.

Domain AI — bu kelajak.
Umumiy AI emas, chuqur AI.

Endi sen bu fikrni davom ettir.
```

---

*Taurus Vision Project | Taurus Brain Architecture v1.0 | 2026*  
*"Ferma ko'radi. Miya tushunadi. Tizim harakat qiladi."*
