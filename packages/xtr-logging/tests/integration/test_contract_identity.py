from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast

import pytest
import xtr_logging_contracts
import xtr_service_contracts

import xtr_logging

if TYPE_CHECKING:
    from types import ModuleType


def _exported(contract: ModuleType) -> tuple[str, ...]:
    # A module's __all__ is Any to a type checker; give it a type once here
    # rather than at every use below.
    names = cast("list[str]", contract.__all__)
    return tuple(name for name in names if name != "__version__")


# Driven off each contract's own surface, so a symbol added to either is covered
# here without anyone remembering to add it.
CONTRACT_SYMBOLS: Final = tuple(
    (contract, name)
    for contract in (xtr_logging_contracts, xtr_service_contracts)
    for name in _exported(contract)
)
SYMBOL_IDS: Final = [f"{contract.__name__}.{name}" for contract, name in CONTRACT_SYMBOLS]
CONTRACT_NAMES: Final = tuple(name for _, name in CONTRACT_SYMBOLS)


@pytest.mark.parametrize(("contract", "name"), CONTRACT_SYMBOLS, ids=SYMBOL_IDS)
def test_a_contract_symbol_is_re_exported_rather_than_redefined(
    contract: ModuleType, name: str
) -> None:
    # Given a symbol one of the contract packages owns
    # When this package exposes one by the same name
    # Then it is the very same object — a copy would break `isinstance` against
    # the runtime-checkable protocols and container registration by type
    assert getattr(xtr_logging, name) is getattr(contract, name)


@pytest.mark.parametrize("name", CONTRACT_NAMES)
def test_a_contract_symbol_stays_part_of_this_package_s_surface(name: str) -> None:
    assert name in xtr_logging.__all__


def test_this_library_s_errors_derive_from_the_contract_error() -> None:
    assert issubclass(xtr_logging.UnknownChannelError, xtr_logging_contracts.LoggingError)
