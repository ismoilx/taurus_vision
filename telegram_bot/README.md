# 🤖 Taurus Vision — Telegram Admin Bot

Tizim boshqaruvi uchun maxsus bot.
**Notification botidan butunlay alohida!**

---

## 🚀 Ishga tushirish

### 1. Yangi bot yarating
```
1. Telegramda @BotFather ga yozing
2. /newbot buyrug'ini yuboring
3. Bot nomini kiriting (masalan: TaurusAdminBot)
4. Token oling: 7xxxxxxxxx:AAxxxx...
```

### 2. Chat ID ni toping
```
1. @userinfobot ga /start yuboring
2. Sizning chat ID ko'rsatiladi
3. Yoki: @getmyid_bot
```

### 3. .env faylni to'ldiring
```env
ADMIN_BOT_TOKEN=7xxxxxxxxx:AAxxxxxxxxxxxxxxxxxxxx
ADMIN_ALLOWED_CHAT_IDS=123456789
HOURLY_STATUS_ENABLED=true
WATCH_INTERVAL_SEC=60
```

### 4. Ishga tushiring
```bash
docker compose up -d telegram-admin-bot
```

---

## 📋 Buyruqlar

| Buyruq | Tavsif |
|--------|--------|
| `/status` | Barcha containerlar holati |
| `/health` | Backend API health check |
| `/stats` | CPU · RAM · Disk |
| `/logs backend` | So'nggi 30 qator log |
| `/logs backend 100` | So'nggi 100 qator log |
| `/restart backend` | Qayta ishga tushirish |
| `/stop worker` | To'xtatish |
| `/start worker` | Ishga tushirish |
| `/screenshot` | Kamera screenshoti |
| `/help` | To'liq yordam |

### Container qisqa nomlari
| Qisqa | To'liq nom |
|-------|-----------|
| `backend` | taurus-backend |
| `worker` / `celery` | taurus-celery-worker |
| `training` | taurus-celery-training |
| `beat` | taurus-celery-beat |
| `frontend` | taurus-frontend |
| `postgres` / `db` | taurus-postgres |
| `redis` | taurus-redis |

---

## 🔐 Xavfsizlik

- Faqat `ADMIN_ALLOWED_CHAT_IDS` dagi chat ID lar ishlata oladi
- Postgres va Redis ni to'xtatish bloklanган
- Docker socket faqat o'qish rejimida (`:ro`)

---

## 🔔 Avtomatik xabarlar

1. **Har soatda** — barcha containerlar holati
2. **Container tushib ketsa** — darhol ogohlantirish
3. **Bot ishga tushganda** — xush kelibsiz xabari

---

## 🐳 Notification boti bilan farqi

| | Notification Bot | Admin Bot |
|--|--|--|
| Maqsad | Alert/ogohlantirishlar | Tizim boshqaruvi |
| Token | `TELEGRAM_BOT_TOKEN` | `ADMIN_BOT_TOKEN` |
| Chat ID | `TELEGRAM_CHAT_IDS` | `ADMIN_ALLOWED_CHAT_IDS` |
| Docker | Yo'q | Ha (/var/run/docker.sock) |
| Buyruqlar | Yo'q | Ha |