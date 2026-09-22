
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from threading import Condition, RLock
from typing import Any

from app.resources.model_handle import ModelHandle
from app.resources.model_lifecycle import ModelLifecycle
from app.resources.model_types import (
    ModelDescriptor,
    ModelId,
)


class _ModelState(str, Enum):
    UNLOADED = "unloaded"
    LOADED = "loaded"
    UNLOADING = "unloading"


@dataclass(slots=True)
class _ModelEntry:
    descriptor: ModelDescriptor
    factory: Callable[[], Any]
    lifecycle: ModelLifecycle
    resource: Any | None = None
    active_leases: int = 0
    state: _ModelState = _ModelState.UNLOADED


class ModelManager:
    """
    Owns registered model-backed resources and their active leases.

    Responsibilities:
    - register model factories and lifecycle adapters
    - lazily create resources on first acquire
    - keep loaded resources resident after lease release
    - track active leases
    - explicitly unload unused resources
    - prevent reload while cleanup is in progress

    This version intentionally does not implement:
    - automatic eviction
    - VRAM budgeting
    - LRU policy
    - gaming/resource modes
    - background preloading
    - inference scheduling

    Callers must not retain resource references beyond their leases.
    """

    def __init__(self) -> None:
        self._entries: dict[ModelId, _ModelEntry] = {}
        self._lock = RLock()
        self._condition = Condition(self._lock)

    def register(
        self,
        *,
        descriptor: ModelDescriptor,
        factory: Callable[[], Any],
        lifecycle: ModelLifecycle,
    ) -> None:
        """
        Register a model without loading it.
        """

        if lifecycle.backend != descriptor.backend:
            raise ValueError(
                "Lifecycle backend does not match "
                "the model descriptor backend."
            )

        with self._condition:
            if descriptor.model_id in self._entries:
                raise ValueError(
                    "Model is already registered: "
                    f"{descriptor.model_id.value}"
                )

            self._entries[descriptor.model_id] = _ModelEntry(
                descriptor=descriptor,
                factory=factory,
                lifecycle=lifecycle,
            )

    def acquire(
        self,
        model_id: ModelId,
    ) -> ModelHandle[Any]:
        """
        Acquire a lease for a registered model.

        Wait if the previous instance is still being unloaded.
        Keep the model resident after the lease is released.
        """

        with self._condition:
            entry = self._get_entry(model_id)

            while entry.state == _ModelState.UNLOADING:
                self._condition.wait()

            if entry.state == _ModelState.UNLOADED:
                resource = entry.factory()

                if resource is None:
                    raise RuntimeError(
                        "Model factory returned None for: "
                        f"{model_id.value}"
                    )

                entry.resource = resource
                entry.state = _ModelState.LOADED

            if entry.resource is None:
                raise RuntimeError(
                    "Loaded model has no resource: "
                    f"{model_id.value}"
                )

            entry.active_leases += 1

            return ModelHandle(
                resource=entry.resource,
                release_callback=lambda: self._release(
                    model_id
                ),
            )

    def unload(
        self,
        model_id: ModelId,
    ) -> bool:
        """
        Unload a model that has no active leases.

        Remove the manager's owning reference before backend cleanup.

        Keep the entry in UNLOADING until cleanup finishes, so a
        concurrent acquire cannot start loading a new instance.
        """

        with self._condition:
            entry = self._get_entry(model_id)

            while entry.state == _ModelState.UNLOADING:
                self._condition.wait()

            if entry.active_leases != 0:
                raise RuntimeError(
                    "Cannot unload model with active leases: "
                    f"{model_id.value} "
                    f"({entry.active_leases} active)"
                )

            if entry.state == _ModelState.UNLOADED:
                return False

            if entry.resource is None:
                raise RuntimeError(
                    "Loaded model has no resource: "
                    f"{model_id.value}"
                )

            entry.state = _ModelState.UNLOADING
            entry.resource = None
            lifecycle = entry.lifecycle

        try:
            lifecycle.cleanup()
        finally:
            with self._condition:
                entry.state = _ModelState.UNLOADED
                self._condition.notify_all()

        return True

    def unload_all(self) -> list[ModelId]:
        """
        Unload all currently loaded models without active leases.

        Models with active leases are left untouched.
        """

        with self._condition:
            unloadable = [
                model_id
                for model_id, entry in self._entries.items()
                if (
                    entry.state == _ModelState.LOADED
                    and entry.resource is not None
                    and entry.active_leases == 0
                )
            ]

        unloaded: list[ModelId] = []

        for model_id in unloadable:
            if self.unload(model_id):
                unloaded.append(model_id)

        return unloaded

    def is_loaded(
        self,
        model_id: ModelId,
    ) -> bool:
        with self._condition:
            entry = self._get_entry(model_id)

            return (
                entry.state == _ModelState.LOADED
                and entry.resource is not None
            )

    def active_leases(
        self,
        model_id: ModelId,
    ) -> int:
        with self._condition:
            entry = self._get_entry(model_id)

            return entry.active_leases

    def _release(
        self,
        model_id: ModelId,
    ) -> None:
        with self._condition:
            entry = self._get_entry(model_id)

            if entry.active_leases <= 0:
                raise RuntimeError(
                    "Model lease count is already zero: "
                    f"{model_id.value}"
                )

            entry.active_leases -= 1

    def _get_entry(
        self,
        model_id: ModelId,
    ) -> _ModelEntry:
        try:
            return self._entries[model_id]
        except KeyError as exc:
            raise KeyError(
                "Model is not registered: "
                f"{model_id.value}"
            ) from exc