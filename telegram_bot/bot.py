"""
Taurus Vision — Telegram Admin Bot

Tizim boshqaruvi uchun maxsus bot.
NOTIFICATION boti dan BUTUNLAY ALOHIDA.

IMKONIYATLAR:
    /start        — Salomlashish, buyruqlar ro'yxati
    /status       — Barcha Docker containerlar holati
    /health       — Backend API health check
    /logs <n> [N] — Container loglari (so'nggi N qator)
    /restart <n>  — Container ni qayta ishga tushirish
    /stop <n>     — Container ni to'xtatish
    /start <n>    — Container ni ishga tushirish
    /stats        — Tizim resurslari (CPU, RAM, Disk)
    /screenshot   — Kamera snapshot (backend API orqali)
    /help         — Yordam

XAVFSIZLIK:
    Faqat ADMIN_ALLOWED_CHAT_IDS dagi chat_id lar ishlata oladi.
    Boshqa har qanday foydalanuvchi bloklangan.

SOZLASH (.env):
    ADMIN_BOT_TOKEN=7xxxxxxxxx:AAxxxx...
    ADMIN_ALLOWED_CHAT_IDS=123456789,987654321
    BACKEND_URL=http://taurus-backend:8000
    BACKEND_INTERNAL_TOKEN=xxxx   (ixtiyoriy, internal API uchun)

AVTOMATIK:
    Har soatda tizim holati xabari
    Containerdan birortasi tushib ketsa ogohlantirish

DOCKER:
    docker socket: /var/run/docker.sock (read+exec)
"""

import os
import asyncio
import logging
import json
import datetime
import subprocess
import urllib.request
import urllib.error
from typing import Optional

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("taurus.admin_bot")


# ─────────────────────────────────────────────
# KONFIGURATSIYA
# ─────────────────────────────────────────────
BOT_TOKEN          = os.environ.get("ADMIN_BOT_TOKEN", "")
ALLOWED_CHAT_IDS   = set(
    x.strip()
    for x in os.environ.get("ADMIN_ALLOWED_CHAT_IDS", "").split(",")
    if x.strip()
)
BACKEND_URL        = os.environ.get("BACKEND_URL", "http://taurus-backend:8000")
BACKEND_TOKEN      = os.environ.get("BACKEND_INTERNAL_TOKEN", "")
HOURLY_STATUS      = os.environ.get("HOURLY_STATUS_ENABLED", "true").lower() == "true"
WATCH_INTERVAL     = int(os.environ.get("WATCH_INTERVAL_SEC", "60"))   # container health watch

# Docker container nomlari (monitoring uchun)
WATCHED_CONTAINERS = [
    "taurus-backend",
    "taurus-celery-worker",
    "taurus-celery-training",
    "taurus-celery-beat",
    "taurus-postgres",
    "taurus-redis",
    "taurus-frontend",
]

# ─────────────────────────────────────────────
# TELEGRAM API YORDAMCHI
# ─────────────────────────────────────────────

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def tg_request(method: str, payload: dict) -> dict:
    """Telegram API ga sinxron so'rov."""
    url  = f"{TELEGRAM_API}/{method}"
    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.error(f"Telegram API xato [{method}]: {exc}")
        return {"ok": False, "error": str(exc)}


async def send(chat_id: str | int, text: str, parse_mode: str = "HTML") -> None:
    """Foydalanuvchiga xabar yuborish."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None, tg_request, "sendMessage",
        {
            "chat_id":                  str(chat_id),
            "text":                     text,
            "parse_mode":               parse_mode,
            "disable_web_page_preview": True,
        }
    )


async def send_photo(chat_id: str | int, photo_bytes: bytes, caption: str = "") -> None:
    """Rasm yuborish."""
    import urllib.parse
    boundary = "----TaurusBotBoundary"
    body  = f"--{boundary}\r\n"
    body += f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
    body += f"--{boundary}\r\n"
    body += f'Content-Disposition: form-data; name="photo"; filename="screenshot.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'
    body_bytes = body.encode("utf-8") + photo_bytes
    body_bytes += f"\r\n--{boundary}--\r\n".encode("utf-8")
    if caption:
        cap_part = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
        )
        body_bytes = body.encode("utf-8") + cap_part.encode("utf-8") + photo_bytes
        body_bytes += f"\r\n--{boundary}--\r\n".encode("utf-8")

    url = f"{TELEGRAM_API}/sendPhoto"
    req = urllib.request.Request(
        url, data=body_bytes,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=20))
    except Exception as exc:
        logger.error(f"Rasm yuborish xato: {exc}")


# ─────────────────────────────────────────────
# XAVFSIZLIK — CHAT ID TEKSHIRISH
# ─────────────────────────────────────────────

def is_allowed(chat_id: str | int) -> bool:
    """Foydalanuvchi ruxsat ro'yxatida bormi?"""
    return str(chat_id) in ALLOWED_CHAT_IDS


