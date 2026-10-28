from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.transport import Dsn, DsnOption


@dataclass(frozen=True)
class _Case:
    raw: str
    scheme: str = "scheme"
    host: str = "localhost"
    user: str | None = None
    password: str | None = None
    port: int | None = None
    options: dict[str, DsnOption] = field(default_factory=dict[str, DsnOption])


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(_Case("smtp://example.com", scheme="smtp", host="example.com"), id="simple"),
        pytest.param(_Case("scheme://@localhost"), id="at-sign"),
        pytest.param(_Case("scheme://:@localhost"), id="colon-at"),
        pytest.param(_Case("scheme://user1:@localhost", user="user1"), id="user-no-password"),
        pytest.param(_Case("scheme://:pass@localhost", password="pass"), id="password-no-user"),
        pytest.param(
            _Case(
                "smtp://user1:pass2@example.com:99",
                scheme="smtp",
                host="example.com",
                user="user1",
                password="pass2",
                port=99,
            ),
            id="port",
        ),
        pytest.param(
            _Case(
                "smtp://u%24er:pa%24s@gmail",
                scheme="smtp",
                host="gmail",
                user="u$er",
                password="pa$s",
            ),
            id="credentials-decoded",
        ),
        pytest.param(
            _Case(
                "api://u%24er:pa%24s@mailgun?region=eu",
                scheme="api",
                host="mailgun",
                user="u$er",
                password="pa$s",
                options={"region": "eu"},
            ),
            id="option",
        ),
        pytest.param(
            _Case("Mailgun+API://Default", scheme="Mailgun+API", host="Default"), id="case-kept"
        ),
        pytest.param(
            _Case(
                "scheme://localhost?a[]=1&a[]=2&b[k]=v&b[j]=w",
                options={"a": ("1", "2"), "b": {"k": "v", "j": "w"}},
            ),
            id="list-and-mapping-options",
        ),
        pytest.param(_Case("smtp://[::1]:25", scheme="smtp", host="[::1]", port=25), id="ipv6"),
    ],
)
def test_it_reads_every_part_of_the_dsn(case: _Case) -> None:
    dsn = Dsn.from_string(case.raw)

    assert dsn.scheme == case.scheme
    assert dsn.host == case.host
    assert dsn.user == case.user
    assert dsn.password == case.password
    assert dsn.get_port() == case.port
    for key, value in case.options.items():
        assert dsn.get_option(key) == value


def test_it_is_built_from_its_parts() -> None:
    dsn = Dsn("smtp", "example.com", "user1", "pass2", 99, {"region": "eu"})

    assert (dsn.scheme, dsn.host, dsn.user, dsn.password) == (
        "smtp",
        "example.com",
        "user1",
        "pass2",
    )
    assert dsn.get_port() == 99
    assert dsn.get_option("region") == "eu"


def test_it_falls_back_to_the_default_port() -> None:
    assert Dsn("smtp", "example.com").get_port(25) == 25
    assert Dsn("smtp", "example.com", port=465).get_port(25) == 465


def test_it_reads_an_option_or_its_default() -> None:
    dsn = Dsn("smtp", "example.com", options={"with_value": "some value", "nullable": None})

    assert dsn.get_option("with_value") == "some value"
    assert dsn.get_option("nullable", "default") == "default"
    assert dsn.get_option("not_existent_property", "default") == "default"
    assert dsn.get_option("not_existent_property") is None


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("some://", "The mailer DSN is invalid."),
        ("some://host:port", "The mailer DSN is invalid."),
        ("//sendmail", "The mailer DSN must contain a scheme."),
        ("file:///some/path", 'The mailer DSN must contain a host (use "default" by default).'),
    ],
)
def test_it_refuses_a_dsn_it_cannot_read(raw: str, message: str) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = Dsn.from_string(raw)

    assert str(caught.value) == message


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
    assert Dsn.from_string(raw).get_boolean_option(option, default) is expected


@pytest.mark.parametrize(
    ("query", "shown"),
    [
        ("enabled=ture", "ture"),
        ("enabled=enabled", "enabled"),
        ("enabled=2", "2"),
        ("enabled[]=1", "list"),
        ("enabled[on]=1", "mapping"),
    ],
)
def test_it_refuses_a_boolean_option_that_is_not_a_boolean(query: str, shown: str) -> None:
    dsn = Dsn.from_string(f"scheme://localhost?{query}")

    with pytest.raises(InvalidArgumentError) as caught:
        _ = dsn.get_boolean_option("enabled")

    assert str(caught.value) == f'Value "{shown}" of the "enabled" DSN option is not a boolean.'


def test_it_never_shows_the_credentials() -> None:
    dsn = Dsn.from_string("smtp://s3cr3t-user:s3cr3t-pass@example.com:465?verify_peer=0")

    for shown in (repr(dsn), str(dsn)):
        assert "s3cr3t" not in shown
        assert "example.com" in shown
        assert "verify_peer" in shown
