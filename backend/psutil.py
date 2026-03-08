"""
psutil stub module — test muhiti uchun.
Haqiqiy psutil o'rnatilmaganda testlar ishlashi uchun mock.
"""


def cpu_percent(interval=None, percpu=False):
    if percpu:
        return [30.0, 30.0, 30.0, 30.0]
    return 30.0


def cpu_count(logical=True):
    """CPU yadrolar soni (stub: 4)."""
    return 4


def cpu_freq():
    class CpuFreq:
        current = 2400.0
        min = 800.0
        max = 3200.0
    return CpuFreq()


def virtual_memory():
    class VMemory:
        total = 8 * 1024 ** 3
        available = 4 * 1024 ** 3
        used = 4 * 1024 ** 3
        percent = 50.0
    return VMemory()


def disk_usage(path="/"):
    class DiskUsage:
        total = 100 * 1024 ** 3
        used = 50 * 1024 ** 3
        free = 50 * 1024 ** 3
        percent = 50.0
    return DiskUsage()


def process_iter(attrs=None):
    return iter([])


def net_io_counters():
    class NetIO:
        bytes_sent = 0
        bytes_recv = 0
        packets_sent = 0
        packets_recv = 0
    return NetIO()


def boot_time():
    import time
    return time.time() - 3600


class Process:
    def __init__(self, pid=None):
        self.pid = pid or 1

    def memory_info(self):
        class MemInfo:
            rss = 100 * 1024 ** 2
            vms = 200 * 1024 ** 2
        return MemInfo()

    def cpu_percent(self, interval=None):
        return 5.0

    def status(self):
        return "running"