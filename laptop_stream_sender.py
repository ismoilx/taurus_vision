"""
Taurus Vision — Laptop Stream Sender
=====================================

Bu skript laptop/serverda ishga tushiriladi.
Webcam dan kadrlarni olib, Colab GPU ga JPEG formatda yuboradi.

Ishlatish:
    python laptop_stream_sender.py --url https://xxxx.ngrok-free.app

Qo'shimcha parametrlar:
    --url       Colab ngrok URL si (majburiy)
    --camera    Kamera indeksi (default: 0)
    --fps       Yuborish tezligi (default: 10)
    --quality   JPEG sifati 1-100 (default: 70)
    --width     Kadr kengligi (default: 640)
    --height    Kadr balandligi (default: 480)
    --show      Oyna ko'rsatish (default: False)
    --rtsp      RTSP URL (webcam o'rniga IP kamera)
"""

import argparse
import time
import sys
import signal
import threading
from collections import deque

import cv2
import requests
import numpy as np


# ─── Argument parsing ──────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="Taurus Vision — Laptop Stream Sender")
parser.add_argument("--url",      required=True,        help="Colab ngrok URL (https://xxxx.ngrok-free.app)")
parser.add_argument("--camera",   type=int, default=0,  help="Webcam indeksi (default: 0)")
parser.add_argument("--rtsp",     default=None,         help="RTSP URL (IP kamera uchun, masalan: rtsp://192.168.1.100:554/stream)")
parser.add_argument("--fps",      type=float, default=10.0, help="Yuborish FPS (default: 10)")
parser.add_argument("--quality",  type=int, default=70, help="JPEG sifati 1-100 (default: 70)")
parser.add_argument("--width",    type=int, default=640, help="Kadr kengligi (default: 640)")
parser.add_argument("--height",   type=int, default=480, help="Kadr balandligi (default: 480)")
parser.add_argument("--show",     action="store_true",  help="Kamera oynasini ko'rsatish")
parser.add_argument("--secret",   default="taurus123",  help="Colab secret key (default: taurus123)")

args = parser.parse_args()

COLAB_URL   = args.url.rstrip("/")
FRAME_URL   = f"{COLAB_URL}/frame"
STATUS_URL  = f"{COLAB_URL}/status"
SEND_DELAY  = 1.0 / args.fps
QUALITY     = [int(cv2.IMWRITE_JPEG_QUALITY), args.quality]
HEADERS     = {
    "ngrok-skip-browser-warning": "1",
    "Content-Type": "application/octet-stream",
}
if args.secret:
    HEADERS["X-Colab-Key"] = args.secret


# ─── Statistika ───────────────────────────────────────────────────────────────

stats = {
    "sent":    0,
    "errors":  0,
    "fps_out": 0.0,
    "latency": 0.0,
    "last_t":  time.time(),
    "colab_fps": 0.0,
    "colab_tracks": 0,
    "colab_identified": 0,
}
latency_buf = deque(maxlen=30)

_running = True

def signal_handler(sig, frame):
    global _running
    print("\n\n🛑 To'xtatilmoqda...")
    _running = False

signal.signal(signal.SIGINT, signal_handler)


# ─── Status tekshirish (alohida thread) ──────────────────────────────────────

def status_checker():
    """Har 5 sekundda Colab status ni tekshiradi."""
    while _running:
        try:
            r = requests.get(STATUS_URL, headers={"ngrok-skip-browser-warning": "1"}, timeout=5)
            if r.status_code == 200:
                d = r.json()
                stats["colab_fps"]        = d.get("fps", 0)
                stats["colab_tracks"]     = d.get("tracks", 0)
                stats["colab_identified"] = d.get("identified", 0)
        except Exception:
            pass
        time.sleep(5)

threading.Thread(target=status_checker, daemon=True).start()


# ─── Colab bilan aloqani tekshirish ───────────────────────────────────────────

print("=" * 55)
print("  🐄 Taurus Vision — Laptop Stream Sender")
print("=" * 55)
print(f"  Colab URL : {COLAB_URL}")
print(f"  FPS target: {args.fps}")
print(f"  JPEG sifat: {args.quality}")
print(f"  Kamera    : {'RTSP: ' + args.rtsp if args.rtsp else f'Webcam #{args.camera}'}")
print("=" * 55)

print("\n⏳ Colab bilan ulanish tekshirilmoqda...")
try:
    r = requests.get(STATUS_URL, headers={"ngrok-skip-browser-warning": "1"}, timeout=10)
    if r.status_code == 200:
        d = r.json()
        print(f"✅ Colab ulandi! Device: {d.get('device', '?').upper()}, "
              f"Embeddinglar: {d.get('embeddings', 0)} jonivor")
    else:
        print(f"⚠️  Colab javob berdi lekin status {r.status_code}")
