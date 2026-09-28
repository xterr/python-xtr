from __future__ import annotations

from xtr_logging import TestHandler
from xtr_logging.config.services import Services


def test_it_supplies_nothing_by_default() -> None:
    services = Services()

    assert (
        dict(services.handlers),
        dict(services.formatters),
        dict(services.processors),
        dict(services.activation_strategies),
    ) == ({}, {}, {}, {})


def test_it_hands_back_what_it_was_given_by_id() -> None:
    handler = TestHandler()

    assert Services(handlers={"main": handler}).handlers["main"] is handler
