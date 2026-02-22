"""
ADI va vazn ma'lumotlarini simulatsiya qilish.

Ishlatish:
    docker exec taurus-backend python scripts/simulate_adi_data.py

Nima qiladi:
    - Barcha jonivvorlar uchun so'nggi 30 kun ADI yozuvlarini yaratadi
    - So'nggi 30 kun uchun vazn o'lchovlarini yaratadi
    - Haqiqiy sigir o'sish trendini simulatsiya qiladi
"""

import asyncio
import random
import math
import sys
import os

sys.path.insert(0, '/app')

async def main():
    from app.core.database import AsyncSessionLocal
    from app.models.adi_log import ADILog
    from app.models.weight_measurement import WeightMeasurement
    from app.models.animal import Animal
    from sqlalchemy import select, delete
    from datetime import datetime, timezone, timedelta

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Animal).limit(10))
        animals = result.scalars().all()

        if not animals:
            print("❌ Jonivor topilmadi. Avval jonivor yarating.")
            return

        print(f"✅ {len(animals)} ta jonivor topildi")

        for animal in animals:
            print(f"\n📊 {animal.tag_id} (ID={animal.id}) uchun...")

            # Eski simulate ma'lumotlarni tozalash
            await db.execute(delete(ADILog).where(ADILog.animal_id == animal.id))
            await db.execute(delete(WeightMeasurement).where(WeightMeasurement.animal_id == animal.id))
            await db.commit()

            base_weight = random.uniform(280, 380)
            base_adi    = random.uniform(50, 80)
            now         = datetime.now(timezone.utc)

            for day in range(30, -1, -1):
                date     = now - timedelta(days=day)
                date_str = date.strftime("%Y-%m-%d")

                # Vazn o'sish trendi
                daily_gain = random.uniform(0.1, 0.45)
                weight     = base_weight + (30 - day) * daily_gain + random.gauss(0, 1.2)
                weight     = max(180, min(650, weight))

                # Kuniga 2-4 o'lchov
                for _ in range(random.randint(2, 4)):
                    ts = date.replace(
                        hour=random.randint(6, 20),
                        minute=random.randint(0, 59),
                        second=0, microsecond=0
                    )
                    db.add(WeightMeasurement(
                        animal_id=           animal.id,
                        timestamp=           ts,
                        estimated_weight_kg= round(weight + random.gauss(0, 0.8), 2),
                        confidence_score=    round(random.uniform(0.78, 0.97), 3),
                        camera_id=           "CAM-SIM-001",
                        source=              "simulation",
                    ))

                # ADI zikzak trendi
                adi_score = base_adi + 8 * math.sin(day / 7 * math.pi) + random.gauss(0, 3)
                adi_score = max(10, min(98, adi_score))

                if   adi_score >= 75: category = "healthy"
                elif adi_score >= 55: category = "average"
                elif adi_score >= 35: category = "warning"
                else:                 category = "critical"

                db.add(ADILog(
                    animal_id=         animal.id,
                    calculation_date=  date_str,
                    adi_score=         round(adi_score, 2),
                    category=          category,
                    feeding_score=     round(max(0, min(100, adi_score + random.gauss(5, 8))),  2),
                    activity_score=    round(max(0, min(100, adi_score + random.gauss(-3, 6))), 2),
                    growth_score=      round(max(0, min(100, adi_score + random.gauss(0, 5))),  2),
                    data_completeness= round(random.uniform(0.75, 1.0), 3),
                    detection_count=   random.randint(2, 8),
                    weight_count=      random.randint(2, 4),
                ))

            await db.commit()
            print(f"   ✅ 30 kunlik ADI + vazn saqlandi | Joriy ~{weight:.1f}kg | ADI ~{adi_score:.1f}")

        print("\n🎉 Simulatsiya tayyor! http://localhost:5173/animals")

asyncio.run(main())