def blocked_message(chat_id: int) -> str:
    return (
        "🚫 <b>Ruxsat yo'q!</b>\n\n"
        "Bu bot faqat tizim administratorlari uchun.\n"
        f"Sizning chat ID: <code>{chat_id}</code>\n\n"
        "Qo'shilish uchun adminstratorga murojaat qiling."
    )


# ─────────────────────────────────────────────
# DOCKER YORDAMCHI
# ─────────────────────────────────────────────

def docker_cmd(*args: str, timeout: int = 30) -> tuple[int, str, str]:
    """Docker buyrug'ini bajarish. (returncode, stdout, stderr)"""
    cmd = ["docker"] + list(args)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Buyruq vaqti tugadi (timeout)"
    except FileNotFoundError:
        return -1, "", "Docker topilmadi"
    except Exception as exc:
        return -1, "", str(exc)


def get_container_status(name: str) -> dict:
    """Container holati."""
    code, out, err = docker_cmd(
        "inspect", "--format",
        '{"status":"{{.State.Status}}","running":{{.State.Running}},"started":"{{.State.StartedAt}}","health":"{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}"}',
        name
    )
    if code != 0:
        return {"status": "not_found", "running": False, "started": "", "health": "none"}
    try:
        return json.loads(out)
    except Exception:
        return {"status": "unknown", "running": False, "started": "", "health": "none"}


def status_emoji(info: dict) -> str:
    s = info.get("status", "")
    h = info.get("health", "none")
    if s == "running" and h in ("healthy", "none"):  return "🟢"
    if s == "running" and h == "unhealthy":           return "🟡"
    if s == "running":                                return "🔵"
    if s in ("exited", "dead"):                       return "🔴"
    if s == "not_found":                              return "⚫"
    return "🟠"


# ─────────────────────────────────────────────
# BACKEND API YORDAMCHI
# ─────────────────────────────────────────────

def backend_get(path: str, timeout: int = 10) -> Optional[dict]:
    """Backend API ga GET so'rov."""
    url  = f"{BACKEND_URL}{path}"
    headers = {}
    if BACKEND_TOKEN:
        headers["X-Internal-Token"] = BACKEND_TOKEN
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.warning(f"Backend API xato [{path}]: {exc}")
        return None


# ─────────────────────────────────────────────
# BUYRUQ HANDLERLARI
# ─────────────────────────────────────────────

async def cmd_start(chat_id: int, _args: str) -> None:
    text = (
        "🐂 <b>Taurus Vision — Admin Bot</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Tizim boshqaruvi uchun maxsus bot.\n\n"
        "📋 <b>Buyruqlar:</b>\n\n"
        "🔍 <b>Monitoring:</b>\n"
        "  /status — Containerlar holati\n"
        "  /health — API health check\n"
        "  /stats  — CPU · RAM · Disk\n\n"
        "📜 <b>Loglar:</b>\n"
        "  /logs backend — So'nggi 30 qator\n"
        "  /logs backend 100 — So'nggi 100 qator\n\n"
        "⚙️ <b>Boshqaruv:</b>\n"
        "  /restart backend — Qayta ishga tushirish\n"
        "  /stop celery-worker — To'xtatish\n"
        "  /start celery-worker — Ishga tushirish\n\n"
        "📸 <b>Boshqalar:</b>\n"
        "  /screenshot — Kamera screenshoti\n"
        "  /help — Batafsil yordam\n\n"
        f"🔐 Sizning chat ID: <code>{chat_id}</code>"
    )
    await send(chat_id, text)


