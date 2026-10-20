from __future__ import annotations

from xtr_notifier.exception import InvalidArgumentError, MultipleExclusiveOptionsUsedError


def test_it_is_an_invalid_argument() -> None:
    assert issubclass(MultipleExclusiveOptionsUsedError, InvalidArgumentError)


def test_its_message_names_the_used_and_the_exclusive_options() -> None:
    error = MultipleExclusiveOptionsUsedError(["foo", "bar"], ["foo", "bar", "baz"])

    assert str(error) == (
        'Multiple exclusive options have been used "foo", "bar". '
        'Only one of "foo", "bar", "baz" can be used.'
    )
    assert error.used_exclusive_options == ("foo", "bar")
    assert error.exclusive_options == ("foo", "bar", "baz")
