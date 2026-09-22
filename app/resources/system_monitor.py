import platform
import socket
from typing import Any

import psutil
import pynvml


BYTES_PER_GB = 1024 ** 3
BYTES_PER_MB = 1024 ** 2


def _round(value: float, digits: int = 1) -> float:
    return round(float(value), digits)


def get_cpu_status() -> dict[str, Any]:
    return {
        "usage_percent": _round(psutil.cpu_percent(interval=0.2)),
        "logical_cores": psutil.cpu_count(logical=True),
        "physical_cores": psutil.cpu_count(logical=False),
    }


def get_memory_status() -> dict[str, Any]:
    memory = psutil.virtual_memory()

    return {
        "usage_percent": _round(memory.percent),
        "used_gb": _round(memory.used / BYTES_PER_GB, 2),
        "available_gb": _round(memory.available / BYTES_PER_GB, 2),
        "total_gb": _round(memory.total / BYTES_PER_GB, 2),
    }


def get_gpu_status() -> dict[str, Any]:
    try:
        pynvml.nvmlInit()

        device_count = pynvml.nvmlDeviceGetCount()

        if device_count == 0:
            return {
                "available": False,
                "reason": "No NVIDIA GPU detected",
            }

        handle = pynvml.nvmlDeviceGetHandleByIndex(0)

        name = pynvml.nvmlDeviceGetName(handle)

        if isinstance(name, bytes):
            name = name.decode("utf-8")

        utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
        memory = pynvml.nvmlDeviceGetMemoryInfo(handle)

        try:
            temperature = pynvml.nvmlDeviceGetTemperature(
                handle,
                pynvml.NVML_TEMPERATURE_GPU,
            )
        except pynvml.NVMLError:
            temperature = None

        return {
            "available": True,
            "name": name,
            "usage_percent": int(utilization.gpu),
            "memory_controller_percent": int(utilization.memory),
            "temperature_c": temperature,
            "vram_used_mb": round(memory.used / BYTES_PER_MB),
            "vram_free_mb": round(memory.free / BYTES_PER_MB),
            "vram_total_mb": round(memory.total / BYTES_PER_MB),
            "vram_usage_percent": _round(
                (memory.used / memory.total) * 100
            ),
        }

    except pynvml.NVMLError as exc:
        return {
            "available": False,
            "reason": str(exc),
        }

    finally:
        try:
            pynvml.nvmlShutdown()
        except pynvml.NVMLError:
            pass


def get_system_status() -> dict[str, Any]:
    return {
        "server": "online",
        "hostname": socket.gethostname(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "cpu": get_cpu_status(),
        "memory": get_memory_status(),
        "gpu": get_gpu_status(),
    }