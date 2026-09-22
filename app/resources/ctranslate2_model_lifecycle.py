
import gc

from app.resources.model_lifecycle import ModelLifecycle
from app.resources.model_types import ModelBackend


class CTranslate2ModelLifecycle(ModelLifecycle):
    """
    Backend cleanup for CTranslate2-backed model resources.

    ModelManager must drop its owning reference before calling
    cleanup(). Callers must release their model leases and must
    not retain separate references to the resource.

    CTranslate2 manages its own model allocations. This adapter
    does not invoke PyTorch CUDA cache cleanup.
    """

    @property
    def backend(self) -> ModelBackend:
        return ModelBackend.CTRANSLATE2

    def cleanup(self) -> None:
        """
        Collect unreachable Python objects after the owning
        model reference has been removed.
        """

        gc.collect()