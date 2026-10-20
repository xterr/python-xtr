from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from xtr_notifier.exception import InvalidArgumentError, MissingRequiredOptionError
from xtr_notifier.transport import Dsn


@dataclass(frozen=True)
class _Case:
    raw: str
    scheme: str = "scheme"
    host: str = "localhost"
    user: str | None = None
    password: str | None = None
    port: int | None = None
    options: dict[str, str] = field(default_factory=dict[str, str])
    path: str | None = None


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(_Case("scheme://localhost"), id="simple"),
        pytest.param(_Case("scheme://@localhost"), id="at-sign"),
        pytest.param(_Case("scheme://:@localhost"), id="colon-at"),
        pytest.param(_Case("scheme://user1:@localhost", user="user1"), id="user-no-password"),
        pytest.param(_Case("scheme://:pass@localhost", password="pass"), id="password-no-user"),
        pytest.param(
            _Case("scheme://u$er:pa$s@localhost", user="u$er", password="pa$s"), id="credentials"
        ),
        pytest.param(
            _Case("scheme://u$er:pa$s@localhost:8000", port=8000, user="u$er", password="pa$s"),
            id="port",
        ),
        pytest.param(
            _Case(
                "scheme://u$er:pa$s@localhost:8000/channel",
                port=8000,
                path="/channel",
                user="u$er",
                password="pa$s",
            ),
            id="path",
        ),
        pytest.param(
            _Case(
                "scheme://u$er:pa$s@localhost:8000/channel?from=FROM",
                port=8000,
                path="/channel",
                options={"from": "FROM"},
                user="u$er",
                password="pa$s",
            ),
            id="option",
        ),
        pytest.param(
            _Case(
                "scheme://u$er:pa$s@localhost:8000/channel?from=FROM&to=TO",
                port=8000,
                path="/channel",
                options={"from": "FROM", "to": "TO"},
                user="u$er",
                password="pa$s",
            ),
            id="options",
        ),
        pytest.param(
            _Case(
                "scheme://u$er:pa$s@localhost:8000/channel?to=TO&from=FROM",
                port=8000,
                path="/channel",
                options={"to": "TO", "from": "FROM"},
                user="u$er",
                password="pa$s",
            ),
            id="options-keep-their-order",
        ),
        pytest.param(
            _Case(
                "Slack+API://Tok%2Fen@Default", scheme="Slack+API", host="Default", user="Tok/en"
            ),
            id="case-kept-and-credentials-decoded",
        ),
    ],
)
def test_it_reads_every_part_of_the_dsn(case: _Case) -> None:
    dsn = Dsn(case.raw)

    assert dsn.original_dsn == case.raw
    assert dsn.scheme == case.scheme
    assert dsn.host == case.host
    assert dsn.user == case.user
    assert dsn.password == case.password
    assert dsn.port == case.port
    assert dsn.path == case.path
    assert list(dsn.options.items()) == list(case.options.items())


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("some://", "The notifier DSN is invalid."),
        ("some://host:port", "The notifier DSN is invalid."),
        ("//slack", "The notifier DSN must contain a scheme."),
        ("file:///some/path", 'The notifier DSN must contain a host (use "default" by default).'),
    ],
)
def test_it_refuses_a_dsn_it_cannot_read(raw: str, message: str) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = Dsn(raw)

    assert str(caught.value) == message


@pytest.mark.parametrize(
    ("expected", "raw", "option", "default"),
    [
        ("foo", "scheme://localhost?with_value=foo", "with_value", None),
        ("", "scheme://localhost?empty=", "empty", None),
        ("0", "scheme://localhost?zero=0", "zero", None),
        (
            "default-value",
            "scheme://localhost?option=value",
            "non_existent_property",
            "default-value",
        ),
        (None, "scheme://localhost?option=value", "non_existent_property", None),
    ],
)
def test_it_reads_an_option_or_its_default(
    expected: str | None, raw: str, option: str, default: str | None
) -> None:
    assert Dsn(raw).get_option(option, default) == expected


@pytest.mark.parametrize(
    ("expected", "query", "option"),
    [("value", "with_value=value", "with_value"), ("0", "timeout=0", "timeout")],
)
def test_it_reads_a_required_option(expected: str, query: str, option: str) -> None:
    assert Dsn(f"scheme://localhost?{query}").get_required_option(option) == expected


@pytest.mark.parametrize(
    ("message", "query", "option"),
    [
        ('The option "foo_bar" is required but missing.', "with_value=value", "foo_bar"),
        (
            'The option "with_empty_string" is required but missing.',
            "with_empty_string=",
            "with_empty_string",
        ),
        ('The option "blank" is required but missing.', "blank=%20%20", "blank"),
    ],
)
def test_it_refuses_a_required_option_missing_or_blank(
    message: str, query: str, option: str
) -> None:
    dsn = Dsn(f"scheme://localhost?{query}")

    with pytest.raises(MissingRequiredOptionError) as caught:
        _ = dsn.get_required_option(option)

    assert str(caught.value) == message
    assert caught.value.option == option


@pytest.mark.parametrize(
    ("expected", "raw", "option", "default"),
    [
        (True, "scheme://localhost?enabled=1", "enabled", False),
        (True, "scheme://localhost?enabled=true", "enabled", False),
        (True, "scheme://localhost?enabled=on", "enabled", False),
        (True, "scheme://localhost?enabled=yes", "enabled", False),
        (True, "scheme://localhost?enabled=TRUE", "enabled", False),
        (False, "scheme://localhost?enabled=0", "enabled", False),
        (False, "scheme://localhost?enabled=false", "enabled", False),
        (False, "scheme://localhost?enabled=off", "enabled", False),
        (False, "scheme://localhost?enabled=no", "enabled", False),
        (False, "scheme://localhost", "not_existant", False),
        (True, "scheme://localhost", "not_existant", True),
        (False, "scheme://localhost?enabled=", "enabled", True),
    ],
)
def test_it_reads_a_boolean_option(expected: bool, raw: str, option: str, default: bool) -> None:
    assert Dsn(raw).get_boolean_option(option, default) is expected


@pytest.mark.parametrize("value", ["ture", "enabled", "2"])
def test_it_refuses_a_boolean_option_that_is_not_a_boolean(value: str) -> None:
    dsn = Dsn(f"scheme://localhost?enabled={value}")

    with pytest.raises(InvalidArgumentError) as caught:
        _ = dsn.get_boolean_option("enabled")

    assert str(caught.value) == f'Value "{value}" of the "enabled" DSN option is not a boolean.'


def test_its_representation_never_shows_the_credentials() -> None:
    shown = repr(Dsn("scheme://s3cr3t-user:s3cr3t-pass@localhost:8000/path?channel=ops"))

    assert "s3cr3t" not in shown
    assert "localhost" in shown
    assert "channel" in shown
