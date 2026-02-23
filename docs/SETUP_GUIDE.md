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

```bash
cat backend/ml/models/yolo11n.pt.1 backend/ml/models/yolo11n.pt.2 > backend/ml/models/yolo11n.pt
ls -lh backend/ml/models/yolo11n.pt  # ~6MB bo'lishi kerak
```

---

## 3. Ishga tushirish

```bash
docker compose up -d
docker compose logs -f
```

---

## 4. Health tekshirish

```bash
docker compose ps
curl http://localhost:8000/health
```

---

## 5. ⚠️ MAJBURIY: Birinchi Admin Yaratish

Tizimga kirish uchun avval admin yaratilishi shart:

```bash
# Tavsiya etilgan usul — o'z ma'lumotlaringiz bilan:
docker exec taurus-backend python scripts/create_admin.py \
    --email admin@sizning-ferma.uz \
    --username admin \
    --password "KuchliParol2024!" \
    --fullname "Ferma Boshqaruvchisi"

# Yoki default parametrlar bilan (keyin parolni o'zgartiring!):
docker exec taurus-backend python scripts/create_admin.py
```

**Default login (agar parametrsiz):**
```
Email:    admin@taurus.local
Username: admin
Parol:    Admin1234!
```

> ⚠️ Production muhitida default parolni albatta o'zgartiring!

---

## 6. Tizimga kirish

- **Frontend:** http://localhost:5173
- **Swagger UI:** http://localhost:8000/docs

---

## 7. API orqali ishlash (token kerak)

```bash
# 1. Token olish
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "Admin1234!"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# 2. Jonivor yaratish
curl -X POST http://localhost:8000/api/v1/animals/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"tag_id": "JNV-001", "species": "cattle", "gender": "male", "acquisition_date": "2026-01-01T00:00:00"}'

# 3. Pipeline ishga tushirish
curl -X POST http://localhost:8000/api/v1/pipeline/start \
  -H "Authorization: Bearer $TOKEN"
```

---

## Foydalanuvchi rollari

| Rol | Huquqlar |
|-----|---------|
| **ADMIN** | To'liq huquq |
| **MANAGER** | Boshqarish (jonivorlar, alertlar) |
| **VIEWER** | Faqat ko'rish |

---

## Foydali buyruqlar

```bash
docker compose logs -f                          # Barcha loglar
docker restart taurus-backend                  # Backend restart
docker exec -it taurus-postgres psql -U taurus -d taurus_vision  # DB
docker exec taurus-backend alembic upgrade head  # Migration
docker exec taurus-backend python scripts/create_admin.py        # Admin yaratish
docker exec taurus-backend python scripts/simulate_adi_data.py   # Test data
docker compose down -v                          # To'liq tozalash
```

---

## Muammolar

| Muammo | Yechim |
|--------|--------|
| 401 Unauthorized | `docker exec taurus-backend python scripts/create_admin.py` |
| Migration xatosi | `docker exec taurus-backend alembic upgrade head` |
| YOLO yuklanmadi | `docker exec taurus-backend ls -lh /app/ml/models/` |
| Port band | `sudo lsof -i :8000` |
| Qaytadan boshlash | `docker compose down -v && docker compose up -d` (keyin admin yarat!) |
