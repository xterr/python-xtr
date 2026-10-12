"""Which class a registered client is, when an application brings its own."""

from __future__ import annotations

from typing import cast

import pytest

from xtr_security_oauth2_server.bundle.client_config import ClientConfig
from xtr_security_oauth2_server.exception import InvalidConfigurationError
from xtr_security_oauth2_server.model.abstract_client import AbstractClient
from xtr_security_oauth2_server.model.client import Client


def test_a_client_class_without_the_registration_is_refused() -> None:
    # Written by hand in an application that may never be type-checked, so the
    # guard has to be a real one.
    not_a_client = cast("type[AbstractClient]", str)

    with pytest.raises(InvalidConfigurationError, match=r"client\.classname"):
        _ = ClientConfig(classname=not_a_client)


def test_the_shipped_client_is_the_default_class() -> None:
    assert ClientConfig().classname is Client
