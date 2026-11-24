"""Unit tests for :class:`xtr_orm_fixtures.TableDefinitions`."""

from __future__ import annotations

import pytest
from sqlalchemy import MetaData

from xtr_orm_fixtures import TableDefinitions
from xtr_orm_fixtures.exception import InvalidArgumentError


def test_definitions_are_found_by_connection() -> None:
    main, audit = MetaData(), MetaData()

    definitions = TableDefinitions({"default": main, "audit": [audit]})

    assert definitions.for_connection("default") is main
    assert definitions.for_connection("audit") == [audit]


def test_table_definitions_refuse_an_unknown_connection() -> None:
    definitions = TableDefinitions({"default": MetaData(), "audit": MetaData()})

    with pytest.raises(InvalidArgumentError) as caught:
        _ = definitions.for_connection("reports")

    assert caught.value.reason == (
        'No connection is named "reports"; the connections are: default, audit'
    )


def test_table_definitions_without_connections_say_so() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = TableDefinitions({}).for_connection("default")

    assert caught.value.reason == 'No connection is named "default"; the connections are: none'


def test_a_connection_without_definitions_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = TableDefinitions({"default": ()}).for_connection("default")

    assert caught.value.reason == 'The "default" connection keeps no table definitions'
