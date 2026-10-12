"""The validator interface is runtime-checkable against a conforming validator."""

from __future__ import annotations

from xtr_security_oauth2_server_core.redirect_uri_validators import (
    RedirectUriValidatorInterface,
)
from xtr_security_oauth2_server_core.redirect_uri_validators.redirect_uri_validator import (
    RedirectUriValidator,
)


def test_the_bundled_validator_satisfies_the_interface() -> None:
    assert isinstance(RedirectUriValidator([]), RedirectUriValidatorInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), RedirectUriValidatorInterface)
