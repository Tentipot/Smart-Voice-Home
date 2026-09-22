
import os
import sys
from pathlib import Path


_DLL_HANDLES: list[object] = []


def register_nvidia_dll_directories() -> None:
    """
    Make NVIDIA DLLs installed in the active Python environment
    discoverable on Windows.

    Keep os.add_dll_directory handles alive for the process lifetime.
    """

    if sys.platform != "win32":
        return

    if _DLL_HANDLES:
        return

    nvidia_root = (
        Path(sys.prefix)
        / "Lib"
        / "site-packages"
        / "nvidia"
    )

    for package in ("cublas", "cuda_nvrtc", "cudnn"):
        directory = nvidia_root / package / "bin"

        if directory.is_dir():
            handle = os.add_dll_directory(str(directory))
            _DLL_HANDLES.append(handle)