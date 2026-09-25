from __future__ import annotations

from typing import Final

import pytest
import xtr_logging_contracts

import xtr_logging

# Driven off the contract's own surface, so a symbol added there is covered here
# without anyone remembering to add it.
CONTRACT_SYMBOLS: Final = tuple(
    name for name in xtr_logging_contracts.__all__ if name != "__version__"
)


@pytest.mark.parametrize("name", CONTRACT_SYMBOLS)
def test_a_contract_symbol_is_re_exported_rather_than_redefined(name: str) -> None:
    # Given a symbol the contract package owns
    # When this package exposes one by the same name
    # Then it is the very same object — a copy would break `isinstance` against
    # the runtime-checkable protocols and container registration by type
    assert getattr(xtr_logging, name) is getattr(xtr_logging_contracts, name)


@pytest.mark.parametrize("name", CONTRACT_SYMBOLS)
def test_a_contract_symbol_stays_part_of_this_package_s_surface(name: str) -> None:
    assert name in xtr_logging.__all__


def test_this_library_s_errors_derive_from_the_contract_error() -> None:
    assert issubclass(xtr_logging.UnknownChannelError, xtr_logging_contracts.LoggingError)


def test_the_contract_declares_no_symbol_this_package_drops() -> None:
    assert not set(CONTRACT_SYMBOLS) - set(xtr_logging.__all__)
