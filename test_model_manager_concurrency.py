
import gc
import threading
import time
import weakref

from app.resources.model_lifecycle import ModelLifecycle
from app.resources.model_manager import ModelManager
from app.resources.model_types import (
    ModelBackend,
    ModelDescriptor,
    ModelId,
)


MODEL_ID = ModelId.BUZZ_BG


class FakeResource:
    def __init__(self, generation: int) -> None:
        self.generation = generation


class BlockingLifecycle(ModelLifecycle):
    def __init__(self) -> None:
        self.cleanup_started = threading.Event()
        self.allow_cleanup_to_finish = threading.Event()
        self.cleanup_finished = threading.Event()

        self.cleanup_calls = 0
        self.resource_ref: (
            weakref.ReferenceType[FakeResource] | None
        ) = None

    @property
    def backend(self) -> ModelBackend:
        return ModelBackend.PYTORCH

    def cleanup(self) -> None:
        self.cleanup_calls += 1

        gc.collect()

        assert self.resource_ref is not None
        assert self.resource_ref() is None, (
            "Old resource is still alive when cleanup begins."
        )

        self.cleanup_started.set()

        if not self.allow_cleanup_to_finish.wait(timeout=5.0):
            raise RuntimeError(
                "Timed out waiting to finish cleanup."
            )

        self.cleanup_finished.set()


def main() -> None:
    lifecycle = BlockingLifecycle()

    created_resources: list[
        weakref.ReferenceType[FakeResource]
    ] = []

    factory_calls = 0

    def factory() -> FakeResource:
        nonlocal factory_calls

        factory_calls += 1

        resource = FakeResource(
            generation=factory_calls
        )

        created_resources.append(
            weakref.ref(resource)
        )

        return resource

    manager = ModelManager()

    manager.register(
        descriptor=ModelDescriptor(
            model_id=MODEL_ID,
            backend=ModelBackend.PYTORCH,
        ),
        factory=factory,
        lifecycle=lifecycle,
    )

    first_handle = manager.acquire(MODEL_ID)

    first_ref = weakref.ref(first_handle.resource)
    lifecycle.resource_ref = first_ref

    assert first_ref() is not None
    assert first_ref().generation == 1
    assert factory_calls == 1

    first_handle.release()

    assert manager.active_leases(MODEL_ID) == 0
    assert first_ref() is not None

    unload_errors: list[BaseException] = []
    acquire_errors: list[BaseException] = []

    acquired_generations: list[int] = []

    def unload_worker() -> None:
        try:
            assert manager.unload(MODEL_ID) is True
        except BaseException as exc:
            unload_errors.append(exc)

    def acquire_worker() -> None:
        try:
            with manager.acquire(MODEL_ID) as resource:
                acquired_generations.append(
                    resource.generation
                )
        except BaseException as exc:
            acquire_errors.append(exc)

    unload_thread = threading.Thread(
        target=unload_worker,
        name="unload-worker",
    )

    acquire_thread = threading.Thread(
        target=acquire_worker,
        name="acquire-worker",
    )

    try:
        unload_thread.start()

        if not lifecycle.cleanup_started.wait(timeout=5.0):
            raise RuntimeError(
                "Cleanup did not start. "
                f"Unload errors: {unload_errors!r}"
            )

        assert first_ref() is None, (
            "Old resource remains alive during cleanup."
        )

        assert manager.is_loaded(MODEL_ID) is False

        print(
            "OLD RESOURCE RELEASED BEFORE CLEANUP: PASS"
        )

        acquire_thread.start()

        time.sleep(0.25)

        assert acquire_thread.is_alive(), (
            "Acquire did not wait during cleanup."
        )

        assert factory_calls == 1, (
            "New model factory ran before cleanup finished."
        )

        assert acquired_generations == []

        print(
            "ACQUIRE WAITS DURING CLEANUP: PASS"
        )

    finally:
        lifecycle.allow_cleanup_to_finish.set()

        if unload_thread.ident is not None:
            unload_thread.join(timeout=5.0)

        if acquire_thread.ident is not None:
            acquire_thread.join(timeout=5.0)

    assert not unload_thread.is_alive()
    assert not acquire_thread.is_alive()

    if unload_errors:
        raise AssertionError(
            f"Unload worker failed: {unload_errors!r}"
        )

    if acquire_errors:
        raise AssertionError(
            f"Acquire worker failed: {acquire_errors!r}"
        )

    assert lifecycle.cleanup_finished.is_set()
    assert lifecycle.cleanup_calls == 1

    assert factory_calls == 2
    assert len(created_resources) == 2

    assert acquired_generations == [2]

    assert manager.is_loaded(MODEL_ID) is True
    assert manager.active_leases(MODEL_ID) == 0

    print(
        "RELOAD STARTS AFTER CLEANUP: PASS"
    )

    print(
        "NO OVERLAPPING MANAGER-OWNED INSTANCES: PASS"
    )

    print(
        "ALL CONCURRENCY TESTS PASSED"
    )


if __name__ == "__main__":
    main()