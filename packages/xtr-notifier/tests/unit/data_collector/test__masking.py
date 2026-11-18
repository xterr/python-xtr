from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from xtr_http_kernel.data_collector import clone_var

from xtr_notifier.data_collector._masking import MASK, is_sensitive, masked
from xtr_notifier.message import MessageOptions


@dataclass(frozen=True, slots=True)
class _Webhook:
    url: str
    token: str


def _attributes(tree: dict[str, object]) -> dict[str, dict[str, object]]:
    return dict(cast("list[tuple[str, dict[str, object]]]", tree["attributes"]))


def test_a_credential_named_option_keeps_its_name_and_loses_its_value() -> None:
    options = MessageOptions("slack", values={"bot_token": "xoxb-1", "mrkdwn": True})

    tree = masked(clone_var(options))

    assert _attributes(tree)["values"]["items"] == [
        [clone_var("bot_token"), clone_var(MASK)],
        [clone_var("mrkdwn"), clone_var(True)],
    ]


def test_a_credential_named_attribute_is_masked() -> None:
    tree = masked(clone_var(_Webhook("https://hooks.example.test", "t-1")))

    attributes = _attributes(tree)
    assert attributes["token"] == clone_var(MASK)
    assert attributes["url"] == clone_var("https://hooks.example.test")


def test_a_credential_header_in_a_mapping_is_masked() -> None:
    tree = masked(clone_var({"Authorization": "Bearer abc", "accept": "text/plain"}))

    assert tree["items"] == [
        [clone_var("Authorization"), clone_var(MASK)],
        [clone_var("accept"), clone_var("text/plain")],
    ]


def test_a_credential_inside_a_sequence_is_masked() -> None:
    tree = masked(clone_var([{"api_key": "k-1"}]))

    [inner] = cast("list[dict[str, object]]", tree["items"])
    assert inner["items"] == [[clone_var("api_key"), clone_var(MASK)]]


def test_a_mapping_with_keys_that_are_not_text_is_left_alone() -> None:
    tree = clone_var({1: "secret value"})

    assert masked(tree) == tree


def test_a_scalar_is_returned_as_it_is() -> None:
    tree = clone_var("plain")

    assert masked(tree) is tree


def test_names_are_told_sensitive_by_header_and_by_field_word() -> None:
    names = ("X-Api-Key", "Proxy-Authorization", "webhook_SECRET", "passwd", "apikey", "channel")

    assert [is_sensitive(name) for name in names] == [True, True, True, True, True, False]
