"""The marker that says a badge's own user loader must be left alone."""

from __future__ import annotations

from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_http.authenticator.fallback_user_loader import FallbackUserLoader


def _load(identifier: str) -> InMemoryUser:
    """Hand back a user carrying the identifier."""
    return InMemoryUser(identifier)


def test_a_wrapped_loader_answers_as_the_loader_it_wraps() -> None:
    loader = FallbackUserLoader(_load)
    user = loader("alice")

    assert isinstance(user, InMemoryUser)
    assert user.get_user_identifier() == "alice"


def test_a_wrapped_nothing_answers_no_user() -> None:
    loader = FallbackUserLoader(None)

    assert loader("alice") is None


def test_the_marker_is_its_own_answer_not_the_loaders() -> None:
    inner = FallbackUserLoader(_load)
    wrapped = FallbackUserLoader(inner)
    user = wrapped("alice")

    assert isinstance(user, InMemoryUser)
    assert user.get_user_identifier() == "alice"
    assert isinstance(wrapped, FallbackUserLoader)
