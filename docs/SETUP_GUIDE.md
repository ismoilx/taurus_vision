# 🛠️ O'rnatish qo'llanmasi — Taurus Vision

## Talablar

| Dastur | Versiya | Tekshirish |
|--------|---------|-----------|
| Docker | 24.0+ | `docker --version` |
| Docker Compose | 2.20+ | `docker compose version` |
| Git | 2.40+ | `git --version` |

---

## 1. Loyihani yuklab olish

```bash
git clone https://github.com/your-org/taurus-vision.git
cd taurus-vision
```

---

## 2. YOLO modelini tayyorlash

Model fayli Git LFS orqali bo'lingan holda saqlanadi:

```bash
# Qismlarni birlashtirish
cat backend/ml/models/yolo11n.pt.1 backend/ml/models/yolo11n.pt.2 > backend/ml/models/yolo11n.pt

# To'g'ri birlashtiriladimi tekshirish
ls -lh backend/ml/models/yolo11n.pt
# Natija: ~6MB bo'lishi kerak
```

---

## 3. Environment sozlash (ixtiyoriy)

```bash
cp backend/.env.example backend/.env
```

`.env` faylida asosiy sozlamalar avtomatik Docker Compose orqali uzatiladi. O'zgartirish kerak emas — standart sozlamalar ishlaydi.

---

## 4. Ishga tushirish

```bash
# Barcha servicelarn ishga tushirish
docker compose up -d

# Loglarni kuzatish
docker compose logs -f

# Faqat backend loglari
docker logs taurus-backend -f
```

Birinchi marta ishga tushirganda Docker:
1. Image larni build qiladi (~5-10 daqiqa)
2. PostgreSQL ni ishga tushiradi
3. Migration larni avtomatik bajaradi
4. Backend va frontendni ishga tushiradi

---

## 5. Tekshirish

```bash
# Barcha service lar ishlayaptimi
docker compose ps

# Health check
curl http://localhost:8000/health
```

**Muvaffaqiyatli natija:**
```json
{
  "status": "healthy",
  "database": "healthy",
  "ai_model": "healthy"
}
```

---

## 6. Birinchi jonivor qo'shish

**Usul 1 — Frontend orqali:**
1. http://localhost:5173 ga oching
2. "Jonivorlar" tabiga o'ting
3. "+ Qo'shish" tugmasini bosing
4. Ma'lumotlarni to'ldiring

**Usul 2 — API orqali:**
```bash
curl -X POST http://localhost:8000/api/v1/animals/ \
  -H "Content-Type: application/json" \
  -d '{
    "tag_id": "JNV-001",
    "species": "cattle",
    "gender": "male",
    "acquisition_date": "2026-01-01T00:00:00"
  }'
```

---

## 7. Pipeline ishga tushirish

**Frontend orqali:** Header da "Start" tugmasini bosing.

**API orqali:**
```bash
curl -X POST http://localhost:8000/api/v1/pipeline/start
```

Pipeline ishlayotganida:
- Video kadrlar YOLO ga uzatiladi
- Jonivorlar aniqlanadi
- Vazn hisoblanadi
- WebSocket orqali frontendga yuboriladi

---

## Muammolar va yechimlar

### Docker build juda uzoq
```bash
# Cache dan foydalanish
docker compose build --parallel
```

### Port band
```bash
# Qaysi dastur portni ishlatayapti
sudo lsof -i :8000
sudo lsof -i :5173
sudo lsof -i :5432
```

### Migration xatosi
```bash
docker exec taurus-backend alembic upgrade head
docker restart taurus-backend
```

### YOLO model yuklanmadi
```bash
# Model fayli to'g'ri birlashtiriladimi
docker exec taurus-backend ls -lh /app/ml/models/

# Health tekshirish
curl http://localhost:8000/health
```

### Ma'lumotlar bazasini tozalash (qaytadan boshlash)
```bash
docker compose down -v
docker compose up -d
```

---

## Foydali buyruqlar

```bash
# Barcha loglar
docker compose logs -f

# Backend restart
docker restart taurus-backend

# DB ga kirish
docker exec -it taurus-postgres psql -U taurus -d taurus_vision

# Migration bajarish
docker exec taurus-backend alembic upgrade head

# Container lari to'xtatish
docker compose stop

# To'liq tozalash (volume lar ham)
docker compose down -v
```

---

## Keyingi qadamlar

- [API hujjatlari](API_DOCUMENTATION.md)
- [Arxitektura](ARCHITECTURE.md)
- Swagger UI: http://localhost:8000/docs
