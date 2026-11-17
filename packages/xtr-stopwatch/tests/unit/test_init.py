from __future__ import annotations

import xtr_stopwatch


def test_everything_public_is_importable_from_the_package() -> None:
    for name in xtr_stopwatch.__all__:
        assert hasattr(xtr_stopwatch, name)


def test_every_error_derives_from_the_base() -> None:
    for error in (
        xtr_stopwatch.EventNotStartedError,
        xtr_stopwatch.NoStartedSectionError,
        xtr_stopwatch.UnknownEventError,
        xtr_stopwatch.UnknownSectionError,
    ):
        assert issubclass(error, xtr_stopwatch.StopwatchError)
