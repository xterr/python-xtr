"""The configuration is buildable bare and refuses an extra map the table cannot read."""

from __future__ import annotations

import pytest

from xtr_mime.bundle import MimeConfig
from xtr_mime.exception import InvalidArgumentError


def test_it_builds_with_no_arguments() -> None:
    assert dict(MimeConfig().extra_map) == {}


def test_it_keeps_an_extra_map() -> None:
    config = MimeConfig(extra_map={"application/mbox": ["mbox"]})

    assert dict(config.extra_map) == {"application/mbox": ["mbox"]}


@pytest.mark.parametrize("mime_type", ["", "mbox", "/mbox", "application/"])
def test_a_type_that_is_not_a_type_slash_subtype_is_refused(mime_type: str) -> None:
    with pytest.raises(InvalidArgumentError, match="type/subtype"):
        _ = MimeConfig(extra_map={mime_type: ["mbox"]})


def test_extensions_given_as_one_string_are_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="a sequence of extensions"):
        _ = MimeConfig(extra_map={"application/mbox": "mbox"})


@pytest.mark.parametrize("extension", ["", ".mbox"])
def test_an_empty_or_dotted_extension_is_refused(extension: str) -> None:
    with pytest.raises(InvalidArgumentError, match="without its leading dot"):
        _ = MimeConfig(extra_map={"application/mbox": [extension]})
