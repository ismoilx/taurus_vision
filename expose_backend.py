"""
Taurus Vision — Backend ni Internetga Ochish (ngrok)
======================================================

Bu skript backend mashinasida ishga tushiriladi.
localhost:8000 ni ngrok orqali internetga ochadi va
URL ni avtomatik taurus_colab_stream.ipynb ga yozadi.

Ishlatish:
    python expose_backend.py --token YOUR_NGROK_TOKEN

Yoki token .env da NGROK_AUTHTOKEN bo'lsa:
    python expose_backend.py

Keyin Colab Cell 2 dagi BACKEND_URL ni mana shu URL ga o'zgartiring.
"""

import argparse
import os
import sys
import time
import json

# ─── Argumentlar ──────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="Taurus Backend ngrok expose")
parser.add_argument(
    "--token",
    default=os.getenv("NGROK_AUTHTOKEN", ""),
    help="ngrok auth token (https://dashboard.ngrok.com/get-started/your-authtoken)",
)
parser.add_argument(
    "--port",
    type=int,
    default=8000,
    help="Backend port (default: 8000)",
)
args = parser.parse_args()

if not args.token:
    print("❌ ngrok token topilmadi!")
    print("   1. https://dashboard.ngrok.com/get-started/your-authtoken dan oling")
    print("   2. --token parametr bilan bering: python expose_backend.py --token YOUR_TOKEN")
    print("   3. Yoki .env faylga NGROK_AUTHTOKEN=YOUR_TOKEN qo'shing")
    sys.exit(1)

# ─── pyngrok o'rnatish ────────────────────────────────────────────────────────

try:
    from pyngrok import ngrok, conf
except ImportError:
    print("⏳ pyngrok o'rnatilmoqda...")
    os.system(f"{sys.executable} -m pip install pyngrok -q")
    from pyngrok import ngrok, conf

# ─── ngrok ishga tushirish ────────────────────────────────────────────────────

print("=" * 55)
print("  🌐 Taurus Backend — ngrok Tunnel")
print("=" * 55)
print(f"  Token : {args.token[:8]}...{args.token[-4:]}")
print(f"  Port  : {args.port}")
print("=" * 55)

conf.get_default().auth_token = args.token

try:
    tunnel = ngrok.connect(args.port, "http")
    backend_url = tunnel.public_url

    # https ga o'tkazish (ngrok ba'zan http beradi)
    if backend_url.startswith("http://"):
        backend_url = "https://" + backend_url[7:]

    print(f"\n✅ Tunnel ochildi!")
    print(f"\n   BACKEND_URL = '{backend_url}'")
    print(f"\n{'─' * 55}")
    print(f"  📋 Colab Cell 2 ga quyidagini ko'chiring:")
    print(f"{'─' * 55}")
    print(f"\n  BACKEND_URL = '{backend_url}'\n")
    print(f"{'─' * 55}")
    print(f"\n  Health check: {backend_url}/health")
    print(f"  API docs    : {backend_url}/docs")
    print(f"\n⚠️  Bu oynani YOPMANG — tunnel ishlayapti")
    print(f"   To'xtatish: Ctrl+C\n")

    # Tunnel URL ni faylga ham yozish
    with open("ngrok_url.txt", "w") as f:
        f.write(backend_url + "\n")
    print(f"   URL 'ngrok_url.txt' ga ham saqlandi\n")

    # Har 30 sekundda status
    while True:
        time.sleep(30)
        tunnels = ngrok.get_tunnels()
        if tunnels:
            print(f"✅ Tunnel aktiv: {backend_url}")
        else:
            print("⚠️  Tunnel uzildi! Qayta ulanmoqda...")
            tunnel = ngrok.connect(args.port, "http")
            backend_url = tunnel.public_url
            if backend_url.startswith("http://"):
                backend_url = "https://" + backend_url[7:]
            print(f"✅ Yangi URL: {backend_url}")

except KeyboardInterrupt:
    print("\n\n🛑 Tunnel yopilmoqda...")
    ngrok.disconnect(tunnel.public_url)
    ngrok.kill()
    print("✅ Tunnel yopildi")
except Exception as e:
    print(f"\n❌ ngrok xatosi: {e}")
    print("   Token to'g'rimi? ngrok.com da tekshiring.")
    sys.exit(1)
