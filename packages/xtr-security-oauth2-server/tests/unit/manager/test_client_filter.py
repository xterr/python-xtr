"""The criteria a caller narrows a client listing by."""

from __future__ import annotations

from xtr_security_oauth2_server.manager.client_filter import ClientFilter
from xtr_security_oauth2_server.value_object.grant import Grant
from xtr_security_oauth2_server.value_object.redirect_uri import RedirectUri
from xtr_security_oauth2_server.value_object.scope import Scope


def test_a_fresh_filter_narrows_nothing() -> None:
    assert ClientFilter.create().has_filters() is False


def test_it_reports_no_criteria_when_fresh() -> None:
    filtered = ClientFilter.create()

    assert (filtered.get_grants(), filtered.get_redirect_uris(), filtered.get_scopes()) == (
        (),
        (),
        (),
    )


def test_it_keeps_the_grants_it_is_given() -> None:
    filtered = ClientFilter.create().add_grant_criteria(Grant("password"))

    assert filtered.get_grants() == (Grant("password"),)


def test_it_keeps_the_redirect_uris_it_is_given() -> None:
    uri = RedirectUri("https://a.example.com/cb")

    assert ClientFilter.create().add_redirect_uri_criteria(uri).get_redirect_uris() == (uri,)


def test_it_keeps_the_scopes_it_is_given() -> None:
    filtered = ClientFilter.create().add_scope_criteria(Scope("read"))

    assert filtered.get_scopes() == (Scope("read"),)


def test_criteria_added_twice_are_both_kept() -> None:
    filtered = ClientFilter.create()

    _ = filtered.add_grant_criteria(Grant("password"))
    _ = filtered.add_grant_criteria(Grant("implicit"))

    assert filtered.get_grants() == (Grant("password"), Grant("implicit"))


def test_it_narrows_once_a_grant_is_named() -> None:
    assert ClientFilter.create().add_grant_criteria(Grant("password")).has_filters() is True


def test_it_narrows_once_a_redirect_uri_is_named() -> None:
    uri = RedirectUri("https://a.example.com/cb")

    assert ClientFilter.create().add_redirect_uri_criteria(uri).has_filters() is True


def test_it_narrows_once_a_scope_is_named() -> None:
    assert ClientFilter.create().add_scope_criteria(Scope("read")).has_filters() is True


def test_its_criteria_setters_answer_the_filter_so_a_caller_can_chain_them() -> None:
    filtered = ClientFilter.create()

    chained = filtered.add_grant_criteria(Grant("password")).add_scope_criteria(Scope("read"))

    assert chained is filtered
