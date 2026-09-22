
from collections.abc import Callable
from types import TracebackType
from typing import Generic, TypeVar, cast


T = TypeVar("T")


class ModelHandle(Generic[T]):
    """
    Temporary lease for a model-backed resource.

    The manager owns the resource. The handle exposes it only while
    the lease is active and drops its own reference upon release.

    Releasing a lease does not unload the model.
    """

    def __init__(
        self,
        *,
        resource: T,
        release_callback: Callable[[], None],
    ) -> None:
        self._resource: T | None = resource
        self._release_callback = release_callback
        self._released = False

    @property
    def resource(self) -> T:
        """
        Return the resource while the lease is active.
        """

        if self._released:
            raise RuntimeError(
                "ModelHandle has already been released."
            )

        if self._resource is None:
            raise RuntimeError(
                "Active ModelHandle has no resource."
            )

        return cast(T, self._resource)

    @property
    def released(self) -> bool:
        return self._released

    def release(self) -> None:
        """
        End this lease exactly once and drop the handle's reference.

        Repeated calls do not invoke the release callback again.
        """

        if self._released:
            return

        self._released = True

        try:
            self._release_callback()
        finally:
            self._resource = None

    def __enter__(self) -> T:
        return self.resource

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        self.release()
        return False