except Exception as e:
    print(f"❌ Colab bilan aloqa yo'q: {e}")
    print("   Colab da Cell 6 ishga tushirilganmi? URL to'g'rimi?")
    sys.exit(1)


# ─── Kamera ochish ────────────────────────────────────────────────────────────

print(f"\n📷 Kamera ochilmoqda...")
if args.rtsp:
    cap = cv2.VideoCapture(args.rtsp)
else:
    cap = cv2.VideoCapture(args.camera)

if not cap.isOpened():
    print(f"❌ Kamera ochilmadi! (indeks: {args.camera})")
    print("   Boshqa kamera indeksini sinab ko'ring: --camera 1")
    sys.exit(1)

# Kamera parametrlari
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  args.width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
cap.set(cv2.CAP_PROP_FPS, 30)

real_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
real_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"✅ Kamera tayyor: {real_w}×{real_h}")
print(f"\n🚀 Stream boshlandi! (To'xtatish: Ctrl+C)\n")


# ─── Asosiy loop ──────────────────────────────────────────────────────────────

frame_count = 0
last_status_print = time.time()

while _running:
    loop_start = time.time()

    ret, frame = cap.read()
    if not ret:
        if args.rtsp:
            print("⚠️  RTSP ulanish uzildi, qayta ulanmoqda...")
            time.sleep(2)
            cap.release()
            cap = cv2.VideoCapture(args.rtsp)
            continue
        else:
            print("❌ Kadr o'qib bo'lmadi!")
            break

    frame_count += 1

    # JPEG ga aylantirish
    ok, jpg_buf = cv2.imencode(".jpg", frame, QUALITY)
    if not ok:
        stats["errors"] += 1
        continue

    jpg_bytes = jpg_buf.tobytes()

    # Colabga yuborish
    t_send = time.time()
    try:
        resp = requests.post(
            FRAME_URL,
            data=jpg_bytes,
            headers=HEADERS,
            timeout=5,
        )
        latency_ms = (time.time() - t_send) * 1000
        latency_buf.append(latency_ms)
        stats["latency"] = round(sum(latency_buf) / len(latency_buf), 1)

        if resp.status_code == 200:
            stats["sent"] += 1
            d = resp.json()
            # Colab dan kelgan real-time ma'lumot
            colab_fno     = d.get("fno", 0)
            colab_fps     = d.get("fps", 0)
            colab_tracks  = d.get("tracks", 0)
            colab_id      = d.get("identified", 0)
        else:
            stats["errors"] += 1

    except requests.exceptions.Timeout:
        stats["errors"] += 1
        # Timeout bo'lsa skip qilamiz — keyingi kadrga o'tamiz
    except requests.exceptions.ConnectionError:
        stats["errors"] += 1
        print("⚠️  Colab bilan aloqa uzildi, qayta urinmoqda...")
        time.sleep(1)
        continue
    except Exception as e:
        stats["errors"] += 1

    # FPS hisoblash
    now = time.time()
    dt = now - stats["last_t"]
    stats["fps_out"] = round(0.9 * stats["fps_out"] + 0.1 * (1.0 / max(dt, 0.001)), 1)
    stats["last_t"] = now

    # Oyna ko'rsatish
    if args.show:
        display = frame.copy()
        cv2.putText(display,
                    f"FPS: {stats['fps_out']} | Latency: {stats['latency']}ms | "
                    f"Tracks: {stats['colab_tracks']} | ID: {stats['colab_identified']}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("Taurus Vision — Stream", display)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    # Har 3 sekundda statistika
    if now - last_status_print >= 3.0:
        sent   = stats["sent"]
        errors = stats["errors"]
        fps_o  = stats["fps_out"]
        lat    = stats["latency"]
        c_fps  = stats["colab_fps"]
        c_tr   = stats["colab_tracks"]
        c_id   = stats["colab_identified"]

        print(
            f"📡 Yuborildi: {sent:5d} | Xato: {errors:3d} | "
            f"FPS→: {fps_o:4.1f} | Kechikish: {lat:5.0f}ms | "
            f"Colab FPS: {c_fps:4.1f} | Tracklar: {c_tr} | Aniqlandi: {c_id}"
        )
        last_status_print = now

    # FPS nazorati
    elapsed = time.time() - loop_start
    sleep_t = SEND_DELAY - elapsed
    if sleep_t > 0:
        time.sleep(sleep_t)


# ─── Tozalash ─────────────────────────────────────────────────────────────────

cap.release()
if args.show:
    cv2.destroyAllWindows()

print(f"\n{'=' * 55}")
print(f"  ✅ Stream tugatildi")
print(f"  Yuborilgan kadrlar : {stats['sent']}")
print(f"  Xatolar           : {stats['errors']}")
print(f"{'=' * 55}\n")
