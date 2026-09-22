
from abc import ABC, abstractmethod

from app.resources.model_types import ModelBackend


class ModelLifecycle(ABC):
    """
    Backend-specific cleanup after ModelManager drops its
    owning reference to a model-backed resource.

    ModelManager decides when a model is unloaded. The lifecycle
    adapter performs backend cleanup only after the manager has
    released its own reference.

    Callers must not retain or use a resource after its lease ends.
    """

    @property
    @abstractmethod
    def backend(self) -> ModelBackend:
        raise NotImplementedError

    @abstractmethod
    def cleanup(self) -> None:
        """
        Collect released resources and perform backend-specific
        cleanup.

        This method does not receive the model instance, so it
        cannot accidentally keep that instance alive.
        """

        raise NotImplementedError