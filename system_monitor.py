import psutil
import time

# A class to calculate network speed over time
class NetworkMonitor:
    def __init__(self):
        self.last_check = time.time()
        self.last_io = psutil.net_io_counters()

    def get_speed(self):
        """Calculates network upload and download speed in bytes/sec."""
        now = time.time()
        current_io = psutil.net_io_counters()

        elapsed_time = now - self.last_check
        # Avoid division by zero on the first run
        if elapsed_time < 0.1:
            return (0, 0) 

        bytes_sent = current_io.bytes_sent - self.last_io.bytes_sent
        bytes_recv = current_io.bytes_recv - self.last_io.bytes_recv

        upload_speed = bytes_sent / elapsed_time
        download_speed = bytes_recv / elapsed_time

        self.last_check = now
        self.last_io = current_io

        return (upload_speed, download_speed)

def format_bytes(byte_count):
    """Formats bytes into a human-readable format (KB, MB, GB)."""
    if byte_count is None:
        return "0 B"
    power = 1024
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while byte_count >= power and n < len(power_labels):
        byte_count /= power
        n += 1
    return f"{byte_count:.1f}{power_labels[n]}B"

def get_cpu_usage():
    """Returns formatted CPU usage string."""
    # interval=None makes it non-blocking and compares against last call
    return f"CPU  : {psutil.cpu_percent(interval=None):>5.1f}%"

def get_memory_usage():
    """Returns formatted memory usage string."""
    mem = psutil.virtual_memory()
    return f"Mem  : {mem.percent:>5.1f}% ({format_bytes(mem.used)} / {format_bytes(mem.total)})"

def get_disk_usage(path='/'):
    """Returns formatted disk usage string for the given path."""
    try:
        disk = psutil.disk_usage(path)
        return f"Disk : {disk.percent:>5.1f}% ({format_bytes(disk.used)} / {format_bytes(disk.total)})"
    except FileNotFoundError:
        return f"Disk : Path '{path}' not found."


def get_formatted_network_speed(upload_speed, download_speed):
    """Returns formatted network speed string."""
    return f"Net  : ↓{format_bytes(download_speed)}/s ↑{format_bytes(upload_speed)}/s"