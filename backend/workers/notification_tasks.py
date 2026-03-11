"""
Taurus Vision — Notification Celery Tasks
"""
def send_alert_email(*args, **kwargs): pass
def send_alert_notification(*args, **kwargs): pass
def send_bulk_notifications(*args, **kwargs): pass

# delay mock for testing without celery
class _FakeTask:
    def __init__(self, fn):
        self._fn = fn
    def delay(self, *args, **kwargs):
        return None
    def __call__(self, *args, **kwargs):
        return self._fn(*args, **kwargs)

send_alert_email = _FakeTask(send_alert_email)
send_alert_notification = _FakeTask(send_alert_notification)
send_bulk_notifications = _FakeTask(send_bulk_notifications)