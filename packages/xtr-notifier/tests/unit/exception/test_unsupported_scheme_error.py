from __future__ import annotations

import pytest

from xtr_notifier.exception import LogicError, NotifierError, UnsupportedSchemeError
from xtr_notifier.exception import unsupported_scheme_error as module


def _installed(distribution: str) -> bool:
    return distribution.startswith("xtr-")


def _absent(_distribution: str) -> bool:
    # The workspace installs the provider libraries; these tests are about one that is missing.
    return False


def test_it_is_a_logic_error_of_this_package() -> None:
    assert issubclass(UnsupportedSchemeError, LogicError)
    assert issubclass(UnsupportedSchemeError, NotifierError)


@pytest.mark.parametrize(
    ("scheme", "distribution"),
    [("telegram", "xtr-telegram-notifier"), ("slack", "xtr-slack-notifier")],
)
def test_it_names_the_library_to_install_for_a_known_scheme(
    scheme: str, distribution: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, "_installed", _absent)

    error = UnsupportedSchemeError(scheme)

    assert str(error) == (
        f'Unable to send notification via "{scheme}" as the bridge is not installed. '
        f'Try running "uv add {distribution}".'
    )


def test_it_reads_the_provider_before_a_plus_in_the_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "_installed", _absent)

    error = UnsupportedSchemeError("telegram+api")

    assert 'via "telegram"' in str(error)


def test_it_does_not_suggest_a_library_that_is_already_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "_installed", _installed)

    error = UnsupportedSchemeError("telegram", "chatter", ["null"])

    assert str(error) == (
        'The "telegram" scheme is not supported; '
        'supported schemes for notifier "chatter" are: "null".'
    )


@pytest.mark.parametrize(
    ("expected", "name", "supported"),
    [
        ('The "somethingElse" scheme is not supported.', None, []),
        ('The "somethingElse" scheme is not supported.', "foo", []),
        (
            (
                'The "somethingElse" scheme is not supported; '
                'supported schemes for notifier "one" are: "one", "two".'
            ),
            "one",
            ["one", "two"],
        ),
    ],
)
def test_it_lists_the_supported_schemes_for_an_unknown_scheme(
    expected: str, name: str | None, supported: list[str]
) -> None:
    error = UnsupportedSchemeError("somethingElse", name, supported)

    assert str(error) == expected


def test_it_carries_what_it_was_told() -> None:
    error = UnsupportedSchemeError("other", "chatter", ["null"])

    assert error.scheme == "other"
    assert error.name == "chatter"
    assert error.supported == ("null",)