async def cmd_status(chat_id: int, _args: str) -> None:
    await send(chat_id, "⏳ Containerlar holati tekshirilmoqda...")

    now   = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    lines = [f"🖥️ <b>Docker Containerlar Holati</b>", f"<i>{now}</i>", "━━━━━━━━━━━━━━━━━━━━━━━━━\n"]

    all_ok = True
    for name in WATCHED_CONTAINERS:
        info  = get_container_status(name)
        emoji = status_emoji(info)
        status = info.get("status", "?")
        short  = name.replace("taurus-", "")

        health_txt = ""
        if info.get("health") not in ("none", ""):
            health_txt = f" · {info['health']}"

        uptime_txt = ""
        started    = info.get("started", "")
        if started and info.get("running"):
            try:
                dt = datetime.datetime.fromisoformat(started[:19])
                delta = datetime.datetime.utcnow() - dt
                h, m = divmod(int(delta.total_seconds()) // 60, 60)
                uptime_txt = f" · ⏱ {h}s {m}d"
            except Exception:
                pass

        lines.append(f"{emoji} <b>{short}</b> — {status}{health_txt}{uptime_txt}")
        if status not in ("running",):
            all_ok = False

    lines.append("")
    lines.append("✅ Hammasi ishlayapti" if all_ok else "⚠️ Ba'zi containerlar ishlamayapti!")

    await send(chat_id, "\n".join(lines))


async def cmd_health(chat_id: int, _args: str) -> None:
    await send(chat_id, "⏳ API health tekshirilmoqda...")
    data = backend_get("/health")
    if data is None:
        await send(chat_id, "🔴 <b>Backend API javob bermayapti!</b>\nContainer ishlamayotgan bo'lishi mumkin.")
        return

    status = data.get("status", "unknown")
    emoji  = "✅" if status == "healthy" else "⚠️" if status == "degraded" else "🔴"
    now    = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    lines = [
        f"{emoji} <b>API Health: {status.upper()}</b>",
        f"<i>{now}</i>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    checks = data.get("checks", {})
    for name, info in checks.items():
        ok  = info.get("status") == "ok" if isinstance(info, dict) else bool(info)
        ico = "✅" if ok else "❌"
        lines.append(f"  {ico} {name}")

    version = data.get("version", "")
    if version:
        lines.append(f"\n📦 Versiya: <code>{version}</code>")

    await send(chat_id, "\n".join(lines))


async def cmd_logs(chat_id: int, args: str) -> None:
    parts = args.strip().split()
    if not parts:
        await send(chat_id, "❌ Foydalanish: /logs <container_nomi> [qator_soni]\nMisol: /logs backend 50")
        return

    short_name = parts[0].lower()
    n_lines    = 30
    if len(parts) > 1:
        try:
            n_lines = min(int(parts[1]), 200)
        except ValueError:
            pass

    # Qisqa nom → to'liq nom
    name_map = {
        "backend":  "taurus-backend",
        "worker":   "taurus-celery-worker",
        "celery":   "taurus-celery-worker",
        "training": "taurus-celery-training",
        "beat":     "taurus-celery-beat",
        "postgres": "taurus-postgres",
        "db":       "taurus-postgres",
        "redis":    "taurus-redis",
        "frontend": "taurus-frontend",
    }
    container = name_map.get(short_name, f"taurus-{short_name}")

    await send(chat_id, f"⏳ <b>{container}</b> loglari yuklanmoqda ({n_lines} qator)...")

    code, out, err = docker_cmd("logs", "--tail", str(n_lines), container)

    if code != 0:
        await send(chat_id, f"❌ Log olishda xato:\n<code>{err[:500]}</code>")
        return

    raw = (out or err or "Log bo'sh")
    # Telegram 4096 belgi limit
    chunks = [raw[i:i+3800] for i in range(0, len(raw), 3800)]
    now    = datetime.datetime.now().strftime("%H:%M:%S")

    for idx, chunk in enumerate(chunks[:3]):  # max 3 xabar
        header = f"📜 <b>{container}</b> [{now}]"
        if len(chunks) > 1:
            header += f" ({idx+1}/{min(len(chunks),3)})"
        await send(chat_id, f"{header}\n<pre>{_escape_html(chunk)}</pre>")


async def cmd_restart(chat_id: int, args: str) -> None:
    name = args.strip().lower()
    if not name:
        await send(chat_id, "❌ Foydalanish: /restart <container_nomi>\nMisol: /restart backend")
        return

    name_map = {
        "backend":  "taurus-backend",
        "worker":   "taurus-celery-worker",
        "celery":   "taurus-celery-worker",
        "training": "taurus-celery-training",
        "beat":     "taurus-celery-beat",
        "frontend": "taurus-frontend",
    }
    container = name_map.get(name, f"taurus-{name}")

    # Postgres va Redis ni qayta ishga tushirishni oldini olish
    if container in ("taurus-postgres", "taurus-redis"):
        await send(
            chat_id,
            f"⚠️ <b>{container}</b> ni qayta ishga tushirish havfli!\n"
            "Ma'lumotlar yo'qolishi mumkin. Qo'lda bajaring."
        )
        return

    await send(chat_id, f"🔄 <b>{container}</b> qayta ishga tushirilmoqda...")
    code, out, err = docker_cmd("restart", container, timeout=60)

    if code == 0:
        await send(chat_id, f"✅ <b>{container}</b> muvaffaqiyatli qayta ishga tushirildi!")
        # Yangi holatini ko'rsatish
        await asyncio.sleep(3)
        info  = get_container_status(container)
        emoji = status_emoji(info)
        await send(chat_id, f"{emoji} Yangi holat: <b>{info.get('status', '?')}</b>")
    else:
        await send(chat_id, f"❌ Xato:\n<code>{(err or out)[:500]}</code>")


async def cmd_stop(chat_id: int, args: str) -> None:
    name = args.strip().lower()
    if not name:
        await send(chat_id, "❌ Foydalanish: /stop <container_nomi>")
        return

    name_map = {
        "backend":  "taurus-backend",
        "worker":   "taurus-celery-worker",
        "celery":   "taurus-celery-worker",
        "training": "taurus-celery-training",
        "beat":     "taurus-celery-beat",
        "frontend": "taurus-frontend",
    }
    container = name_map.get(name, f"taurus-{name}")

    if container in ("taurus-postgres", "taurus-redis"):
        await send(chat_id, f"🚫 <b>{container}</b> ni to'xtatib bo'lmaydi (muhim servis).")
        return

    await send(chat_id, f"⏹️ <b>{container}</b> to'xtatilmoqda...")
    code, out, err = docker_cmd("stop", container, timeout=30)

    if code == 0:
        await send(chat_id, f"✅ <b>{container}</b> to'xtatildi.")
    else:
        await send(chat_id, f"❌ Xato:\n<code>{(err or out)[:500]}</code>")


async def cmd_start_container(chat_id: int, args: str) -> None:
    name = args.strip().lower()
    if not name:
        await send(chat_id, "❌ Foydalanish: /start <container_nomi>")
        return

    name_map = {
        "backend":  "taurus-backend",
        "worker":   "taurus-celery-worker",
        "celery":   "taurus-celery-worker",
        "training": "taurus-celery-training",
        "beat":     "taurus-celery-beat",
        "frontend": "taurus-frontend",
    }
    container = name_map.get(name, f"taurus-{name}")

    await send(chat_id, f"▶️ <b>{container}</b> ishga tushirilmoqda...")
    code, out, err = docker_cmd("start", container, timeout=30)

    if code == 0:
        await asyncio.sleep(3)
        info  = get_container_status(container)
        emoji = status_emoji(info)
        await send(chat_id, f"✅ <b>{container}</b> ishga tushirildi! {emoji} {info.get('status', '?')}")
    else:
        await send(chat_id, f"❌ Xato:\n<code>{(err or out)[:500]}</code>")


async def cmd_stats(chat_id: int, _args: str) -> None:
    await send(chat_id, "⏳ Tizim resurslari tekshirilmoqda...")

    # CPU
    try:
        with open("/proc/loadavg") as f:
            load = f.read().split()
        cpu_load = f"{load[0]} / {load[1]} / {load[2]}"
    except Exception:
        cpu_load = "N/A"

    # RAM
    try:
        with open("/proc/meminfo") as f:
            mem = {}
            for line in f:
                k, v = line.split(":")
                mem[k.strip()] = int(v.strip().split()[0])
        total = mem.get("MemTotal", 0)
        free  = mem.get("MemAvailable", 0)
        used  = total - free
        ram_pct = round(used / total * 100) if total else 0
        ram_txt = f"{used//1024} MB / {total//1024} MB ({ram_pct}%)"
    except Exception:
        ram_txt = "N/A"

    # Disk
    try:
        import shutil
        disk  = shutil.disk_usage("/")
        d_pct = round(disk.used / disk.total * 100)
        disk_txt = f"{disk.used//1024//1024//1024} GB / {disk.total//1024//1024//1024} GB ({d_pct}%)"
    except Exception:
        disk_txt = "N/A"

    # Docker container soni
    code, out, _ = docker_cmd("ps", "-q")
    running_count = len(out.splitlines()) if code == 0 else "?"

    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    text = (
        f"📊 <b>Tizim Resurslari</b>\n"
        f"<i>{now}</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🖥️ <b>CPU yuklanish:</b> {cpu_load}\n"
        f"💾 <b>RAM:</b> {ram_txt}\n"
        f"💿 <b>Disk:</b> {disk_txt}\n"
        f"🐳 <b>Ishlaydigan containerlar:</b> {running_count}\n"
    )
    await send(chat_id, text)


async def cmd_screenshot(chat_id: int, args: str) -> None:
    """Backend API orqali kamera screenshoti olish."""
    await send(chat_id, "📸 Kamera screenshoti olinmoqda...")

    # Avval kameralar ro'yxatini olish
    cameras = backend_get("/api/v1/cameras/?limit=5")
    if not cameras:
        await send(chat_id, "❌ Backend API javob bermayapti yoki kameralar yo'q.")
        return

    items = cameras if isinstance(cameras, list) else cameras.get("items", [])
    if not items:
        await send(chat_id, "📷 Hozircha kameralar ro'yxatda yo'q.")
        return

    # Birinchi aktiv kamerani olish
    target = None
    for cam in items:
        if cam.get("is_active"):
            target = cam
            break
    if not target:
        target = items[0]

    cam_id   = target.get("id")
    cam_name = target.get("name", f"Kamera {cam_id}")

    # Snapshot endpoint
    snap = backend_get(f"/api/v1/cameras/{cam_id}/snapshot", timeout=15)
    if not snap:
        await send(chat_id, f"❌ <b>{cam_name}</b> dan snapshot olishda xato.")
        return

    snap_url  = snap.get("url") or snap.get("snapshot_url")
    snap_time = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    if snap_url:
        await send(
            chat_id,
            f"📸 <b>{cam_name}</b>\n"
            f"<i>{snap_time}</i>\n"
            f"🔗 <a href='{snap_url}'>Screenshotni ko'rish</a>"
        )
    else:
        await send(chat_id, f"⚠️ <b>{cam_name}</b> screenshoti tayyor emas.")


async def cmd_help(chat_id: int, _args: str) -> None:
    text = (
        "📖 <b>Taurus Admin Bot — To'liq Yordam</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "🔍 <b>/status</b>\n"
        "  Barcha Docker containerlar holati, uptime\n\n"

        "❤️ <b>/health</b>\n"
        "  Backend API health check (DB, Redis, YOLO...)\n\n"

        "📊 <b>/stats</b>\n"
        "  CPU yuklanish, RAM va disk holati\n\n"

        "📜 <b>/logs</b> &lt;nomi&gt; [N]\n"
        "  Container log lari. N = qator soni (max 200)\n"
        "  Qisqa nomlar: backend, worker, training,\n"
        "  beat, postgres, redis, frontend\n\n"

        "🔄 <b>/restart</b> &lt;nomi&gt;\n"
        "  Containerni qayta ishga tushirish\n"
        "  ⚠️ postgres va redis dan himoyalangan\n\n"

        "⏹️ <b>/stop</b> &lt;nomi&gt;\n"
        "  Containerni to'xtatish\n\n"

        "▶️ <b>/start</b> &lt;nomi&gt;\n"
        "  To'xtatilgan containerni ishga tushirish\n\n"

        "📸 <b>/screenshot</b>\n"
        "  Birinchi aktiv kameradan snapshot\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 Bu bot faqat ruxsat etilgan chat ID larga javob beradi.\n"
        "🔔 Har soatda avtomatik status xabari keladi.\n"
        "⚠️ Container tushib ketsa darhol xabar keladi."
    )
    await send(chat_id, text)


# ─────────────────────────────────────────────
# DISPATCHER
# ─────────────────────────────────────────────

COMMANDS = {
    "/start":      cmd_start,
    "/status":     cmd_status,
    "/health":     cmd_health,
    "/logs":       cmd_logs,
    "/restart":    cmd_restart,
    "/stop":       cmd_stop,
    "/start_c":    cmd_start_container,   # /start container nomi bilan
    "/stats":      cmd_stats,
    "/screenshot": cmd_screenshot,
    "/help":       cmd_help,
}


async def handle_update(update: dict) -> None:
    """Telegram update ni qayta ishlash."""
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return

    chat_id = msg["chat"]["id"]
    text    = msg.get("text", "").strip()
    if not text:
        return

    # Xavfsizlik tekshiruvi
    if not is_allowed(chat_id):
        logger.warning(f"Bloklangan foydalanuvchi: chat_id={chat_id} text={text!r}")
        await send(chat_id, blocked_message(chat_id))
        return

    # Buyruqni ajratish (bot mention: /cmd@botname args)
    parts   = text.split(None, 1)
    raw_cmd = parts[0].lower().split("@")[0]
    args    = parts[1] if len(parts) > 1 else ""

    # /start <container> → cmd_start_container
    if raw_cmd == "/start" and args.strip():
        await cmd_start_container(chat_id, args)
        return

    handler = COMMANDS.get(raw_cmd)
    if handler:
        logger.info(f"Buyruq: {raw_cmd!r} | chat={chat_id} | args={args!r}")
        try:
            await handler(chat_id, args)
        except Exception as exc:
            logger.error(f"Handler xato [{raw_cmd}]: {exc}", exc_info=True)
            await send(chat_id, f"❌ Ichki xato: <code>{_escape_html(str(exc)[:300])}</code>")
    else:
        await send(
            chat_id,
            f"❓ Noma'lum buyruq: <code>{_escape_html(raw_cmd)}</code>\n"
            "/help — buyruqlar ro'yxati"
        )


# ─────────────────────────────────────────────
# AVTOMATIK STATUS (har soatda)
# ─────────────────────────────────────────────

async def hourly_status_task() -> None:
    """Har soatda barcha allowed chat larga status xabari."""
    if not HOURLY_STATUS or not ALLOWED_CHAT_IDS:
        return
    while True:
        await asyncio.sleep(3600)
        logger.info("Soatlik status xabari yuborilmoqda...")
        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        lines = [f"🕐 <b>Soatlik Holat Hisoboti</b> — {now}", "━━━━━━━━━━━━━━━━━━━━━━━━━"]

        all_ok = True
        for name in WATCHED_CONTAINERS:
            info  = get_container_status(name)
            emoji = status_emoji(info)
            short = name.replace("taurus-", "")
            lines.append(f"{emoji} {short} — {info.get('status','?')}")
            if info.get("status") != "running":
                all_ok = False

        lines.append("")
        lines.append("✅ Barcha servislar ishlayapti." if all_ok else "⚠️ Muammo aniqlandi!")

        for chat_id in ALLOWED_CHAT_IDS:
            try:
                await send(chat_id, "\n".join(lines))
            except Exception as exc:
                logger.error(f"Soatlik xabar xato ({chat_id}): {exc}")


# ─────────────────────────────────────────────
# CONTAINER WATCH (tushib ketsa ogohlantirish)
# ─────────────────────────────────────────────

async def container_watch_task() -> None:
    """Container holati o'zgarsa darhol xabar."""
    if not ALLOWED_CHAT_IDS:
        return

    prev_states: dict[str, str] = {}
    # Boshlang'ich holatni o'qish
    for name in WATCHED_CONTAINERS:
        info = get_container_status(name)
        prev_states[name] = info.get("status", "unknown")

    logger.info("Container watch ishga tushdi.")
    while True:
        await asyncio.sleep(WATCH_INTERVAL)
        for name in WATCHED_CONTAINERS:
            info        = get_container_status(name)
            new_status  = info.get("status", "unknown")
            prev_status = prev_states.get(name, "unknown")

            if new_status != prev_status:
                prev_states[name] = new_status
                emoji_new  = status_emoji(info)
                short_name = name.replace("taurus-", "")
                now        = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

                if new_status != "running":
                    msg = (
                        f"🚨 <b>Container to'xtadi!</b>\n"
                        f"<i>{now}</i>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"📦 Container: <b>{short_name}</b>\n"
                        f"{emoji_new} Holat: <b>{new_status}</b> (avval: {prev_status})\n\n"
                        f"Qayta ishga tushirish: /restart {short_name}"
                    )
                else:
                    msg = (
                        f"✅ <b>Container ishga tushdi</b>\n"
                        f"<i>{now}</i>\n"
                        f"📦 Container: <b>{short_name}</b>\n"
                        f"🟢 Holat: <b>running</b> (avval: {prev_status})"
                    )

                logger.info(f"Container holat o'zgarishi: {name} {prev_status} → {new_status}")
                for chat_id in ALLOWED_CHAT_IDS:
                    try:
                        await send(chat_id, msg)
                    except Exception as exc:
                        logger.error(f"Watch xabar xato ({chat_id}): {exc}")


# ─────────────────────────────────────────────
# POLLING LOOP
# ─────────────────────────────────────────────

async def polling_loop() -> None:
    """Telegram long polling."""
    offset = 0
    logger.info(f"Admin bot polling boshlandi. Ruxsat etilgan chatlar: {ALLOWED_CHAT_IDS}")

    # Botni tekshirish
    loop   = asyncio.get_event_loop()
    me     = await loop.run_in_executor(None, tg_request, "getMe", {})
    if me.get("ok"):
        bot_name = me["result"].get("username", "?")
        logger.info(f"Bot: @{bot_name}")
        for chat_id in ALLOWED_CHAT_IDS:
            try:
                await send(
                    chat_id,
                    f"🚀 <b>Taurus Admin Bot ishga tushdi!</b>\n"
                    f"@{bot_name}\n"
                    f"⏰ {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
                    "/status — holat ko'rish\n"
                    "/help — barcha buyruqlar"
                )
            except Exception:
                pass
    else:
        logger.error(f"Bot token noto'g'ri! {me}")

    while True:
        try:
            result = await loop.run_in_executor(
                None, tg_request, "getUpdates",
                {"offset": offset, "timeout": 30, "allowed_updates": ["message"]}
            )
            if not result.get("ok"):
                logger.warning(f"getUpdates xato: {result}")
                await asyncio.sleep(5)
                continue

            for update in result.get("result", []):
                offset = update["update_id"] + 1
                await handle_update(update)

        except asyncio.CancelledError:
            logger.info("Polling to'xtatildi.")
            break
        except Exception as exc:
            logger.error(f"Polling xato: {exc}", exc_info=True)
            await asyncio.sleep(5)


# ─────────────────────────────────────────────
# YORDAMCHI
# ─────────────────────────────────────────────

def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

async def main() -> None:
    if not BOT_TOKEN:
        logger.critical("ADMIN_BOT_TOKEN sozlanmagan! Bot ishlamaydi.")
        return
    if not ALLOWED_CHAT_IDS:
        logger.warning("ADMIN_ALLOWED_CHAT_IDS bo'sh! Hech kim ishlata olmaydi.")

    await asyncio.gather(
        polling_loop(),
        hourly_status_task(),
        container_watch_task(),
    )


if __name__ == "__main__":
    asyncio.run(main())