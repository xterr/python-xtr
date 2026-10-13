from __future__ import annotations

import pytest

from xtr_http_client_contracts import TransportError, TransportTimeoutError


def test_it_is_a_transport_error() -> None:
    assert issubclass(TransportTimeoutError, TransportError)


def test_it_is_also_the_timeout_every_async_library_raises() -> None:
    assert issubclass(TransportTimeoutError, TimeoutError)


def test_code_already_guarding_against_timeouts_catches_it() -> None:
    with pytest.raises(TimeoutError):
        raise TransportTimeoutError('Idle timeout reached for "https://example.com/".')


def test_it_keeps_the_reason_it_was_given() -> None:
    error = TransportTimeoutError('Idle timeout reached for "https://example.com/".')

    assert error.reason == 'Idle timeout reached for "https://example.com/".'
    assert str(error) == 'Idle timeout reached for "https://example.com/".'
