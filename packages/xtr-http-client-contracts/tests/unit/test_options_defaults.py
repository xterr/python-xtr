from __future__ import annotations

from xtr_http_client_contracts import OPTIONS_DEFAULTS, RequestOptions


def test_every_option_the_contract_names_has_a_default() -> None:
    assert set(OPTIONS_DEFAULTS) == set(RequestOptions.__annotations__)


def test_the_default_of_every_option() -> None:
    assert dict(OPTIONS_DEFAULTS) == {
        "auth_basic": None,
        "auth_bearer": None,
        "query": {},
        "headers": {},
        "body": b"",
        "json": None,
        "user_data": None,
        "max_redirects": 20,
        "http_version": None,
        "base_uri": None,
        "timeout": None,
        "max_duration": 0.0,
        "max_connect_duration": 0.0,
        "resolve": {},
        "proxy": None,
        "no_proxy": None,
        "verify_peer": True,
        "verify_host": True,
        "cafile": None,
        "capath": None,
        "local_cert": None,
        "local_pk": None,
        "passphrase": None,
        "max_retries": 3,
        "extra": {"use_persistent_connections": False},
    }
