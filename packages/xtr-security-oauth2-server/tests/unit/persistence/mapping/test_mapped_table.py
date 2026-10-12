"""The table a model was mapped to, which is where its columns are named."""

from __future__ import annotations

import pytest
from sqlalchemy import MetaData
from sqlalchemy.orm.exc import UnmappedClassError

from xtr_security_oauth2_server.model.access_token import AccessToken
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.model.device_code import DeviceCode
from xtr_security_oauth2_server.persistence.mapping.driver import Driver
from xtr_security_oauth2_server.persistence.mapping.mapped_table import mapped_table


def test_it_answers_with_the_table_a_model_was_mapped_to() -> None:
    driver = Driver(Client, True)
    try:
        _ = driver.load_metadata(MetaData())

        assert mapped_table(AccessToken).name == "oauth2_access_token"
        assert "expiry" in mapped_table(AccessToken).c
    finally:
        driver._dispose()


def test_it_answers_with_the_prefixed_table_a_deployment_asked_for() -> None:
    driver = Driver(Client, True, "srv_")
    try:
        _ = driver.load_metadata(MetaData())

        assert mapped_table(AccessToken).name == "srv_access_token"
    finally:
        driver._dispose()


def test_a_model_the_deployment_turned_off_has_no_table() -> None:
    driver = Driver(Client, True, "oauth2_", False)
    try:
        _ = driver.load_metadata(MetaData())

        with pytest.raises(UnmappedClassError):
            _ = mapped_table(DeviceCode)
    finally:
        driver._dispose()
