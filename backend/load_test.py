from locust import HttpUser, task, between
import random
from datetime import datetime

class AI_Camera_User(HttpUser):
    # Har bir foydalanuvchi (kamera) so'rov orasida 1-3 sekund kutadi
    wait_time = between(1, 3)
    
    animal_id = None
    camera_id = None

    def on_start(self):
        """
        Har bir virtual foydalanuvchi ishga tushganda 1 marta bajariladi.
        Biz har bir 'Locust' uchun yangi hayvon yaratib olamiz.
        """
        self.camera_id = f"CAM-{random.randint(100, 999)}"
        unique_tag = f"LOAD-TEST-{random.randint(10000, 99999)}"
        
        # 1. Hayvon yaratish
        response = self.client.post("/api/v1/animals/", json={
            "tag_id": unique_tag,
            "species": "cattle",
            "gender": "male",
            "acquisition_date": datetime.utcnow().isoformat(),
            "status": "active"
        })
        
        if response.status_code == 201:
            self.animal_id = response.json()["id"]
            # print(f"🤖 Kamera {self.camera_id} ishga tushdi (Animal ID: {self.animal_id})")
        else:
            print(f"❌ Hayvon yaratishda xato: {response.text}")

    @task(3) # Bu vazifa tez-tez bajariladi (vazn o'lchash)
    def send_weight_measurement(self):
        if self.animal_id:
            # Random ma'lumotlar
            weight = round(random.uniform(200.0, 600.0), 2)
            confidence = round(random.uniform(0.70, 0.99), 2)
            
            payload = {
                "animal_id": self.animal_id,
                "timestamp": datetime.utcnow().isoformat(),
                "estimated_weight_kg": weight,
                "confidence_score": confidence,
                "camera_id": self.camera_id,
                "raw_ai_data": {"test_run": "load_test"}
            }
            
            # POST so'rov yuborish
            with self.client.post("/api/v1/weights/", json=payload, catch_response=True) as response:
                if response.status_code == 201:
                    response.success()
                else:
                    response.failure(f"Status kodi xato: {response.status_code}")

    @task(1) # Bu vazifa kamroq bajariladi (statistikani ko'rish)
    def check_stats(self):
        if self.animal_id:
            self.client.get(f"/api/v1/weights/animal/{self.animal_id}/stats")