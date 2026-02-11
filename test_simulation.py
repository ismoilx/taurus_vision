import requests
import time
import random
from datetime import datetime

# Server manzili
BASE_URL = "http://localhost:8000/api/v1"

def run_simulation():
    print("🚀 Simulyatsiya boshlandi...")

    # 1. Yangi hayvon yaratish
    animal_data = {
        "tag_id": f"SIM-COW-{random.randint(1000, 9999)}",
        "species": "cattle",
        "gender": "female",
        "acquisition_date": datetime.utcnow().isoformat(),
        "status": "active"
    }
    
    response = requests.post(f"{BASE_URL}/animals/", json=animal_data)
    if response.status_code != 201:
        print("❌ Hayvon yaratishda xatolik!")
        return
    
    animal = response.json()
    animal_id = animal['id']
    print(f"✅ Yangi hayvon yaratildi: {animal['tag_id']} (ID: {animal_id})")

    # 2. 10 marta vazn o'lchash (Xuddi kamera har 1 sekundda ko'rgandek)
    current_weight = 300.0
    
    print("\n📸 Kamera ishga tushdi (10 ta o'lchov yuborilmoqda)...")
    
    for i in range(1, 11):
        # Vazn biroz o'zgaradi (simulyatsiya)
        current_weight += random.uniform(-0.5, 1.0) 
        
        measurement_data = {
            "animal_id": animal_id,
            "timestamp": datetime.utcnow().isoformat(),
            "estimated_weight_kg": round(current_weight, 2),
            "confidence_score": round(random.uniform(0.8, 0.99), 2),
            "camera_id": "CAM-SIM-01",
            "raw_ai_data": {"frame": i}
        }
        
        resp = requests.post(f"{BASE_URL}/weights/", json=measurement_data)
        
        if resp.status_code == 201:
            print(f"   [{i}/10] O'lchandi: {measurement_data['estimated_weight_kg']} kg (Status: OK)")
        else:
            print(f"   [{i}/10] Xatolik: {resp.text}")
            
        time.sleep(0.5) # Yarim sekund kutish

    # 3. Yakuniy statistika
    print("\n📊 Statistika olinmoqda...")
    stats_resp = requests.get(f"{BASE_URL}/weights/animal/{animal_id}/stats")
    print(stats_resp.json())

if __name__ == "__main__":
    try:
        run_simulation()
    except Exception as e:
        print(f"Xatolik (Server yoniqmi?): {e}")
        print("Avval 'pip install requests' qiling")