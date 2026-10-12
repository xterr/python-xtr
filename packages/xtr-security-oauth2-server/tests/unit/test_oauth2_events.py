"""Every announcement is named once, under this package's own prefix."""

from __future__ import annotations

from xtr_security_oauth2_server.oauth2_events import OAuth2Events

_NAMES = (
    OAuth2Events.USER_RESOLVE,
    OAuth2Events.SCOPE_RESOLVE,
    OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE,
    OAuth2Events.TOKEN_REQUEST_RESOLVE,
    OAuth2Events.PRE_SAVE_CLIENT,
    OAuth2Events.ACCESS_TOKEN_EXTRA_CLAIMS_RESOLVE,
)


def test_every_name_is_under_this_server_prefix() -> None:
    assert all(name.startswith("oauth2_server.") for name in _NAMES)


def test_no_two_announcements_share_a_name() -> None:
    assert len(set(_NAMES)) == len(_NAMES)


def test_the_names_are_the_ones_a_listener_registers_under() -> None:
    assert OAuth2Events.USER_RESOLVE == "oauth2_server.user_resolve"
    assert OAuth2Events.SCOPE_RESOLVE == "oauth2_server.scope_resolve"
    assert OAuth2Events.PRE_SAVE_CLIENT == "oauth2_server.pre_save_client"
