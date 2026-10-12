"""The validator matches exactly, and ignores the port of a loopback redirect."""

from __future__ import annotations

from xtr_security_oauth2_server_core.redirect_uri_validators import (
    RedirectUriValidatorInterface,
)
from xtr_security_oauth2_server_core.redirect_uri_validators.redirect_uri_validator import (
    RedirectUriValidator,
)

REGISTERED = "https://client.example.test/callback"


def test_it_declares_the_redirect_uri_validator_contract() -> None:
    assert RedirectUriValidatorInterface in RedirectUriValidator.__mro__


def test_it_accepts_a_uri_registered_verbatim() -> None:
    assert RedirectUriValidator([REGISTERED]).validate_redirect_uri(REGISTERED)


def test_it_accepts_a_single_registered_uri_given_as_a_bare_string() -> None:
    assert RedirectUriValidator(REGISTERED).validate_redirect_uri(REGISTERED)


def test_it_accepts_the_second_of_several_registered_uris() -> None:
    validator = RedirectUriValidator(["https://other.example.test/cb", REGISTERED])

    assert validator.validate_redirect_uri(REGISTERED)


def test_it_refuses_a_uri_that_is_not_registered() -> None:
    assert not RedirectUriValidator([REGISTERED]).validate_redirect_uri(
        "https://attacker.example.test/callback",
    )


def test_it_refuses_a_uri_differing_by_a_trailing_slash() -> None:
    assert not RedirectUriValidator([REGISTERED]).validate_redirect_uri(f"{REGISTERED}/")


def test_it_refuses_a_uri_differing_only_in_the_case_of_its_path() -> None:
    assert not RedirectUriValidator([REGISTERED]).validate_redirect_uri(
        "https://client.example.test/Callback",
    )


def test_it_refuses_a_uri_carrying_an_extra_query_parameter() -> None:
    assert not RedirectUriValidator([REGISTERED]).validate_redirect_uri(
        f"{REGISTERED}?next=https://attacker.example.test",
    )


def test_it_refuses_a_uri_carrying_an_extra_fragment() -> None:
    assert not RedirectUriValidator([REGISTERED]).validate_redirect_uri(f"{REGISTERED}#part")


def test_it_refuses_every_uri_when_none_is_registered() -> None:
    assert not RedirectUriValidator([]).validate_redirect_uri(REGISTERED)


def test_it_accepts_an_ipv4_loopback_on_another_port() -> None:
    # RFC 8252 section 7.3: a native client takes whatever port it is given.
    validator = RedirectUriValidator(["http://127.0.0.1:1234/callback"])

    assert validator.validate_redirect_uri("http://127.0.0.1:49152/callback")


def test_it_accepts_an_ipv6_loopback_on_another_port() -> None:
    validator = RedirectUriValidator(["http://[::1]:1234/callback"])

    assert validator.validate_redirect_uri("http://[::1]:49152/callback")


def test_it_accepts_an_ipv4_loopback_naming_no_port_at_all() -> None:
    validator = RedirectUriValidator(["http://127.0.0.1:1234/callback"])

    assert validator.validate_redirect_uri("http://127.0.0.1/callback")


def test_it_accepts_an_ipv4_loopback_against_a_registration_naming_no_port() -> None:
    validator = RedirectUriValidator(["http://127.0.0.1/callback"])

    assert validator.validate_redirect_uri("http://127.0.0.1:49152/callback")


def test_it_accepts_an_ipv4_loopback_whose_query_matches() -> None:
    validator = RedirectUriValidator(["http://127.0.0.1:1234/callback?app=desk"])

    assert validator.validate_redirect_uri("http://127.0.0.1:49152/callback?app=desk")


def test_it_refuses_an_ipv4_loopback_whose_path_differs() -> None:
    validator = RedirectUriValidator(["http://127.0.0.1:1234/callback"])

    assert not validator.validate_redirect_uri("http://127.0.0.1:1234/other")


def test_it_refuses_an_ipv4_loopback_whose_query_differs() -> None:
    validator = RedirectUriValidator(["http://127.0.0.1:1234/callback?app=desk"])

    assert not validator.validate_redirect_uri("http://127.0.0.1:1234/callback?app=other")


def test_it_refuses_an_ipv6_loopback_against_a_registered_ipv4_loopback() -> None:
    validator = RedirectUriValidator(["http://127.0.0.1:1234/callback"])

    assert not validator.validate_redirect_uri("http://[::1]:1234/callback")


def test_it_refuses_a_loopback_whose_scheme_differs_from_the_registration() -> None:
    # Only `http` loopbacks are port-agnostic, so an `https` candidate falls
    # back to the exact comparison and finds no match.
    validator = RedirectUriValidator(["http://127.0.0.1:1234/callback"])

    assert not validator.validate_redirect_uri("https://127.0.0.1:1234/callback")


def test_it_refuses_an_https_loopback_on_another_port() -> None:
    validator = RedirectUriValidator(["https://127.0.0.1:1234/callback"])

    assert not validator.validate_redirect_uri("https://127.0.0.1:49152/callback")


def test_it_does_not_treat_the_localhost_name_as_a_loopback() -> None:
    # RFC 8252 section 8.3 warns against the name: it resolves through the host
    # file and may not be the loopback at all, so only the literals qualify.
    validator = RedirectUriValidator(["http://localhost:1234/callback"])

    assert not validator.validate_redirect_uri("http://localhost:49152/callback")


def test_it_accepts_the_localhost_name_on_the_registered_port() -> None:
    validator = RedirectUriValidator(["http://localhost:1234/callback"])

    assert validator.validate_redirect_uri("http://localhost:1234/callback")


def test_it_does_not_treat_another_address_of_the_loopback_range_as_a_loopback() -> None:
    validator = RedirectUriValidator(["http://127.0.0.2:1234/callback"])

    assert not validator.validate_redirect_uri("http://127.0.0.2:49152/callback")


def test_it_refuses_a_candidate_whose_port_cannot_be_read() -> None:
    validator = RedirectUriValidator(["http://127.0.0.1:1234/callback"])

    assert not validator.validate_redirect_uri("http://127.0.0.1:not-a-port/callback")


def test_it_refuses_a_candidate_that_cannot_be_read_as_a_uri_at_all() -> None:
    validator = RedirectUriValidator(["http://127.0.0.1:1234/callback"])

    assert not validator.validate_redirect_uri("http://[::1/callback")


def test_it_accepts_an_unreadable_candidate_registered_verbatim() -> None:
    # Nothing is parsed on the exact path, so a registration this library
    # cannot read still matches itself and nothing else.
    unreadable = "http://[::1/callback"

    assert RedirectUriValidator([unreadable]).validate_redirect_uri(unreadable)


def test_it_refuses_a_loopback_against_a_registration_whose_port_cannot_be_read() -> None:
    validator = RedirectUriValidator(["http://127.0.0.1:not-a-port/callback"])

    assert not validator.validate_redirect_uri("http://127.0.0.1:49152/callback")


def test_it_accepts_an_unreadable_loopback_registered_verbatim() -> None:
    # A uri whose port cannot be read is not a uri this library understands,
    # so it gets none of the loopback leniency and only matches itself.
    unreadable = "http://127.0.0.1:not-a-port/callback"

    assert RedirectUriValidator([unreadable]).validate_redirect_uri(unreadable)


def test_it_ignores_only_the_port_of_a_loopback_and_not_its_user_information() -> None:
    validator = RedirectUriValidator(["http://127.0.0.1:1234/callback"])

    assert not validator.validate_redirect_uri("http://someone@127.0.0.1:49152/callback")
