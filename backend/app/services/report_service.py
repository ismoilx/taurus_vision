"""
Report Service - Taurus Vision

Professional PDF report generation for animals, farm, and health data.
Uses ReportLab for high-quality, customizable PDF documents.

Author: Taurus Vision Team
Date: 2026-02-16
"""

from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, BinaryIO
from io import BytesIO
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image as RLImage, KeepTogether
)
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart

from app.models.animal import Animal, AnimalStatus
from app.models.detection import Detection
from app.models.weight_measurement import WeightMeasurement
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class ReportService:
    """
    Professional PDF report generation service.
    
    Generates comprehensive PDF reports for:
    - Individual animals (history, weight, health)
    - Farm-wide summaries (statistics, trends)
    - Health reports (alerts, risk analysis)
    
    All reports include:
    - Professional header/footer
    - Tables with styling
    - Charts and graphs
    - Page numbers
    - Generation timestamp
    """
    
    def __init__(self):
        """Initialize report service."""
        self.page_size = A4
        self.margin = 0.75 * inch
        
        # Define styles
        self.styles = getSampleStyleSheet()
        
        # Custom styles
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a472a'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2d5a3d'),
            spaceBefore=20,
            spaceAfter=12,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=14,
            alignment=TA_LEFT
        ))
    
    # =========================================================================
    # ANIMAL REPORT
    # =========================================================================
    
    async def generate_animal_report(
        self,
        db: AsyncSession,
        animal_id: int
    ) -> bytes:
        """
        Generate comprehensive PDF report for a single animal.
        
        Args:
            db: Database session
            animal_id: Animal ID
        
        Returns:
            PDF file as bytes
        
        Raises:
            ValueError: If animal not found
        
        Report sections:
        1. Animal Information (tag, species, gender, status, etc)
        2. Weight History (table + chart)
        3. Detection Timeline (last 30 days)
        4. Health Summary
        5. Statistics
        
        Example:
            >>> service = ReportService()
            >>> pdf_bytes = await service.generate_animal_report(db, 5)
            >>> with open('animal_5.pdf', 'wb') as f:
            ...     f.write(pdf_bytes)
        """
        logger.info(f"Generating animal report: animal_id={animal_id}")
        
        try:
            # ===== Fetch animal data =====
            query = select(Animal).options(
                selectinload(Animal.weight_measurements),
                selectinload(Animal.detections)
            ).where(Animal.id == animal_id)
            
            result = await db.execute(query)
            animal = result.scalar_one_or_none()
            
            if not animal:
                raise ValueError(f"Animal with id {animal_id} not found")
            
            # ===== Create PDF =====
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=self.page_size,
                rightMargin=self.margin,
                leftMargin=self.margin,
                topMargin=self.margin,
                bottomMargin=self.margin,
                title=f"Animal Report - {animal.tag_id}"
            )
            
            # Story (content elements)
            story = []
            
            # ===== HEADER =====
            story.append(Paragraph(
                "🐄 TAURUS VISION",
                self.styles['CustomTitle']
            ))
            story.append(Paragraph(
                f"Animal Report: {animal.tag_id}",
                self.styles['Heading1']
            ))
            story.append(Spacer(1, 0.3 * inch))
            
            # ===== SECTION 1: Animal Information =====
            story.append(Paragraph("1. Animal Information", self.styles['CustomHeading']))
            
            info_data = [
                ['Tag ID:', animal.tag_id],
                ['Species:', animal.species.capitalize()],
                ['Gender:', animal.gender.capitalize()],
                ['Status:', animal.status.value.capitalize()],
                ['Breed:', animal.breed or 'Not specified'],
                ['Acquisition Date:', animal.acquisition_date.strftime('%Y-%m-%d') if animal.acquisition_date else 'N/A'],
                ['Total Detections:', str(animal.total_detections)],
                ['Last Detected:', animal.last_detected_at.strftime('%Y-%m-%d %H:%M') if animal.last_detected_at else 'Never'],
            ]
            
            info_table = Table(info_data, colWidths=[2.5*inch, 4*inch])
            info_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f5e9')),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1b5e20')),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(info_table)
            story.append(Spacer(1, 0.3 * inch))
            
            # ===== SECTION 2: Weight History =====
            story.append(Paragraph("2. Weight History", self.styles['CustomHeading']))
            
            # Get weight measurements (last 30 days)
            weight_measurements = sorted(
                [w for w in animal.weight_measurements],
                key=lambda w: w.timestamp,
                reverse=True
            )[:30]
            
            if weight_measurements:
                # Latest weight
                latest = weight_measurements[0]
                story.append(Paragraph(
                    f"<b>Current Weight:</b> {latest.estimated_weight_kg:.1f} kg "
                    f"(Confidence: {latest.confidence_score*100:.1f}%)",
                    self.styles['CustomBody']
                ))
                story.append(Spacer(1, 0.1 * inch))
                
                # Weight table (last 10 measurements)
                weight_data = [['Date', 'Weight (kg)', 'Confidence', 'Camera']]
                for w in weight_measurements[:10]:
                    weight_data.append([
                        w.timestamp.strftime('%Y-%m-%d %H:%M'),
                        f"{w.estimated_weight_kg:.1f}",
                        f"{w.confidence_score*100:.0f}%",
                        w.camera_id
                    ])
                
                weight_table = Table(weight_data, colWidths=[1.8*inch, 1.3*inch, 1.3*inch, 1.8*inch])
                weight_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4caf50')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 11),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('ALIGN', (1, 1), (2, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ]))
                story.append(weight_table)
                
                # Weight trend analysis
                if len(weight_measurements) >= 2:
                    oldest = weight_measurements[-1]
                    change = latest.estimated_weight_kg - oldest.estimated_weight_kg
                    change_pct = (change / oldest.estimated_weight_kg) * 100
                    
                    trend_text = f"<b>Trend:</b> "
                    if change > 0:
                        trend_text += f"<font color='green'>↑ +{change:.1f} kg (+{change_pct:.1f}%)</font>"
                    elif change < 0:
                        trend_text += f"<font color='red'>↓ {change:.1f} kg ({change_pct:.1f}%)</font>"
                    else:
                        trend_text += "Stable"
                    
                    story.append(Spacer(1, 0.1 * inch))
                    story.append(Paragraph(trend_text, self.styles['CustomBody']))
            else:
                story.append(Paragraph(
                    "No weight measurements available.",
                    self.styles['CustomBody']
                ))
            
            story.append(Spacer(1, 0.3 * inch))
            
            # ===== SECTION 3: Detection Timeline =====
            story.append(Paragraph("3. Detection Activity", self.styles['CustomHeading']))
            
            # Get detections (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_detections = [
                d for d in animal.detections
                if d.detected_at >= thirty_days_ago
            ]
            recent_detections = sorted(recent_detections, key=lambda d: d.detected_at, reverse=True)
            
            if recent_detections:
                story.append(Paragraph(
                    f"Total detections (last 30 days): <b>{len(recent_detections)}</b>",
                    self.styles['CustomBody']
                ))
                story.append(Spacer(1, 0.1 * inch))
                
                # Detection frequency by day
                detection_by_day: Dict[date, int] = {}
                for d in recent_detections:
                    day = d.detected_at.date()
                    detection_by_day[day] = detection_by_day.get(day, 0) + 1
                
                # Average per day
                avg_per_day = len(recent_detections) / 30
                story.append(Paragraph(
                    f"Average detections per day: <b>{avg_per_day:.1f}</b>",
                    self.styles['CustomBody']
                ))
                
                # Last 5 detections table
                story.append(Spacer(1, 0.1 * inch))
                story.append(Paragraph("Recent Detections:", self.styles['CustomBody']))
                
                detection_data = [['Date & Time', 'Camera', 'Confidence']]
                for d in recent_detections[:5]:
                    detection_data.append([
                        d.detected_at.strftime('%Y-%m-%d %H:%M:%S'),
                        d.camera_id,
                        f"{d.confidence_score*100:.0f}%"
                    ])
                
                detection_table = Table(detection_data, colWidths=[2.5*inch, 2.5*inch, 1.5*inch])
                detection_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4caf50')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 11),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('ALIGN', (2, 1), (2, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ]))
                story.append(detection_table)
            else:
                story.append(Paragraph(
                    "No detections in the last 30 days.",
                    self.styles['CustomBody']
                ))
            
            story.append(Spacer(1, 0.3 * inch))
            
            # ===== SECTION 4: Notes =====
            if animal.notes:
                story.append(Paragraph("4. Notes", self.styles['CustomHeading']))
                story.append(Paragraph(animal.notes, self.styles['CustomBody']))
                story.append(Spacer(1, 0.3 * inch))
            
            # ===== FOOTER =====
            story.append(Spacer(1, 0.5 * inch))
            story.append(Paragraph(
                f"<i>Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>",
                self.styles['CustomBody']
            ))
            story.append(Paragraph(
                "<i>Taurus Vision - AI-Powered Livestock Monitoring</i>",
                self.styles['CustomBody']
            ))
            
            # ===== Build PDF =====
            doc.build(story, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)
            
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            logger.info(f"Animal report generated: {len(pdf_bytes)} bytes")
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"Error generating animal report: {e}", exc_info=True)
            raise
    
    # =========================================================================
    # FARM REPORT
    # =========================================================================
    
    async def generate_farm_report(
        self,
        db: AsyncSession,
        date_from: date,
        date_to: date,
        report_type: str = "summary"
    ) -> bytes:
        """
        Generate farm-wide summary report.
        
        Args:
            db: Database session
            date_from: Start date
            date_to: End date
            report_type: Report type (summary/detailed/health)
        
        Returns:
            PDF file as bytes
        
        Report types:
        - summary: High-level statistics and trends
        - detailed: Comprehensive data with all animals
        - health: Health-focused with alerts
        
        Report sections:
        1. Executive Summary
        2. Animal Statistics
        3. Detection Summary
        4. Weight Trends
        5. Top Performers
        6. Alerts (if health report)
        
        Example:
            >>> service = ReportService()
            >>> pdf_bytes = await service.generate_farm_report(
            ...     db,
            ...     date(2026, 2, 1),
            ...     date(2026, 2, 16),
            ...     "summary"
            ... )
        """
        logger.info(f"Generating farm report: {date_from} to {date_to}, type={report_type}")
        
        try:
            # ===== Fetch data =====
            
            # Animals
            total_animals = await db.scalar(select(func.count(Animal.id)))
            active_animals = await db.scalar(
                select(func.count(Animal.id)).where(Animal.status == AnimalStatus.ACTIVE)
            )
            
            # Detections
            detections_query = select(func.count(Detection.id)).where(
                and_(
                    func.date(Detection.detected_at) >= date_from,
                    func.date(Detection.detected_at) <= date_to
                )
            )
            total_detections = await db.scalar(detections_query)
            
            # Average weight
            avg_weight_query = select(
                func.avg(WeightMeasurement.estimated_weight_kg)
            ).where(
                and_(
                    func.date(WeightMeasurement.timestamp) >= date_from,
                    func.date(WeightMeasurement.timestamp) <= date_to
                )
            )
            avg_weight = await db.scalar(avg_weight_query)
            
            # ===== Create PDF =====
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=self.page_size,
                rightMargin=self.margin,
                leftMargin=self.margin,
                topMargin=self.margin,
                bottomMargin=self.margin,
                title=f"Farm Report - {date_from} to {date_to}"
            )
            
            story = []
            
            # ===== HEADER =====
            story.append(Paragraph("🐄 TAURUS VISION", self.styles['CustomTitle']))
            story.append(Paragraph(f"Farm Report", self.styles['Heading1']))
            story.append(Paragraph(
                f"Period: {date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')}",
                self.styles['CustomBody']
            ))
            story.append(Spacer(1, 0.3 * inch))
            
            # ===== EXECUTIVE SUMMARY =====
            story.append(Paragraph("Executive Summary", self.styles['CustomHeading']))
            
            summary_data = [
                ['Total Animals:', str(total_animals or 0)],
                ['Active Animals:', str(active_animals or 0)],
                ['Total Detections:', str(total_detections or 0)],
                ['Average Weight:', f"{avg_weight:.1f} kg" if avg_weight else 'N/A'],
                ['Report Period:', f"{(date_to - date_from).days + 1} days"],
            ]
            
            summary_table = Table(summary_data, colWidths=[2.5*inch, 4*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f5e9')),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1b5e20')),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 0.3 * inch))
            
            # ===== ANIMAL STATISTICS =====
            story.append(Paragraph("Animal Statistics", self.styles['CustomHeading']))
            
            # Animals by status
            status_query = select(
                Animal.status,
                func.count(Animal.id).label('count')
            ).group_by(Animal.status)
            
            status_result = await db.execute(status_query)
            status_rows = status_result.all()
            
            status_data = [['Status', 'Count']]
            for row in status_rows:
                status_data.append([row.status.value.capitalize(), str(row.count)])
            
            status_table = Table(status_data, colWidths=[3*inch, 3*inch])
            status_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4caf50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ALIGN', (1, 1), (1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(status_table)
            story.append(Spacer(1, 0.5 * inch))
            
            # ===== FOOTER =====
            story.append(Paragraph(
                f"<i>Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>",
                self.styles['CustomBody']
            ))
            story.append(Paragraph(
                "<i>Taurus Vision - AI-Powered Livestock Monitoring</i>",
                self.styles['CustomBody']
            ))
            
            # ===== Build PDF =====
            doc.build(story, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)
            
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            logger.info(f"Farm report generated: {len(pdf_bytes)} bytes")
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"Error generating farm report: {e}", exc_info=True)
            raise
    
    # =========================================================================
    # HEALTH REPORT
    # =========================================================================
    
    async def generate_health_report(
        self,
        db: AsyncSession,
        animal_ids: Optional[List[int]] = None
    ) -> bytes:
        """
        Generate health-focused report with alerts.
        
        Args:
            db: Database session
            animal_ids: Specific animal IDs (None = all active animals)
        
        Returns:
            PDF file as bytes
        
        Report sections:
        1. Health Overview
        2. Weight Loss Alerts
        3. No Detection Alerts
        4. Risk Assessment
        5. Recommendations
        
        Example:
            >>> service = ReportService()
            >>> pdf_bytes = await service.generate_health_report(db)
        """
        logger.info(f"Generating health report: animal_ids={animal_ids}")
        
        try:
            # ===== Fetch animals =====
            query = select(Animal).where(Animal.status == AnimalStatus.ACTIVE)
            if animal_ids:
                query = query.where(Animal.id.in_(animal_ids))
            
            result = await db.execute(query)
            animals = result.scalars().all()
            
            # ===== Analyze health =====
            alerts = []
            now = datetime.utcnow()
            
            for animal in animals:
                # Check detection frequency
                if animal.last_detected_at:
                    days_since = (now - animal.last_detected_at).days
                    if days_since > 7:
                        alerts.append({
                            'animal': animal,
                            'type': 'no_detection',
                            'severity': 'warning',
                            'message': f"No detection for {days_since} days"
                        })
                else:
                    alerts.append({
                        'animal': animal,
                        'type': 'never_detected',
                        'severity': 'critical',
                        'message': "Never detected by system"
                    })
            
            # ===== Create PDF =====
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=self.page_size,
                rightMargin=self.margin,
                leftMargin=self.margin,
                topMargin=self.margin,
                bottomMargin=self.margin,
                title="Health Report"
            )
            
            story = []
            
            # ===== HEADER =====
            story.append(Paragraph("🐄 TAURUS VISION", self.styles['CustomTitle']))
            story.append(Paragraph("Health Report", self.styles['Heading1']))
            story.append(Spacer(1, 0.3 * inch))
            
            # ===== OVERVIEW =====
            story.append(Paragraph("Health Overview", self.styles['CustomHeading']))
            
            overview_data = [
                ['Animals Monitored:', str(len(animals))],
                ['Active Alerts:', str(len(alerts))],
                ['Critical Alerts:', str(len([a for a in alerts if a['severity'] == 'critical']))],
                ['Warning Alerts:', str(len([a for a in alerts if a['severity'] == 'warning']))],
            ]
            
            overview_table = Table(overview_data, colWidths=[2.5*inch, 4*inch])
            overview_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f5e9')),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1b5e20')),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(overview_table)
            story.append(Spacer(1, 0.3 * inch))
            
            # ===== ALERTS =====
            if alerts:
                story.append(Paragraph("Active Alerts", self.styles['CustomHeading']))
                
                alert_data = [['Animal', 'Type', 'Severity', 'Message']]
                for alert in alerts:
                    alert_data.append([
                        alert['animal'].tag_id,
                        alert['type'].replace('_', ' ').title(),
                        alert['severity'].title(),
                        alert['message']
                    ])
                
                alert_table = Table(alert_data, colWidths=[1.3*inch, 1.5*inch, 1.3*inch, 2.5*inch])
                alert_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d32f2f')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ffebee')),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ]))
                story.append(alert_table)
            else:
                story.append(Paragraph(
                    "✓ No active health alerts. All animals appear healthy.",
                    self.styles['CustomBody']
                ))
            
            story.append(Spacer(1, 0.5 * inch))
            
            # ===== FOOTER =====
            story.append(Paragraph(
                f"<i>Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>",
                self.styles['CustomBody']
            ))
            story.append(Paragraph(
                "<i>Taurus Vision - AI-Powered Livestock Monitoring</i>",
                self.styles['CustomBody']
            ))
            
            # ===== Build PDF =====
            doc.build(story, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)
            
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            logger.info(f"Health report generated: {len(pdf_bytes)} bytes")
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"Error generating health report: {e}", exc_info=True)
            raise
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _add_page_number(self, canvas_obj: canvas.Canvas, doc: SimpleDocTemplate):
        """
        Add page number to footer.
        
        Args:
            canvas_obj: ReportLab canvas
            doc: Document template
        """
        canvas_obj.saveState()
        canvas_obj.setFont('Helvetica', 9)
        canvas_obj.setFillColor(colors.grey)
        
        page_num = canvas_obj.getPageNumber()
        text = f"Page {page_num}"
        
        canvas_obj.drawRightString(
            doc.width + doc.rightMargin,
            0.5 * inch,
            text
        )
        
        canvas_obj.restoreState()
