from __future__ import annotations

import pytest

from xtr_logging.exception.invalid_option_error import InvalidOptionError
from xtr_logging.processor.processor_declaration import ProcessorDeclaration


def test_two_declarations_saying_the_same_are_equal() -> None:
    assert ProcessorDeclaration(channel="app") == ProcessorDeclaration(channel="app")


def test_it_may_not_target_both_a_channel_and_a_handler() -> None:
    with pytest.raises(InvalidOptionError):
        _ = ProcessorDeclaration(channel="app", handler="main")
