"""
Taurus Vision — Finance Celery Tasks

TASKLAR:
    finance.monthly_summary    — Har oyning 1-kunida o'tgan oy xulosasi
    finance.weekly_summary     — Har dushanba o'tgan hafta xulosasi

ISHLATISH:
    from workers.tasks.finance_tasks import monthly_finance_summary
    monthly_finance_summary.delay()

JADVAL (celery_config.py da qo'shilishi kerak):
    "finance-monthly": {
        "task": "finance.monthly_summary",
        "schedule": crontab(day_of_month=1, hour=6, minute=0),
    },
    "finance-weekly": {
        "task": "finance.weekly_summary",
        "schedule": crontab(day_of_week=1, hour=7, minute=0),
    },
"""

import asyncio
import logging
from datetime import date, timedelta

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run(coro):
    """Async coroutine ni sync kontekstda ishlatish."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="finance.monthly_summary",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def monthly_finance_summary(self):
    """
    O'tgan oy moliyaviy xulosasini hisoblash va notification yuborish.

    Har oyning 1-kunida 06:00 da ishlaydi.
    O'tgan oy: date_from=birinchi kun, date_to=oxirgi kun.
    """
    try:
        return _run(_monthly_summary_async())
    except Exception as exc:
        logger.error(f"monthly_finance_summary xatosi: {exc}", exc_info=True)
        raise self.retry(exc=exc)


async def _monthly_summary_async():
    from app.core.database import AsyncSessionFactory
    from app.services.finance_service import FinanceService
    from app.services.notification_service import NotificationService

    today     = date.today()
    # O'tgan oy
    first_this = today.replace(day=1)
    last_prev  = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)

    async with AsyncSessionFactory() as db:
        try:
            svc     = FinanceService(db)
            summary = await svc.get_summary(first_prev, last_prev)

            logger.info(
                "[Finance] Oylik xulosa hisoblandi",
                extra={"extra_data": {
                    "period":   summary.period_label,
                    "income":   summary.total_income,
                    "expense":  summary.total_expense,
                    "profit":   summary.net_profit,
                    "roi":      summary.roi_percent,
                }},
            )

            # Notification (agar SMTP sozlangan bo'lsa)
            notif_svc = NotificationService()
            if notif_svc.is_configured:
                profit_str = f"{summary.net_profit:,} UZS"
                roi_str    = f"{summary.roi_percent:.1f}%"
                sign       = "✅" if summary.net_profit >= 0 else "⚠️"
                subject    = f"[Taurus Vision] {summary.period_label} — Moliyaviy xulosa"
                body = (
                    f"<h2>{sign} {summary.period_label} — Moliyaviy Xulosa</h2>"
                    f"<table style='border-collapse:collapse;width:100%'>"
                    f"<tr><td><b>Jami daromad:</b></td><td style='color:#059669'>"
                    f"+{summary.total_income:,} UZS</td></tr>"
                    f"<tr><td><b>Jami xarajat:</b></td><td style='color:#DC2626'>"
                    f"-{summary.total_expense:,} UZS</td></tr>"
                    f"<tr><td><b>Sof foyda:</b></td><td><b>{profit_str}</b></td></tr>"
                    f"<tr><td><b>ROI:</b></td><td><b>{roi_str}</b></td></tr>"
                    f"</table>"
                    f"<p>To'liq hisobot: <a href='/finance'>Taurus Vision Finance</a></p>"
                )
                await notif_svc.send_raw_email(
                    subject    = subject,
                    html_body  = body,
                    recipients = notif_svc.get_recipients(),
                )

            return {
                "status":  "ok",
                "period":  summary.period_label,
                "income":  summary.total_income,
                "expense": summary.total_expense,
                "profit":  summary.net_profit,
            }

        except Exception as exc:
            logger.error(f"_monthly_summary_async: {exc}", exc_info=True)
            raise


@celery_app.task(
    name="finance.weekly_summary",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def weekly_finance_summary(self):
    """
    O'tgan hafta moliyaviy xulosasi.

    Har dushanba 07:00 da ishlaydi.
    """
    try:
        return _run(_weekly_summary_async())
    except Exception as exc:
        logger.error(f"weekly_finance_summary xatosi: {exc}", exc_info=True)
        raise self.retry(exc=exc)


async def _weekly_summary_async():
    from app.core.database import AsyncSessionFactory
    from app.services.finance_service import FinanceService

    today      = date.today()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)

    async with AsyncSessionFactory() as db:
        try:
            svc     = FinanceService(db)
            summary = await svc.get_summary(last_monday, last_sunday)

            logger.info(
                "[Finance] Haftalik xulosa hisoblandi",
                extra={"extra_data": {
                    "period":  summary.period_label,
                    "income":  summary.total_income,
                    "expense": summary.total_expense,
                    "profit":  summary.net_profit,
                }},
            )

            return {
                "status":  "ok",
                "period":  summary.period_label,
                "income":  summary.total_income,
                "expense": summary.total_expense,
                "profit":  summary.net_profit,
            }

        except Exception as exc:
            logger.error(f"_weekly_summary_async: {exc}", exc_info=True)
            raise