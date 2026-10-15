from __future__ import annotations

from xtr_http_client_contracts import exception as contract_exception

from xtr_http_client import exception


def test_the_errors_of_the_contract_are_reachable_from_here_too() -> None:
    for name in contract_exception.__all__:
        assert getattr(exception, name) is getattr(contract_exception, name)


def test_this_package_adds_only_the_logic_error_of_its_own() -> None:
    assert set(exception.__all__) - set(contract_exception.__all__) == {"LogicError"}


def test_the_logic_error_is_an_error_of_the_contract() -> None:
    assert issubclass(exception.LogicError, contract_exception.HttpClientError)
