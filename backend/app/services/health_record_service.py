from datetime import datetime, date, timedelta
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.health_record import HealthRecord, HealthRecordType, HealthRecordSeverity
from app.core.exceptions import EntityNotFoundError


class HealthRecordService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_health_record(
        self,
        db: AsyncSession,
        animal_id: int,
        record_type: HealthRecordType,
        severity: HealthRecordSeverity,
        diagnosis: str,
        symptoms: Optional[str] = None,
        treatment: Optional[str] = None,
        medication: Optional[str] = None,
        dosage: Optional[str] = None,
        veterinarian: Optional[str] = None,
        clinic_name: Optional[str] = None,
        cost: Optional[float] = None,
        notes: Optional[str] = None,
        recorded_at: Optional[datetime] = None,
        next_checkup_date=None,
    ) -> HealthRecord:
        from app.models.animal import Animal
        animal = await db.get(Animal, animal_id)
        if animal is None:
            raise ValueError(f"Animal {animal_id} not found")
        if cost is not None and cost < 0:
            raise ValueError("Cost cannot be negative")
        if next_checkup_date is not None and next_checkup_date < date.today():
            raise ValueError("next_checkup_date cannot be in the past")

        record = HealthRecord(
            animal_id=animal_id,
            record_type=record_type,
            severity=severity,
            diagnosis=diagnosis,
            symptoms=symptoms,
            treatment=treatment,
            medication=medication,
            dosage=dosage,
            veterinarian=veterinarian,
            clinic_name=clinic_name,
            cost=cost,
            notes=notes,
            next_checkup_date=next_checkup_date,
            is_resolved=False,
            recorded_at=recorded_at or datetime.utcnow(),
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record

    async def get_record_by_id(self, db: AsyncSession, record_id: int) -> Optional[HealthRecord]:
        return await db.get(HealthRecord, record_id)

    async def get_animal_records(
        self, db: AsyncSession, animal_id: int, skip: int = 0, limit: int = 20
    ) -> tuple:
        from app.models.animal import Animal
        animal = await db.get(Animal, animal_id)
        if animal is None:
            raise ValueError(f"Animal {animal_id} not found")
        count_q = select(func.count()).where(HealthRecord.animal_id == animal_id)
        total = (await db.execute(count_q)).scalar_one()
        q = select(HealthRecord).where(HealthRecord.animal_id == animal_id).offset(skip).limit(limit)
        records = (await db.execute(q)).scalars().all()
        return list(records), total

    async def get_records_by_type(
        self, db: AsyncSession, animal_id: int, record_type: HealthRecordType
    ) -> tuple:
        # SQLite enumni int yoki str saqlaganda ham ishlashi uchun
        rt_val = record_type.value if hasattr(record_type, 'value') else record_type
        q = select(HealthRecord).where(HealthRecord.animal_id == animal_id)
        all_records = (await db.execute(q)).scalars().all()
        filtered = [
            r for r in all_records
            if (r.record_type.value if hasattr(r.record_type, 'value') else r.record_type) == rt_val
        ]
        return filtered, len(filtered)

    async def get_records_by_severity(
        self, db: AsyncSession, animal_id: int, severity: HealthRecordSeverity
    ) -> tuple:
        sev_val = severity.value if hasattr(severity, 'value') else severity
        q = select(HealthRecord).where(HealthRecord.animal_id == animal_id)
        all_records = (await db.execute(q)).scalars().all()
        filtered = [
            r for r in all_records
            if (r.severity.value if hasattr(r.severity, 'value') else r.severity) == sev_val
        ]
        return filtered, len(filtered)

    async def get_unresolved_records(
        self, db: AsyncSession, animal_id: Optional[int] = None,
        skip: int = 0, limit: int = 20
    ) -> tuple:
        q = select(HealthRecord).where(HealthRecord.is_resolved == False)
        if animal_id is not None:
            q = q.where(HealthRecord.animal_id == animal_id)
        all_r = (await db.execute(q)).scalars().all()
        total = len(all_r)
        return list(all_r)[skip:skip+limit], total

    async def get_critical_records(
        self, db: AsyncSession, skip: int = 0, limit: int = 20,
        animal_id: Optional[int] = None
    ) -> tuple:
        q = select(HealthRecord).where(HealthRecord.is_resolved == False)
        if animal_id is not None:
            q = q.where(HealthRecord.animal_id == animal_id)
        all_r = (await db.execute(q)).scalars().all()
        critical_val = HealthRecordSeverity.CRITICAL.value
        filtered = [
            r for r in all_r
            if (r.severity.value if hasattr(r.severity, 'value') else r.severity) == critical_val
        ]
        total = len(filtered)
        return filtered[skip:skip+limit], total

    async def get_upcoming_checkups(
        self, db: AsyncSession, days_ahead: int = 7, skip: int = 0, limit: int = 20
    ) -> tuple:
        today = date.today()
        future = today + timedelta(days=days_ahead)
        q = select(HealthRecord).where(
            HealthRecord.next_checkup_date != None,
            HealthRecord.next_checkup_date >= today,
            HealthRecord.next_checkup_date <= future,
        )
        all_r = (await db.execute(q)).scalars().all()
        total = len(all_r)
        return list(all_r)[skip:skip+limit], total

    async def update_health_record(
        self, db: AsyncSession, record_id: int, data=None, **kwargs
    ) -> HealthRecord:
        record = await db.get(HealthRecord, record_id)
        if record is None:
            raise EntityNotFoundError(entity="HealthRecord", identifier=record_id)
        # dict yoki kwargs ikkalasini ham qabul qiladi
        update_data = data if isinstance(data, dict) else kwargs
        for key, value in update_data.items():
            setattr(record, key, value)
        await db.commit()
        await db.refresh(record)
        return record

    async def resolve_health_record(
        self, db: AsyncSession, record_id: int,
        resolution_note: Optional[str] = None
    ) -> HealthRecord:
        record = await db.get(HealthRecord, record_id)
        if record is None:
            raise EntityNotFoundError(entity="HealthRecord", identifier=record_id)
        record.is_resolved = True
        record.resolved_at = datetime.utcnow()
        if resolution_note:
            record.notes = resolution_note
        await db.commit()
        await db.refresh(record)
        return record

    async def delete_health_record(self, db: AsyncSession, record_id: int) -> bool:
        record = await db.get(HealthRecord, record_id)
        if record is None:
            raise EntityNotFoundError(entity="HealthRecord", identifier=record_id)
        await db.delete(record)
        await db.commit()
        return True

    async def get_health_statistics(
        self, db: AsyncSession, animal_id: Optional[int] = None
    ) -> dict:
        q = select(HealthRecord)
        if animal_id:
            q = q.where(HealthRecord.animal_id == animal_id)
        records = (await db.execute(q)).scalars().all()
        total = len(records)
        unresolved = sum(1 for r in records if not r.is_resolved)
        critical_val = HealthRecordSeverity.CRITICAL.value
        critical_unresolved = sum(
            1 for r in records if not r.is_resolved and
            (r.severity.value if hasattr(r.severity, 'value') else r.severity) == critical_val
        )
        by_severity = {}
        for r in records:
            sev = r.severity.value if hasattr(r.severity, 'value') else str(r.severity)
            by_severity[sev] = by_severity.get(sev, 0) + 1
        return {
            "total_records": total,
            "unresolved": unresolved,
            "critical_unresolved": critical_unresolved,
            "by_severity": by_severity,
        }

    async def get_health_summary(self, db: AsyncSession, animal_id: int) -> dict:
        from app.models.animal import Animal
        animal = await db.get(Animal, animal_id)
        if animal is None:
            raise ValueError(f"Animal {animal_id} not found")
        stats = await self.get_health_statistics(db, animal_id=animal_id)
        score = self._calculate_health_score(stats)
        status = self._get_health_status(score)
        return {
            "animal_id": animal_id,
            "total_records": stats["total_records"],
            "unresolved_issues": stats["unresolved"],
            "health_score": score,
            "health_status": status,
        }

    def _calculate_health_score(self, stats: dict) -> int:
        score = 100
        score -= stats.get("critical_unresolved", 0) * 20
        score -= stats.get("unresolved", 0) * 5
        return max(0, min(100, score))

    def _get_health_status(self, score: int) -> str:
        if score >= 90:   return "excellent"
        elif score >= 75: return "good"
        elif score >= 60: return "fair"
        elif score >= 40: return "poor"
        return "critical"
