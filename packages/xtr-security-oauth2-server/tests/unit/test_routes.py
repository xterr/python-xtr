"""The router declares every endpoint, whether or not a deployment serves it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.routing import APIRoute

from xtr_security_oauth2_server._endpoint_paths import (
    AUTHORIZE_PATH,
    DEVICE_CODE_PATH,
    INTROSPECT_PATH,
    JWKS_PATH,
    METADATA_PATH,
    REVOKE_PATH,
    ROUTE_NAMES,
    TOKEN_PATH,
)
from xtr_security_oauth2_server.routes import routes

if TYPE_CHECKING:
    from collections.abc import Mapping


def _declared() -> Mapping[str, APIRoute]:
    """Return every route the router carries, by path."""
    return {route.path: route for route in routes().routes if isinstance(route, APIRoute)}


def test_every_endpoint_is_declared() -> None:
    assert set(_declared()) == {
        AUTHORIZE_PATH,
        TOKEN_PATH,
        DEVICE_CODE_PATH,
        REVOKE_PATH,
        INTROSPECT_PATH,
        METADATA_PATH,
        JWKS_PATH,
    }


def test_an_endpoint_a_deployment_turns_off_is_still_declared() -> None:
    # The router is built when the module is imported, before any
    # configuration is read, so it cannot leave a path out; a controller
    # answers 404 instead.
    declared = _declared()

    assert INTROSPECT_PATH in declared
    assert DEVICE_CODE_PATH in declared


def test_each_route_carries_the_name_an_application_builds_a_url_by() -> None:
    for path, route in _declared().items():
        assert route.name == ROUTE_NAMES[path]


def test_the_authorization_endpoint_also_answers_the_consent_form_posting_back() -> None:
    # Consent is stateless: the form posts the original query back here, and
    # that second pass is the one a listener approves.
    assert _declared()[AUTHORIZE_PATH].methods == {"GET", "POST"}


def test_the_endpoints_a_client_calls_are_post_only() -> None:
    declared = _declared()

    for path in (TOKEN_PATH, DEVICE_CODE_PATH, REVOKE_PATH, INTROSPECT_PATH):
        assert declared[path].methods == {"POST"}


def test_the_endpoints_something_reads_are_get_only() -> None:
    declared = _declared()

    for path in (METADATA_PATH, JWKS_PATH):
        assert declared[path].methods == {"GET"}


def test_the_description_lives_where_the_standard_fixes_it() -> None:
    # RFC 8414 fixes this path relative to the issuer, which is why the issuer
    # must be an origin carrying no path of its own.
    assert METADATA_PATH == "/.well-known/oauth-authorization-server"


def test_a_second_router_is_a_separate_object() -> None:
    # An application including the routes twice — two mounts, a test building
    # one per case — must not share route objects.
    assert routes() is not routes()
