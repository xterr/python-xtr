from __future__ import annotations

import pytest

from tests.support.secret_header_request_parser import SecretHeaderRequestParser
from xtr_webhook.controller._built_parsers import BuiltParsers
from xtr_webhook.exception import LogicError


@pytest.mark.anyio
async def test_it_hands_back_the_parser_registered_under_a_type() -> None:
    parser = SecretHeaderRequestParser()

    assert await BuiltParsers({"acme": parser}).get("acme") is parser


@pytest.mark.anyio
async def test_it_refuses_a_type_nothing_was_registered_under() -> None:
    with pytest.raises(LogicError) as caught:
        _ = await BuiltParsers({}).get("acme")

    assert str(caught.value) == 'Unable to find a parser for the webhook type "acme".'


def test_it_knows_which_types_it_has_without_building_anything() -> None:
    built = BuiltParsers({"acme": SecretHeaderRequestParser()})

    assert built.has("acme")
    assert not built.has("other")
    assert dict(built.provided_services()) == {"acme": SecretHeaderRequestParser}


def test_the_mapping_it_was_given_is_copied() -> None:
    parsers = {"acme": SecretHeaderRequestParser()}
    built = BuiltParsers(parsers)
    parsers.clear()

    assert built.has("acme")
