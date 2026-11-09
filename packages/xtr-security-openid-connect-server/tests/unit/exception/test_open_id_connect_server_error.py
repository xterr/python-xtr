"""The root every error this package raises derives from."""

from __future__ import annotations

import pytest
from xtr_security_oauth2_server_core.exception import OAuth2Error

from xtr_security_openid_connect_server.exception import OpenIdConnectServerError


def test_one_except_for_the_authorization_server_catches_it() -> None:
    with pytest.raises(OAuth2Error, match=r"something the identity layer could not do"):
        raise OpenIdConnectServerError("something the identity layer could not do")
