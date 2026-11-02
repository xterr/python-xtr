"""The bundle registers the MIME types table and the HTML-to-text converter."""

from __future__ import annotations

import pytest
from xtr_dependency_injection.testing import assert_zero_config

from tests.support.mime_kernel import mime_kernel
from xtr_mime import (
    DefaultHtmlToTextConverter,
    HtmlToTextConverterInterface,
    MimeTypeGuesserInterface,
    MimeTypes,
    MimeTypesInterface,
)
from xtr_mime.bundle import MimeBundle, MimeConfig

pytestmark = pytest.mark.anyio


async def test_it_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(MimeBundle)


async def test_booting_builds_no_table() -> None:
    MimeTypes._default = None

    async with await mime_kernel().boot():
        built = MimeTypes._default

    assert built is None


async def test_the_table_is_both_interfaces() -> None:
    async with await mime_kernel().boot() as booted:
        table = await booted.container.get(MimeTypes)
        found = [
            await booted.container.get(MimeTypesInterface),
            await booted.container.get(MimeTypeGuesserInterface),
        ]

    assert all(one is table for one in found)


async def test_the_table_becomes_the_default_one() -> None:
    async with await mime_kernel().boot() as booted:
        table = await booted.container.get(MimeTypesInterface)

    assert MimeTypes.get_default() is table


async def test_the_configured_extra_map_ranks_first() -> None:
    config = MimeConfig(extra_map={"text/x-notes": ["txt"]})

    async with await mime_kernel(config).boot() as booted:
        table = await booted.container.get(MimeTypesInterface)

    assert table.get_mime_types("txt")[0] == "text/x-notes"


async def test_the_converter_is_the_default_one() -> None:
    async with await mime_kernel().boot() as booted:
        converter = await booted.container.get(HtmlToTextConverterInterface)

    assert isinstance(converter, DefaultHtmlToTextConverter)
    assert converter.convert("<p>Hello</p>", "utf-8") == "Hello"
