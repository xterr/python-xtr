from __future__ import annotations

from xtr_http_client_contracts import exception as contract_exception

from xtr_http_client import exception


def test_the_errors_of_the_contract_are_reachable_from_here_too() -> None:
    for name in contract_exception.__all__:
        assert getattr(exception, name) is getattr(contract_exception, name)


def test_the_two_errors_this_package_adds_are_exported() -> None:
    assert set(exception.__all__) == {
        *contract_exception.__all__,
        "InvalidArgumentError",
        "JsonError",
    }
