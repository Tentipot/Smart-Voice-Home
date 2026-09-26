
import gc
import weakref
from collections.abc import Callable

from app.resources.model_lifecycle import ModelLifecycle
from app.resources.model_manager import ModelManager
from app.resources.model_types import (
    ModelBackend,
    ModelDescriptor,
    ModelId,
)


class FakeResource:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeLifecycle(ModelLifecycle):
    def __init__(self, backend: ModelBackend) -> None:
        self._backend = backend
        self.cleanup_calls = 0
        self.on_cleanup: Callable[[], None] | None = None

    @property
    def backend(self) -> ModelBackend:
        return self._backend

    def cleanup(self) -> None:
        self.cleanup_calls += 1

        if self.on_cleanup is not None:
            self.on_cleanup()


def create_manager() -> tuple[
    ModelManager,
    FakeLifecycle,
    list[weakref.ReferenceType[FakeResource]],
]:
    lifecycle = FakeLifecycle(ModelBackend.PYTORCH)
    created: list[weakref.ReferenceType[FakeResource]] = []

    def factory() -> FakeResource:
        resource = FakeResource(
            name=f"resource-{len(created) + 1}"
        )
        created.append(weakref.ref(resource))
        return resource

    manager = ModelManager()

    manager.register(
        descriptor=ModelDescriptor(
            model_id=ModelId.BUZZ_BG,
            backend=ModelBackend.PYTORCH,
            estimated_vram_mb=3323,
        ),
        factory=factory,
        lifecycle=lifecycle,
    )

    return manager, lifecycle, created


def test_lazy_loading() -> None:
    manager, _, created = create_manager()

    assert manager.is_loaded(ModelId.BUZZ_BG) is False
    assert len(created) == 0

    handle = manager.acquire(ModelId.BUZZ_BG)

    assert manager.is_loaded(ModelId.BUZZ_BG) is True
    assert len(created) == 1
    assert manager.active_leases(ModelId.BUZZ_BG) == 1

    handle.release()

    assert manager.active_leases(ModelId.BUZZ_BG) == 0
    assert manager.is_loaded(ModelId.BUZZ_BG) is True

    print("LAZY LOADING: PASS")


def test_resident_reuse() -> None:
    manager, _, created = create_manager()

    first_handle = manager.acquire(ModelId.BUZZ_BG)
    first_ref = weakref.ref(first_handle.resource)
    first_handle.release()

    second_handle = manager.acquire(ModelId.BUZZ_BG)

    assert second_handle.resource is first_ref()
    assert len(created) == 1

    second_handle.release()

    print("RESIDENT REUSE: PASS")


def test_multiple_leases() -> None:
    manager, _, _ = create_manager()

    first_handle = manager.acquire(ModelId.BUZZ_BG)
    second_handle = manager.acquire(ModelId.BUZZ_BG)

    assert manager.active_leases(ModelId.BUZZ_BG) == 2
    assert first_handle.resource is second_handle.resource

    first_handle.release()

    assert manager.active_leases(ModelId.BUZZ_BG) == 1

    second_handle.release()

    assert manager.active_leases(ModelId.BUZZ_BG) == 0

    print("MULTIPLE LEASES: PASS")


def test_unload_rejected_with_active_lease() -> None:
    manager, lifecycle, _ = create_manager()

    handle = manager.acquire(ModelId.BUZZ_BG)

    try:
        manager.unload(ModelId.BUZZ_BG)
    except RuntimeError:
        pass
    else:
        raise AssertionError(
            "Unload must fail while a lease is active."
        )

    assert manager.is_loaded(ModelId.BUZZ_BG) is True
    assert lifecycle.cleanup_calls == 0

    handle.release()

    print("ACTIVE LEASE UNLOAD REJECTION: PASS")


def test_explicit_unload() -> None:
    manager, lifecycle, created = create_manager()

    handle = manager.acquire(ModelId.BUZZ_BG)
    resource_ref = weakref.ref(handle.resource)

    handle.release()

    assert resource_ref() is not None

    unloaded = manager.unload(ModelId.BUZZ_BG)

    assert unloaded is True
    assert manager.is_loaded(ModelId.BUZZ_BG) is False
    assert lifecycle.cleanup_calls == 1
    assert len(created) == 1

    gc.collect()
    assert resource_ref() is None

    unloaded_again = manager.unload(ModelId.BUZZ_BG)

    assert unloaded_again is False
    assert lifecycle.cleanup_calls == 1

    print("EXPLICIT UNLOAD: PASS")


def test_reload_after_unload() -> None:
    manager, _, created = create_manager()

    first_handle = manager.acquire(ModelId.BUZZ_BG)
    first_ref = weakref.ref(first_handle.resource)

    first_handle.release()
    manager.unload(ModelId.BUZZ_BG)

    assert first_ref() is None

    second_handle = manager.acquire(ModelId.BUZZ_BG)
    second_ref = weakref.ref(second_handle.resource)

    assert second_ref() is not None
    assert len(created) == 2

    second_handle.release()

    print("RELOAD AFTER UNLOAD: PASS")


def test_backend_mismatch() -> None:
    manager = ModelManager()
    lifecycle = FakeLifecycle(ModelBackend.CTRANSLATE2)

    try:
        manager.register(
            descriptor=ModelDescriptor(
                model_id=ModelId.BUZZ_BG,
                backend=ModelBackend.PYTORCH,
            ),
            factory=lambda: FakeResource("unused"),
            lifecycle=lifecycle,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Backend mismatch must be rejected."
        )

    print("BACKEND MISMATCH: PASS")


def test_resource_released_before_cleanup() -> None:
    manager, lifecycle, _ = create_manager()

    handle = manager.acquire(ModelId.BUZZ_BG)
    resource_ref = weakref.ref(handle.resource)

    handle.release()

    def verify_during_cleanup() -> None:
        gc.collect()

        assert resource_ref() is None, (
            "Model resource is still referenced "
            "when backend cleanup begins."
        )

        assert manager.is_loaded(ModelId.BUZZ_BG) is False

    lifecycle.on_cleanup = verify_during_cleanup

    assert manager.unload(ModelId.BUZZ_BG) is True
    assert lifecycle.cleanup_calls == 1

    print("RESOURCE RELEASED BEFORE CLEANUP: PASS")


def test_handle_drops_reference_on_release() -> None:
    manager, _, _ = create_manager()

    handle = manager.acquire(ModelId.BUZZ_BG)
    resource_ref = weakref.ref(handle.resource)

    handle.release()

    assert handle.released is True

    manager.unload(ModelId.BUZZ_BG)
    gc.collect()

    assert resource_ref() is None, (
        "Released ModelHandle still retains the resource."
    )

    print("HANDLE DROPS REFERENCE: PASS")


def main() -> None:
    test_lazy_loading()
    test_resident_reuse()
    test_multiple_leases()
    test_unload_rejected_with_active_lease()
    test_explicit_unload()
    test_reload_after_unload()
    test_backend_mismatch()
    test_resource_released_before_cleanup()
    test_handle_drops_reference_on_release()

    print("ALL MODEL MANAGER TESTS PASSED")


if __name__ == "__main__":
    main()