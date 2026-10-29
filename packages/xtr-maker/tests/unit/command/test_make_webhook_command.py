"""Unit tests for :class:`xtr_maker.command.make_webhook_command.MakeWebhookCommand`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import ExitCode

from tests.conftest import FIXTURES
from tests.support.captured_style import CapturedStyle
from xtr_maker import FileManager, Generator, TemplateRenderer
from xtr_maker.command.make_webhook_command import MakeWebhookCommand

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

pytestmark = pytest.mark.anyio

_EXPECTED = FIXTURES / "expected" / "webhook"
_PARSER = "src/app/webhook/stripe_request_parser.py"
_CONSUMER = "src/app/remote_event/stripe_webhook_consumer.py"
_CONFIG = "src/app/config/packages/webhook_stripe.py"


async def _run(
    project: Path,
    style: CapturedStyle,
    name: str | None = None,
    *,
    matcher: list[str] | None = None,
) -> int:
    manager = FileManager(project, "app")
    command = MakeWebhookCommand(manager, ["github"])
    return await command(style.io, Generator(manager, TemplateRenderer()), name, matcher=matcher)


def _read(project: Path, path: str) -> str:
    return (project / path).read_text(encoding="utf-8")


def _expected(case: str, name: str) -> str:
    return (_EXPECTED / case / name).read_text(encoding="utf-8")


def _batch() -> CapturedStyle:
    return CapturedStyle(interactive=False)


async def test_one_matcher_is_returned_as_it_is(project: Path) -> None:
    code = await _run(project, _batch(), "stripe", matcher=["Method"])

    assert code == ExitCode.SUCCESS
    assert _read(project, _PARSER) == _expected("one_matcher", "stripe_request_parser.py.txt")


async def test_the_consumer_is_declared_under_the_webhook_type(project: Path) -> None:
    code = await _run(project, _batch(), "stripe", matcher=["Method"])

    assert code == ExitCode.SUCCESS
    assert _read(project, _CONSUMER) == _expected("one_matcher", "stripe_webhook_consumer.py.txt")


async def test_the_route_is_a_transform_adding_the_parser_and_a_secret_placeholder(
    project: Path,
) -> None:
    code = await _run(project, _batch(), "stripe", matcher=["Method"])

    assert code == ExitCode.SUCCESS
    assert _read(project, _CONFIG) == _expected("one_matcher", "webhook_stripe.py.txt")


async def test_several_matchers_are_chained_in_the_order_picked(project: Path) -> None:
    style = CapturedStyle(["acme-pay", "Method", "Header", ""])

    code = await _run(project, style)

    assert code == ExitCode.SUCCESS
    assert _read(project, "src/app/webhook/acme_pay_request_parser.py") == _expected(
        "several_matchers", "acme_pay_request_parser.py.txt"
    )


async def test_picking_no_matcher_writes_an_empty_chain(project: Path) -> None:
    code = await _run(project, CapturedStyle(["stripe", "[done]"]))

    assert code == ExitCode.SUCCESS
    assert _read(project, _PARSER) == _expected("zero_matchers", "stripe_request_parser.py.txt")


async def test_the_matchers_are_asked_for_even_when_the_type_is_given(project: Path) -> None:
    code = await _run(project, CapturedStyle(["Scheme"]), "stripe")

    assert code == ExitCode.SUCCESS
    assert 'return SchemeRequestMatcher("https")' in _read(project, _PARSER)


async def test_a_matcher_already_picked_is_not_offered_again(project: Path) -> None:
    style = CapturedStyle(["Method", "Method", "IsJson"])

    code = await _run(project, style, "stripe")

    assert code == ExitCode.SUCCESS
    source = _read(project, _PARSER)
    assert source.count("MethodRequestMatcher(") == 1
    assert "IsJsonRequestMatcher()" in source


async def test_without_a_terminal_and_no_matcher_the_method_and_json_ones_apply(
    project: Path,
) -> None:
    code = await _run(project, _batch(), "stripe")

    assert code == ExitCode.SUCCESS
    source = _read(project, _PARSER)
    assert 'MethodRequestMatcher("POST"),\n                IsJsonRequestMatcher(),' in source


async def test_matchers_are_picked_by_name_without_case_and_once_each(project: Path) -> None:
    code = await _run(
        project, _batch(), "stripe", matcher=["isjson", "IsJsonRequestMatcher", "port"]
    )

    assert code == ExitCode.SUCCESS
    source = _read(project, _PARSER)
    assert source.count("IsJsonRequestMatcher()") == 1
    assert "PortRequestMatcher(443)" in source


async def test_class_and_module_names_derive_from_the_type(project: Path) -> None:
    code = await _run(project, _batch(), "acme-pay.v2", matcher=["Method"])

    assert code == ExitCode.SUCCESS
    assert "class AcmePayV2RequestParser(" in _read(
        project, "src/app/webhook/acme_pay_v2_request_parser.py"
    )
    assert "class AcmePayV2WebhookConsumer:" in _read(
        project, "src/app/remote_event/acme_pay_v2_webhook_consumer.py"
    )
    config = _read(project, "src/app/config/packages/webhook_acme_pay_v2.py")
    assert 'env("ACME_PAY_V2_WEBHOOK_SECRET")' in config
    assert '"acme-pay.v2": route' in config


async def test_the_next_steps_name_the_secret_and_the_routes_file(project: Path) -> None:
    style = _batch()

    _ = await _run(project, style, "stripe")

    assert style.lines[-4:] == [
        "- Add STRIPE_WEBHOOK_SECRET to .env.local: the secret stripe shares with you.",
        (
            f"- Open {_PARSER} and replace the secret check with the one its sender's protocol"
            " asks for."
        ),
        f"- Open {_CONSUMER} and write what an event leads to.",
        (
            "- Make sure config/routes/webhook.py exists, with an @as_routes function including"
            ' resources["webhook"]: the sender posts to /webhook/stripe.'
        ),
    ]


async def test_without_a_terminal_a_missing_type_is_refused(project: Path) -> None:
    style = _batch()

    code = await _run(project, style)

    assert code == ExitCode.INVALID
    assert "make:webhook <name>" in style.output
    assert not (project / "src/app/webhook").exists()


@pytest.mark.parametrize("name", ["1stripe", "stripe hooks", "stri/pe", ""])
async def test_a_type_that_is_no_url_segment_is_refused(project: Path, name: str) -> None:
    style = _batch()

    code = await _run(project, style, name)

    assert code == ExitCode.INVALID
    assert "cannot name a webhook type" in style.output
    assert not (project / "src/app/webhook").exists()


async def test_a_type_naming_no_class_is_refused(project: Path) -> None:
    style = _batch()

    code = await _run(project, style, "-")

    assert code == ExitCode.INVALID
    assert not (project / "src/app/webhook").exists()


async def test_a_type_already_routed_is_refused(project: Path) -> None:
    style = _batch()

    code = await _run(project, style, "github")

    assert code == ExitCode.INVALID
    assert "The webhook type 'github' is already routed." in style.output
    assert not (project / "src/app/webhook").exists()


async def test_an_unknown_matcher_is_refused_naming_the_offered_ones(project: Path) -> None:
    style = _batch()

    code = await _run(project, style, "stripe", matcher=["Method", "Body"])

    assert code == ExitCode.INVALID
    assert "There is no request matcher 'Body'; the ones offered are Attributes, Callable," in (
        style.output
    )
    assert not (project / "src/app/webhook").exists()


async def test_an_invalid_answer_is_asked_again(project: Path) -> None:
    style = CapturedStyle(["github", "stripe", ""])

    code = await _run(project, style)

    assert code == ExitCode.SUCCESS
    assert "already routed" in style.output
    assert (project / _PARSER).is_file()


@pytest.mark.parametrize("answers", [("github", "1x", "a b"), ()])
async def test_the_type_is_asked_three_times_at_most(project: Path, answers: Sequence[str]) -> None:
    code = await _run(project, CapturedStyle(answers))

    assert code == ExitCode.INVALID
    assert not (project / "src/app/webhook").exists()


async def test_an_existing_route_module_is_refused_and_nothing_is_written(project: Path) -> None:
    (project / "src/app/config/packages").mkdir(parents=True)
    _ = (project / _CONFIG).write_text('"""Mine."""\n', encoding="utf-8")
    style = _batch()

    code = await _run(project, style, "stripe")

    assert code == ExitCode.FAILURE
    assert "src/app/config/packages/webhook_stripe.py already exists" in style.output
    assert _read(project, _CONFIG) == '"""Mine."""\n'
    assert not (project / _PARSER).exists()
    assert not (project / _CONSUMER).exists()


async def test_an_existing_parser_is_refused_and_nothing_is_written(project: Path) -> None:
    (project / "src/app/webhook").mkdir()
    _ = (project / _PARSER).write_text('"""Mine."""\n', encoding="utf-8")
    style = _batch()

    code = await _run(project, style, "stripe")

    assert code == ExitCode.FAILURE
    assert "stripe_request_parser.py already exists" in style.output
    assert not (project / _CONSUMER).exists()
    assert not (project / _CONFIG).exists()
