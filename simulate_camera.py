import requests
import time
import random
import json
from datetime import datetime, timezone

# Backend manzili
API_URL = "http://localhost:8000/api/v1/weights/"

def generate_dummy_data():
    """Sun'iy sigir ma'lumotlarini yaratish"""
    weight = round(random.uniform(350.0, 600.0), 1)
    confidence = round(random.uniform(0.90, 0.99), 2)
    
    return {
        # --- O'ZGARISH 1: Backend talab qilayotgan ID ---
        "animal_id": 1,  
        "animal_tag_id": f"ANGUS-{random.randint(100, 999)}",
        
        "estimated_weight_kg": weight,
        "confidence_score": confidence,
        "camera_id": "CAM-01",
        
        # --- O'ZGARISH 2: Toshkent vaqtini emas, UTC vaqtini yuboramiz ---
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def start_simulation():
    print(f"🚀 Simulyatsiya boshlandi! Manzil: {API_URL}")
    print("To'xtatish uchun: Ctrl + C")
    print("-" * 50)

    try:
        while True:
            data = generate_dummy_data()
            
            try:
                response = requests.post(API_URL, json=data)
                
                if response.status_code in [200, 201]:
                    print(f"✅ Yuborildi: {data['animal_tag_id']} -> {data['estimated_weight_kg']} kg")
                else:
                    # Agar animal_id topilmasa (FK error), biz uni yaratishimiz kerak bo'ladi
                    print(f"⚠️ Xatolik ({response.status_code}): {response.text}")
                    
            except requests.exceptions.ConnectionError:
                print("❌ Backendga ulanib bo'lmadi! (Docker ishlayaptimi?)")
            
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\n🛑 Simulyatsiya to'xtatildi.")

if __name__ == "__main__":
    try:
        start_simulation()
    except ImportError:
        print("Xatolik: 'requests' kutubxonasi o'rnatilmagan.")
        print("Iltimos, uni o'rnating: pip install requests")
