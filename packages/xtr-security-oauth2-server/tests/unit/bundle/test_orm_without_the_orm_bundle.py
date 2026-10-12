"""A database persistence with nothing to read the database through.

The deployment is told what it is missing, by name. That only happens if the
bundle's own check runs before the pass that would load the tables into a
connection nobody opened: the pass is registered to run after it for exactly
this reason, and this is what holds it there.
"""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel

from xtr_security_oauth2_server.bundle import OAuth2ServerBundle
from xtr_security_oauth2_server.exception import InvalidConfigurationError

_APP = "tests.fixtures.oauth2_orm_no_bundle_app"


def _kernel() -> Kernel:
    """Return a kernel of the stored deployment, listing no ORM bundle."""
    return Kernel(_APP, env="test", bundles={OAuth2ServerBundle: {"all": True}})


def test_it_is_refused_with_the_bundle_that_is_missing_named() -> None:
    with pytest.raises(InvalidConfigurationError) as refused:
        _ = _kernel().build()

    message = str(refused.value)
    assert "orm bundle is not active" in message
    assert "OrmBundle" in message


def test_the_refusal_is_this_package_s_own_and_not_an_internal_failure() -> None:
    # The mappings pass runs after this bundle's ``process``, so what a
    # deployment sees is the sentence above rather than a connection the pass
    # could not resolve.
    with pytest.raises(InvalidConfigurationError) as refused:
        _ = _kernel().build()

    assert refused.value.__cause__ is None
