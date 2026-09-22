from app.resources.model_handle import ModelHandle


def test_context_manager_release() -> None:
    release_count = 0
    resource = object()

    def release_callback() -> None:
        nonlocal release_count
        release_count += 1

    handle = ModelHandle(
        resource=resource,
        release_callback=release_callback,
    )

    assert handle.released is False

    with handle as acquired:
        assert acquired is resource
        assert handle.released is False

    assert handle.released is True
    assert release_count == 1

    print("CONTEXT MANAGER RELEASE: PASS")


def test_double_release() -> None:
    release_count = 0

    def release_callback() -> None:
        nonlocal release_count
        release_count += 1

    handle = ModelHandle(
        resource=object(),
        release_callback=release_callback,
    )

    handle.release()
    handle.release()

    assert handle.released is True
    assert release_count == 1

    print("DOUBLE RELEASE SAFETY: PASS")


def test_exception_release() -> None:
    release_count = 0

    def release_callback() -> None:
        nonlocal release_count
        release_count += 1

    handle = ModelHandle(
        resource=object(),
        release_callback=release_callback,
    )

    exception_propagated = False

    try:
        with handle:
            raise ValueError(
                "intentional test exception"
            )
    except ValueError as exc:
        assert str(exc) == (
            "intentional test exception"
        )
        exception_propagated = True

    assert exception_propagated is True
    assert handle.released is True
    assert release_count == 1

    print("EXCEPTION RELEASE: PASS")


def test_access_after_release() -> None:
    handle = ModelHandle(
        resource=object(),
        release_callback=lambda: None,
    )

    handle.release()

    try:
        _ = handle.resource
    except RuntimeError as exc:
        assert str(exc) == (
            "ModelHandle has already been released."
        )
    else:
        raise AssertionError(
            "Resource access after release "
            "must raise RuntimeError."
        )

    print("ACCESS AFTER RELEASE: PASS")


def main() -> None:
    test_context_manager_release()
    test_double_release()
    test_exception_release()
    test_access_after_release()

    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()