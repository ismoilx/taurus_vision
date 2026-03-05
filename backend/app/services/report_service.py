"""
Taurus Vision — Report Service

Professional PDF hisobotlarini yaratish xizmati.
ReportLab orqali yuqori sifatli PDF hujjatlar generatsiya qiladi.

TUZATILGAN BUGLAR (eski versiyadan):
    XATO:  d.detected_at      → TO'GRI: d.timestamp          (Detection.timestamp)
    XATO:  d.confidence_score → TO'GRI: d.confidence          (Detection.confidence)
    XATO:  Detection.detected_at → TO'GRI: Detection.timestamp
    XATO:  naive vs aware datetime solishtirish → TO'GRI: UTC aware qilindi

HISOBOT TURLARI:
    generate_animal_report()  — Bitta jonivor: tarix, vazn, deteksiya, sog'liq
    generate_farm_report()    — Ferma xulosasi: statistika, trendlar, top jonivorlar
    generate_health_report()  — Sog'liq hisoboti: alertlar, xavf tahlili, tavsiyalar

ARXITEKTURA:
    Endpoint → ReportService → SQLAlchemy ORM → ReportLab → PDF bytes
    Barcha metodlar async, AsyncSession bilan ishlaydi.
"""

from __future__ import annotations

import logging
from datetime import datetime, date, timedelta, timezone
from io import BytesIO
from typing import Optional, List, Dict, Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import and_, desc, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging_config import get_logger
from app.models.alert import Alert as AlertModel, AlertStatus, AlertSeverity
from app.models.animal import Animal, AnimalStatus
from app.models.detection import Detection
from app.models.weight_measurement import WeightMeasurement

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Dizayn konstantalari
# ---------------------------------------------------------------------------
_BRAND_DARK    = colors.HexColor("#1a3a2a")
_BRAND_GREEN   = colors.HexColor("#2d6a4f")
_BRAND_ACCENT  = colors.HexColor("#52b788")
_TABLE_HEADER  = colors.HexColor("#40916c")
_TABLE_ROW_ALT = colors.HexColor("#f0faf5")
_CRITICAL_RED  = colors.HexColor("#d62828")
_WARNING_AMBER = colors.HexColor("#e85d04")
_NEUTRAL_GREY  = colors.HexColor("#6c757d")

_PAGE_MARGIN   = 0.65 * inch


