import ctypes
import os
import sys
from pathlib import Path


_DLL_DIRECTORY_HANDLES: list[object] = []
_DLL_LIBRARY_HANDLES: list[object] = []


def register_nvidia_dll_directories() -> None:
    """
    Make NVIDIA DLLs installed in the active Python environment
    discoverable and loadable on Windows.

    os.add_dll_directory() registers the package directories with the
    Windows loader. CTranslate2 CUDA inference additionally requires
    cuBLAS/cuDNN to be loaded into the process explicitly in the tested
    Windows environment.

    Keep both directory and library handles alive for the process
    lifetime.
    """

    if sys.platform != "win32":
        return

    if _DLL_DIRECTORY_HANDLES:
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
            _DLL_DIRECTORY_HANDLES.append(handle)

    for library_name in (
        "cublas64_12.dll",
        "cudnn64_9.dll",
    ):
        try:
            library = ctypes.WinDLL(library_name)
        except OSError as exc:
            raise RuntimeError(
                f"Required NVIDIA DLL could not be loaded: "
                f"{library_name}"
            ) from exc

        _DLL_LIBRARY_HANDLES.append(library)
