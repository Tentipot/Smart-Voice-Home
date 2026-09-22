
import gc

import torch

from app.resources.model_lifecycle import ModelLifecycle
from app.resources.model_types import ModelBackend


class PyTorchModelLifecycle(ModelLifecycle):
    """
    Backend cleanup for PyTorch-backed model resources.

    ModelManager must drop its owning reference before calling
    cleanup(). Callers must also release their model leases and
    must not retain separate references to the resource.

    PyTorch may keep unused CUDA memory in its caching allocator.
    empty_cache() releases unused cached blocks to the CUDA driver,
    but cannot free tensors that are still referenced.
    """

    @property
    def backend(self) -> ModelBackend:
        return ModelBackend.PYTORCH

    def cleanup(self) -> None:
        """
        Collect unreachable Python objects, then release unused
        cached CUDA memory.
        """

        gc.collect()

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        gc.collect()