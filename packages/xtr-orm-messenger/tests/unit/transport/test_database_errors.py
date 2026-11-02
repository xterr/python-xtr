from __future__ import annotations

import pytest
from sqlalchemy.exc import DBAPIError

from tests.support.database_errors import SqlStateError
from xtr_orm_messenger.transport._database_errors import is_missing_table, is_retryable


def _raised(original: Exception) -> DBAPIError:
    return DBAPIError("SELECT", None, original)


@pytest.mark.parametrize(
    "original",
    [
        SqlStateError("40P01"),
        SqlStateError("40001"),
        SqlStateError("55P03"),
        Exception(1213, "Deadlock found when trying to get lock"),
        Exception(1205, "Lock wait timeout exceeded"),
        Exception("database is locked"),
    ],
    ids=[
        "deadlock",
        "serialization",
        "lock-not-available",
        "mysql-deadlock",
        "mysql-wait",
        "sqlite",
    ],
)
def test_a_conflict_with_another_transaction_is_worth_trying_again(original: Exception) -> None:
    assert is_retryable(_raised(original))


@pytest.mark.parametrize(
    "original",
    [SqlStateError("23505"), Exception(1062, "Duplicate entry"), Exception("disk I/O error")],
    ids=["unique", "mysql-duplicate", "sqlite-io"],
)
def test_anything_else_is_not(original: Exception) -> None:
    assert not is_retryable(_raised(original))


def test_a_flag_first_among_the_arguments_is_no_error_number() -> None:
    assert not is_retryable(_raised(Exception(True, "nothing")))


def test_an_error_with_no_arguments_has_no_error_number() -> None:
    assert not is_retryable(_raised(Exception()))


@pytest.mark.parametrize(
    "original",
    [
        SqlStateError("42P01"),
        Exception(1146, "Table 'app.messenger_messages' doesn't exist"),
        Exception("no such table: messenger_messages"),
    ],
    ids=["postgresql", "mysql", "sqlite"],
)
def test_a_missing_table_is_told_apart(original: Exception) -> None:
    assert is_missing_table(_raised(original))


def test_another_error_is_no_missing_table() -> None:
    assert not is_missing_table(_raised(SqlStateError("40P01")))