class ReportService:
    """
    Professional PDF hisobot generatsiya servisi.

    Barcha metodlar async va side-effect'siz (faqat DB o'qish + PDF yaratish).
    Har bir metod PDF ni bytes sifatida qaytaradi.

    Usage:
        svc = ReportService()
        pdf = await svc.generate_animal_report(db, animal_id=12)
    """

    def __init__(self) -> None:
        self._styles = getSampleStyleSheet()

        self._styles.add(ParagraphStyle(
            name="TVTitle",
            parent=self._styles["Heading1"],
            fontSize=22,
            textColor=_BRAND_DARK,
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            leading=26,
        ))
        self._styles.add(ParagraphStyle(
            name="TVSubtitle",
            parent=self._styles["Normal"],
            fontSize=11,
            textColor=_BRAND_GREEN,
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName="Helvetica",
        ))
        self._styles.add(ParagraphStyle(
            name="TVSection",
            parent=self._styles["Heading2"],
            fontSize=13,
            textColor=_BRAND_GREEN,
            spaceBefore=16,
            spaceAfter=8,
            fontName="Helvetica-Bold",
        ))
        self._styles.add(ParagraphStyle(
            name="TVBody",
            parent=self._styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#2c2c2c"),
            fontName="Helvetica",
        ))
        self._styles.add(ParagraphStyle(
            name="TVCaption",
            parent=self._styles["Normal"],
            fontSize=8,
            textColor=_NEUTRAL_GREY,
            fontName="Helvetica",
            alignment=TA_RIGHT,
        ))

    # ==================================================================
    # ANIMAL REPORT
    # ==================================================================

    async def generate_animal_report(
        self,
        db:        AsyncSession,
        animal_id: int,
    ) -> bytes:
        """
        Bitta jonivor uchun to'liq PDF hisobot yaratadi.

        Args:
            db:        Async database session
            animal_id: Jonivor ID

        Returns:
            PDF fayl baytlari (application/pdf uchun)

        Raises:
            ValueError: Jonivor topilmasa

        To'g'ri ORM maydon nomlari:
            Detection.timestamp    (detected_at EMAS)
            Detection.confidence   (confidence_score EMAS)
            WeightMeasurement.timestamp
            WeightMeasurement.confidence_score
            WeightMeasurement.estimated_weight_kg
        """
        logger.info(
            "Generating animal report",
            extra={"extra_data": {"animal_id": animal_id}},
        )

        result = await db.execute(
            select(Animal)
            .options(
                selectinload(Animal.weight_measurements),
                selectinload(Animal.detections),
            )
            .where(Animal.id == animal_id)
        )
        animal = result.scalar_one_or_none()

        if animal is None:
            raise ValueError(f"Animal with id={animal_id} not found")

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=_PAGE_MARGIN,
            leftMargin=_PAGE_MARGIN,
            topMargin=_PAGE_MARGIN,
            bottomMargin=_PAGE_MARGIN + 0.3 * inch,
            title=f"Animal Report — {animal.tag_id}",
            author="Taurus Vision",
        )

        story: List[Any] = []
        story.extend(self._build_header(
            title="Jonivor Hisoboti",
            subtitle=f"Tag ID: {animal.tag_id}",
        ))

        # ── Bo'lim 1: Jonivor ma'lumotlari ────────────────────────────
        story.append(Paragraph("1. Jonivor Ma'lumotlari", self._styles["TVSection"]))

        species_val = getattr(animal.species, "value", str(animal.species))
        gender_val  = getattr(animal.gender,  "value", str(animal.gender))
        status_val  = getattr(animal.status,  "value", str(animal.status))

        info_rows = [
            ["Tag ID",            animal.tag_id],
            ["Tur (species)",     species_val.capitalize()],
            ["Jinsi",             gender_val.capitalize()],
            ["Holat",             status_val.capitalize()],
            ["Zot (breed)",       animal.breed or "Ko'rsatilmagan"],
            ["Ro'yxatga olingan", self._fmt_date(animal.acquisition_date)],
            ["Tug'ilgan sana",    self._fmt_date(animal.birth_date) if animal.birth_date else "Noma'lum"],
            ["Jami deteksiyalar", str(animal.total_detections)],
            ["Oxirgi ko'rinish",  self._fmt_datetime(animal.last_detected_at) if animal.last_detected_at else "Hech qachon"],
        ]
        story.append(self._build_kv_table(info_rows))
        story.append(Spacer(1, 0.25 * inch))

        # ── Bo'lim 2: Vazn tarixi ─────────────────────────────────────
        story.append(Paragraph("2. Vazn Tarixi", self._styles["TVSection"]))

        # ✅ WeightMeasurement.timestamp — to'g'ri
        sorted_weights = sorted(
            animal.weight_measurements,
            key=lambda w: w.timestamp,
            reverse=True,
        )

        if sorted_weights:
            latest_w = sorted_weights[0]
            story.append(Paragraph(
                f"<b>Joriy vazn:</b> {latest_w.estimated_weight_kg:.1f} kg "
                f"(Ishonch: {latest_w.confidence_score * 100:.0f}%)",
                self._styles["TVBody"],
            ))
            story.append(Spacer(1, 0.1 * inch))

            # ✅ .timestamp, .confidence_score, .estimated_weight_kg — hammasi to'g'ri
            w_rows = [["Sana va vaqt", "Vazn (kg)", "Ishonch", "Kamera"]]
            for w in sorted_weights[:10]:
                w_rows.append([
                    self._fmt_datetime(w.timestamp),
                    f"{w.estimated_weight_kg:.1f}",
                    f"{w.confidence_score * 100:.0f}%",
                    w.camera_id or "—",
                ])
            story.append(self._build_data_table(w_rows, header_row=True))

            if len(sorted_weights) >= 2:
                newest = sorted_weights[0].estimated_weight_kg
                oldest = sorted_weights[-1].estimated_weight_kg
                delta  = newest - oldest
                pct    = (delta / oldest * 100) if oldest > 0 else 0.0
                if delta > 0:
                    trend_html = (
                        f"<b>Trend:</b> "
                        f"<font color='#2d6a4f'>↑ +{delta:.1f} kg (+{pct:.1f}%)</font>"
                        f" ({len(sorted_weights)} o'lchov)"
                    )
                elif delta < 0:
                    trend_html = (
                        f"<b>Trend:</b> "
                        f"<font color='#d62828'>↓ {delta:.1f} kg ({pct:.1f}%)</font>"
                        f" ({len(sorted_weights)} o'lchov)"
                    )
                else:
                    trend_html = "<b>Trend:</b> Barqaror (o'zgarish yo'q)"

                story.append(Spacer(1, 0.1 * inch))
                story.append(Paragraph(trend_html, self._styles["TVBody"]))
        else:
            story.append(Paragraph(
                "Vazn o'lchovlari hali kiritilmagan.",
                self._styles["TVBody"],
            ))

        story.append(Spacer(1, 0.25 * inch))

        # ── Bo'lim 3: Deteksiya faolligi ──────────────────────────────
        story.append(Paragraph("3. Deteksiya Faolligi", self._styles["TVSection"]))

        now_utc    = datetime.now(timezone.utc)
        thirty_ago = now_utc - timedelta(days=30)

        # ✅ d.timestamp — to'g'ri (detected_at EMAS)
        # ✅ timezone-aware solishtirish — _to_utc() orqali
        recent_dets = sorted(
            [d for d in animal.detections if self._to_utc(d.timestamp) >= thirty_ago],
            key=lambda d: d.timestamp,
            reverse=True,
        )

        if recent_dets:
            avg_per_day = len(recent_dets) / 30.0
            story.append(Paragraph(
                f"<b>So'nggi 30 kun:</b> {len(recent_dets)} ta deteksiya "
                f"(kuniga o'rtacha {avg_per_day:.1f} ta)",
                self._styles["TVBody"],
            ))
            story.append(Spacer(1, 0.1 * inch))
            story.append(Paragraph("So'nggi deteksiyalar:", self._styles["TVBody"]))
            story.append(Spacer(1, 0.06 * inch))

            # ✅ d.timestamp va d.confidence — to'g'ri maydon nomlari
            det_rows = [["Sana va vaqt", "Kamera", "Ishonch"]]
            for d in recent_dets[:5]:
                det_rows.append([
                    self._fmt_datetime(d.timestamp),
                    d.camera_id or "—",
                    f"{d.confidence * 100:.0f}%",
                ])
            story.append(self._build_data_table(det_rows, header_row=True))
        else:
            story.append(Paragraph(
                "So'nggi 30 kunda deteksiya qayd etilmagan.",
                self._styles["TVBody"],
            ))

        story.append(Spacer(1, 0.25 * inch))

        # ── Bo'lim 4: Izohlar (mavjud bo'lsa) ─────────────────────────
        if animal.notes:
            story.append(Paragraph("4. Izohlar", self._styles["TVSection"]))
            story.append(Paragraph(animal.notes, self._styles["TVBody"]))
            story.append(Spacer(1, 0.25 * inch))

        story.extend(self._build_footer())

        doc.build(
            story,
            onFirstPage=self._page_decorator,
            onLaterPages=self._page_decorator,
        )

        pdf_bytes = buffer.getvalue()
        buffer.close()

        logger.info(
            "Animal report generated",
            extra={"extra_data": {"animal_id": animal_id, "size_bytes": len(pdf_bytes)}},
        )
        return pdf_bytes

    # ==================================================================
    # FARM REPORT
    # ==================================================================

    async def generate_farm_report(
        self,
        db:          AsyncSession,
        date_from:   date,
        date_to:     date,
        report_type: str = "summary",
    ) -> bytes:
        """
        Ferma bo'yicha to'liq yig'ma hisobot.

        Args:
            db:          Async database session
            date_from:   Hisobot boshi (YYYY-MM-DD)
            date_to:     Hisobot oxiri  (YYYY-MM-DD)
            report_type: "summary" | "detailed" | "health"

        Returns:
            PDF fayl baytlari

        To'g'ri ORM maydon nomlari:
            Detection.timestamp    (detected_at EMAS)
            Detection.confidence   (confidence_score EMAS)
        """
        logger.info(
            "Generating farm report",
            extra={"extra_data": {
                "date_from": str(date_from),
                "date_to":   str(date_to),
                "type":      report_type,
            }},
        )

        # timezone-aware datetime chegara qiymatlari
        dt_from = datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc)
        dt_to   = (
            datetime(date_to.year, date_to.month, date_to.day, tzinfo=timezone.utc)
            + timedelta(days=1)
        )
        days_count = (date_to - date_from).days + 1

        # ── Statistika yig'ish ─────────────────────────────────────────

        total_animals  = await db.scalar(select(func.count(Animal.id))) or 0
        active_animals = await db.scalar(
            select(func.count(Animal.id)).where(Animal.status == AnimalStatus.ACTIVE)
        ) or 0

        # ✅ Detection.timestamp — to'g'ri
        total_dets = await db.scalar(
            select(func.count(Detection.id)).where(
                and_(Detection.timestamp >= dt_from, Detection.timestamp < dt_to)
            )
        ) or 0

        # ✅ Detection.confidence — to'g'ri
        avg_conf = await db.scalar(
            select(func.avg(Detection.confidence)).where(
                and_(Detection.timestamp >= dt_from, Detection.timestamp < dt_to)
            )
        )

        avg_weight = await db.scalar(
            select(func.avg(WeightMeasurement.estimated_weight_kg)).where(
                and_(
                    WeightMeasurement.timestamp >= dt_from,
                    WeightMeasurement.timestamp <  dt_to,
                )
            )
        )

        # Holat bo'yicha taqsimot
        status_rows = (await db.execute(
            select(Animal.status, func.count(Animal.id).label("cnt"))
            .group_by(Animal.status)
        )).all()

        # Top 10 aktiv jonivorlar
        # ✅ Detection.timestamp — to'g'ri
        top_rows = (await db.execute(
            select(
                Animal.tag_id,
                Animal.species,
                func.count(Detection.id).label("det_count"),
            )
            .select_from(Detection)
            .join(Animal, Detection.animal_id == Animal.id)
            .where(and_(Detection.timestamp >= dt_from, Detection.timestamp < dt_to))
            .group_by(Animal.id, Animal.tag_id, Animal.species)
            .order_by(desc("det_count"))
            .limit(10)
        )).all()

        # ── PDF yaratish ───────────────────────────────────────────────

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=_PAGE_MARGIN,
            leftMargin=_PAGE_MARGIN,
            topMargin=_PAGE_MARGIN,
            bottomMargin=_PAGE_MARGIN + 0.3 * inch,
            title=f"Farm Report — {date_from} to {date_to}",
            author="Taurus Vision",
        )

        story: List[Any] = []
        story.extend(self._build_header(
            title="Ferma Hisoboti",
            subtitle=(
                f"Davr: {self._fmt_date(date_from)} — {self._fmt_date(date_to)} "
                f"({days_count} kun)"
            ),
        ))

        # ── Bosh xulosa ────────────────────────────────────────────────
        story.append(Paragraph("1. Bosh Xulosa", self._styles["TVSection"]))

        avg_det_per_day = total_dets / days_count if days_count else 0.0

        summary_rows = [
            ["Ko'rsatkich",                   "Qiymat"],
            ["Jami jonivorlar",               str(total_animals)],
            ["Aktiv jonivorlar",              str(active_animals)],
            ["Jami deteksiyalar (davr)",       str(total_dets)],
            ["Kunlik o'rtacha deteksiya",      f"{avg_det_per_day:.1f}"],
            ["O'rtacha ishonch (confidence)",  f"{float(avg_conf) * 100:.1f}%" if avg_conf else "—"],
            ["O'rtacha vazn",                  f"{float(avg_weight):.1f} kg" if avg_weight else "—"],
            ["Hisobot davri",                  f"{days_count} kun"],
        ]
        story.append(self._build_data_table(summary_rows, header_row=True))
        story.append(Spacer(1, 0.25 * inch))

        # ── Holat taqsimoti ────────────────────────────────────────────
        story.append(Paragraph("2. Jonivor Holati", self._styles["TVSection"]))

        st_rows = [["Holat", "Soni"]]
        for row in status_rows:
            sv = getattr(row.status, "value", str(row.status))
            st_rows.append([sv.capitalize(), str(row.cnt)])
        story.append(self._build_data_table(st_rows, header_row=True))
        story.append(Spacer(1, 0.25 * inch))

        # ── Top 10 faol jonivorlar ─────────────────────────────────────
        if top_rows:
            story.append(Paragraph("3. Eng Faol Jonivorlar (Top 10)", self._styles["TVSection"]))

            top_table = [["#", "Tag ID", "Tur", "Deteksiyalar"]]
            for i, r in enumerate(top_rows, 1):
                sp = getattr(r.species, "value", str(r.species))
                top_table.append([str(i), r.tag_id, sp.capitalize(), str(r.det_count)])
            story.append(self._build_data_table(top_table, header_row=True))
            story.append(Spacer(1, 0.25 * inch))

        story.extend(self._build_footer())

        doc.build(
            story,
            onFirstPage=self._page_decorator,
            onLaterPages=self._page_decorator,
        )

        pdf_bytes = buffer.getvalue()
        buffer.close()

        logger.info(
            "Farm report generated",
            extra={"extra_data": {"size_bytes": len(pdf_bytes)}},
        )
        return pdf_bytes

    # ==================================================================
    # HEALTH REPORT
    # ==================================================================

    async def generate_health_report(
        self,
        db:         AsyncSession,
        animal_ids: Optional[List[int]] = None,
    ) -> bytes:
        """
        Sog'liq yo'naltirilgan hisobot: alertlar, xavf tahlili, tavsiyalar.

        Args:
            db:         Async database session
            animal_ids: Aniq jonivor ID'lar (None = barcha aktiv)

        Returns:
            PDF fayl baytlari
        """
        logger.info(
            "Generating health report",
            extra={"extra_data": {"animal_ids": animal_ids}},
        )

        q = select(Animal).where(Animal.status == AnimalStatus.ACTIVE)
        if animal_ids:
            q = q.where(Animal.id.in_(animal_ids))
        animals = (await db.execute(q)).scalars().all()

        now_utc  = datetime.now(timezone.utc)
        week_ago = now_utc - timedelta(days=7)

        # Ko'rinmaslik alertlari
        detection_alerts: List[Dict] = []
        for a in animals:
            if a.last_detected_at is None:
                detection_alerts.append({
                    "tag_id":   a.tag_id,
                    "severity": "critical",
                    "message":  "Hech qachon kamera orqali aniqlanmagan",
                    "days":     None,
                })
            else:
                last_utc   = self._to_utc(a.last_detected_at)
                days_since = (now_utc - last_utc).days
                if days_since > 7:
                    detection_alerts.append({
                        "tag_id":   a.tag_id,
                        "severity": "warning" if days_since < 14 else "critical",
                        "message":  f"So'nggi ko'rinish: {days_since} kun oldin",
                        "days":     days_since,
                    })

        # DB dagi ochiq alertlar
        db_alerts = (await db.execute(
            select(AlertModel)
            .where(AlertModel.status.in_([AlertStatus.OPEN, AlertStatus.SEEN]))
            .order_by(AlertModel.severity.desc(), AlertModel.created_at.desc())
            .limit(50)
        )).scalars().all()

        # ── PDF ────────────────────────────────────────────────────────

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=_PAGE_MARGIN,
            leftMargin=_PAGE_MARGIN,
            topMargin=_PAGE_MARGIN,
            bottomMargin=_PAGE_MARGIN + 0.3 * inch,
            title="Health Report — Taurus Vision",
            author="Taurus Vision",
        )

        story: List[Any] = []
        story.extend(self._build_header(
            title="Sog'liq Hisoboti",
            subtitle=f"Sana: {self._fmt_date(now_utc.date())}",
        ))

        # ── Umumiy ko'rinish ───────────────────────────────────────────
        story.append(Paragraph("1. Sog'liq Umumiy Ko'rinishi", self._styles["TVSection"]))

        critical_det = sum(1 for a in detection_alerts if a["severity"] == "critical")
        warning_det  = len(detection_alerts) - critical_det
        critical_db  = sum(
            1 for a in db_alerts
            if getattr(a.severity, "value", str(a.severity)) in ("critical",)
        )
        warning_db   = len(db_alerts) - critical_db

        overview_rows = [
            ["Ko'rsatkich",              "Qiymat"],
            ["Monitoring jonivorlari",   str(len(animals))],
            ["Ko'rinmaslik alertlari",    str(len(detection_alerts))],
            ["  — Kritik",               str(critical_det)],
            ["  — Ogohlantirish",         str(warning_det)],
            ["Tizim alertlari (ochiq)",   str(len(db_alerts))],
            ["  — Kritik",               str(critical_db)],
            ["  — Boshqalar",            str(warning_db)],
        ]
        story.append(self._build_data_table(overview_rows, header_row=True))
        story.append(Spacer(1, 0.25 * inch))

        # ── Ko'rinmaslik alertlari ─────────────────────────────────────
        story.append(Paragraph("2. Ko'rinmaslik Alertlari", self._styles["TVSection"]))
        if detection_alerts:
            da_rows = [["Tag ID", "Daraja", "Xabar"]]
            for a in detection_alerts:
                da_rows.append([a["tag_id"], a["severity"].capitalize(), a["message"]])
            story.append(self._build_alert_table(da_rows))
        else:
            story.append(Paragraph(
                "✓ Barcha aktiv jonivorlar so'nggi 7 kun ichida aniqlangan.",
                self._styles["TVBody"],
            ))
        story.append(Spacer(1, 0.25 * inch))

        # ── Tizim alertlari ────────────────────────────────────────────
        if db_alerts:
            story.append(Paragraph("3. Tizim Alertlari (Ochiq)", self._styles["TVSection"]))
            sys_rows = [["Tag ID", "Tur", "Daraja", "Sarlavha"]]
            for a in db_alerts[:20]:
                sev   = getattr(a.severity,   "value", str(a.severity))
                atype = getattr(a.alert_type, "value", str(a.alert_type))
                sys_rows.append([
                    getattr(a, "animal_tag_id", None) or "—",
                    atype.replace("_", " ").title(),
                    sev.capitalize(),
                    (a.title or "")[:55],
                ])
            story.append(self._build_alert_table(sys_rows))
            story.append(Spacer(1, 0.25 * inch))

        # ── Tavsiyalar ─────────────────────────────────────────────────
        story.append(Paragraph("4. Tavsiyalar", self._styles["TVSection"]))
        for rec in self._build_recommendations(detection_alerts, db_alerts, len(animals)):
            story.append(Paragraph(f"• {rec}", self._styles["TVBody"]))
            story.append(Spacer(1, 0.04 * inch))

        story.extend(self._build_footer())

        doc.build(
            story,
            onFirstPage=self._page_decorator,
            onLaterPages=self._page_decorator,
        )

        pdf_bytes = buffer.getvalue()
        buffer.close()

        logger.info(
            "Health report generated",
            extra={"extra_data": {"size_bytes": len(pdf_bytes), "animal_count": len(animals)}},
        )
        return pdf_bytes

    # ==================================================================
    # PRIVATE — PDF qurilish yordamchi metodlari
    # ==================================================================

    def _build_header(self, title: str, subtitle: str) -> List[Any]:
        return [
            Paragraph("TAURUS VISION", self._styles["TVTitle"]),
            Paragraph(title,            self._styles["TVTitle"]),
            Paragraph(subtitle,         self._styles["TVSubtitle"]),
            Spacer(1, 0.1 * inch),
            self._build_divider(),
            Spacer(1, 0.15 * inch),
        ]

    def _build_footer(self) -> List[Any]:
        return [
            Spacer(1, 0.4 * inch),
            self._build_divider(),
            Spacer(1, 0.1 * inch),
            Paragraph(
                "Taurus Vision — AI-Powered Livestock Monitoring System",
                self._styles["TVCaption"],
            ),
            Paragraph(
                f"Hisobot yaratilgan: "
                f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
                self._styles["TVCaption"],
            ),
        ]

    def _build_divider(self) -> Table:
        t = Table([[""]], colWidths=[7.1 * inch])
        t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1.0, _BRAND_ACCENT)]))
        return t

    def _build_kv_table(self, rows: List[List[str]]) -> Table:
        tbl = Table(rows, colWidths=[2.4 * inch, 4.5 * inch])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (0, -1), colors.HexColor("#e8f5ee")),
            ("TEXTCOLOR",     (0, 0), (0, -1), _BRAND_GREEN),
            ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME",      (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE",      (0, 0), (-1, -1), 10),
            ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        return tbl

    def _build_data_table(
        self,
        rows: List[List[str]],
        header_row: bool = True,
    ) -> Table:
        col_count  = len(rows[0]) if rows else 1
        col_widths = [7.0 * inch / col_count] * col_count

        tbl   = Table(rows, colWidths=col_widths)
        style = [
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
        if header_row and rows:
            style += [
                ("BACKGROUND", (0, 0), (-1, 0), _TABLE_HEADER),
                ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
                ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME",   (0, 1), (-1, -1), "Helvetica"),
            ]
            for i in range(1, len(rows)):
                if i % 2 == 0:
                    style.append(("BACKGROUND", (0, i), (-1, i), _TABLE_ROW_ALT))
        tbl.setStyle(TableStyle(style))
        return tbl

    def _build_alert_table(self, rows: List[List[str]]) -> Table:
        col_count  = len(rows[0]) if rows else 1
        col_widths = [7.0 * inch / col_count] * col_count

        tbl = Table(rows, colWidths=col_widths)
        style = [
            ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#b5202a")),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#e8aaaa")),
            ("BACKGROUND",    (0, 1), (-1, -1), colors.HexColor("#fff5f5")),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
        for i, row in enumerate(rows[1:], 1):
            if any("kritik" in str(c).lower() or "critical" in str(c).lower() for c in row):
                style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#ffe0e0")))
        tbl.setStyle(TableStyle(style))
        return tbl

    @staticmethod
    def _build_recommendations(
        detection_alerts: List[Dict],
        db_alerts: List[Any],
        animal_count: int,
    ) -> List[str]:
        recs: List[str] = []
        critical_count = sum(1 for a in detection_alerts if a["severity"] == "critical")
        if critical_count > 0:
            recs.append(
                f"{critical_count} ta jonivor kritik holat ko'rsatmoqda — "
                "darhol veterinar ko'rigidan o'tkazish tavsiya etiladi."
            )
        long_missing = sum(1 for a in detection_alerts if (a.get("days") or 0) > 14)
        if long_missing > 0:
            recs.append(
                f"{long_missing} ta jonivor 14 kundan ortiq ko'rinmayapti — "
                "kamera burchagi va jonivor joylashuvini tekshirish zarur."
            )
        open_count = len(db_alerts)
        if open_count > 10:
            recs.append(
                f"Tizimda {open_count} ta ochiq alert mavjud — "
                "Alertlar sahifasida ko'rib chiqish tavsiya etiladi."
            )
        elif open_count > 0:
            recs.append(
                f"{open_count} ta ochiq tizim alerti mavjud — ko'rib chiqing."
            )
        if not recs:
            recs.append(
                f"Barcha {animal_count} ta aktiv jonivorning holati qoniqarli. "
                "Joriy monitoring rejimlari samarali ishlayapti."
            )
        return recs

    # ==================================================================
    # PRIVATE — Sahifa bezaklari va formatlash
    # ==================================================================

    @staticmethod
    def _page_decorator(
        canvas_obj: rl_canvas.Canvas,
        doc: SimpleDocTemplate,
    ) -> None:
        """Har bir sahifaga raqam qo'shadi (pastki o'ng burchak)."""
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.setFillColor(_NEUTRAL_GREY)
        canvas_obj.drawRightString(
            doc.width + doc.rightMargin,
            0.35 * inch,
            f"Sahifa {canvas_obj.getPageNumber()}",
        )
        canvas_obj.restoreState()

    @staticmethod
    def _fmt_date(d: Any) -> str:
        """date yoki datetime → 'YYYY-MM-DD'."""
        if d is None:
            return "—"
        if hasattr(d, "strftime"):
            return d.strftime("%Y-%m-%d")
        return str(d)

    @staticmethod
    def _fmt_datetime(dt: Any) -> str:
        """datetime → 'YYYY-MM-DD HH:MM' (UTC)."""
        if dt is None:
            return "—"
        if hasattr(dt, "strftime"):
            return dt.strftime("%Y-%m-%d %H:%M")
        return str(dt)

    @staticmethod
    def _to_utc(dt: datetime) -> datetime:
        """
        Naive datetime ni UTC-aware ga aylantiradi.
        Allaqachon aware bo'lsa — o'zgarmaydi.
        Timezone-aware solishtirish xatolarini oldini olish uchun.
        """
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt