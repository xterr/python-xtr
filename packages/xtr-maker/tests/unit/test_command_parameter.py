"""Unit tests for :class:`xtr_maker.command_parameter.CommandParameter`."""

from __future__ import annotations

import pytest

from xtr_maker.command_parameter import CommandParameter
from xtr_maker.exception import InvalidArgumentError


def test_an_argument_is_a_required_string_by_default() -> None:
    parameter = CommandParameter.parse("recipient", option=False)

    assert parameter == CommandParameter("recipient", "str", description="Recipient.")


def test_an_option_is_a_flag_by_default() -> None:
    parameter = CommandParameter.parse("dry-run", option=True)

    assert parameter == CommandParameter(
        "dry_run", "bool", option=True, required=False, description="Dry run."
    )


def test_a_question_mark_makes_an_argument_optional() -> None:
    parameter = CommandParameter.parse("cc?:list", option=False)

    assert (parameter.name, parameter.value_type, parameter.required) == ("cc", "list[str]", False)
    assert parameter.is_list


@pytest.mark.parametrize("typed", ["str", "int", "float", "list[str]"])
def test_a_named_type_is_kept(typed: str) -> None:
    assert CommandParameter.parse(f"value:{typed}", option=True).value_type == typed


def test_a_dotted_type_names_an_enum_class() -> None:
    parameter = CommandParameter.parse("status:http.HTTPStatus", option=False)

    assert parameter.enum_class == ("http", "HTTPStatus")


def test_a_named_type_is_no_enum_class() -> None:
    assert CommandParameter.parse("limit:int", option=True).enum_class is None


def test_an_option_cannot_be_marked_optional() -> None:
    with pytest.raises(InvalidArgumentError, match="never required"):
        _ = CommandParameter.parse("limit?:int", option=True)


def test_a_declaration_out_of_shape_is_refused() -> None:
    with pytest.raises(
        InvalidArgumentError, match=r"Cannot read 'cc\?list' as name\[\?\]\[:type\]"
    ):
        _ = CommandParameter.parse("cc?list", option=False)


def test_an_option_cannot_be_required() -> None:
    with pytest.raises(InvalidArgumentError, match="cannot be required"):
        _ = CommandParameter("limit", "int", option=True)


def test_an_argument_cannot_be_a_flag() -> None:
    with pytest.raises(InvalidArgumentError, match="a flag is an option, --option force"):
        _ = CommandParameter.parse("force:bool", option=False)


@pytest.mark.parametrize(
    ("typed", "reason"),
    [
        ("Recipient", "use lowercase letters"),
        ("2fa", "use lowercase letters"),
        ("", "use lowercase letters"),
        ("class", "it is a Python keyword"),
        ("id", "it would hide the builtin"),
        ("io", "the command's output goes by that name"),
        ("self", "it names the command itself"),
        ("help", "it would take --help over"),
        ("version", "it would take --version over"),
    ],
)
def test_a_name_the_signature_cannot_hold_is_refused(typed: str, reason: str) -> None:
    with pytest.raises(InvalidArgumentError, match=reason):
        _ = CommandParameter.check_name(typed, option=False)


@pytest.mark.parametrize("typed", ["quiet", "silent", "verbose", "no-interaction", "no_ansi"])
def test_an_option_taking_a_global_flag_over_is_refused(typed: str) -> None:
    with pytest.raises(InvalidArgumentError, match="every command already takes --"):
        _ = CommandParameter.check_name(typed, option=True)


def test_an_argument_may_share_a_global_flag_name() -> None:
    assert CommandParameter.check_name("quiet", option=False) == "quiet"


def test_dashes_become_underscores() -> None:
    assert CommandParameter.check_name(" dry-run ", option=True) == "dry_run"


def test_an_unknown_type_is_refused_naming_the_types() -> None:
    with pytest.raises(InvalidArgumentError, match="There is no type 'enum'; use str, bool"):
        _ = CommandParameter.check_type("enum")


@pytest.mark.parametrize(
    ("typed", "reason"),
    [
        ("missing_module_for_tests.Color", "Cannot import 'missing_module_for_tests'"),
        ("http.Missing", "'http.Missing' is not an Enum class"),
        ("http.HTTPConnection", "is not an Enum class"),
        (".Color", "Name the enum class as module.Class"),
        ("http.", "Name the enum class as module.Class"),
    ],
)
def test_a_dotted_type_must_import_an_enum_class(typed: str, reason: str) -> None:
    with pytest.raises(InvalidArgumentError, match=reason):
        _ = CommandParameter.check_type(typed)


@pytest.mark.parametrize("description", ["a \\ b", 'a """ b'])
def test_help_text_breaking_the_docstring_is_refused(description: str) -> None:
    with pytest.raises(InvalidArgumentError, match="cannot hold a backslash"):
        _ = CommandParameter("name", "str", description=description)


def test_the_default_help_text_is_the_name_in_words() -> None:
    assert CommandParameter.default_description("dry_run") == "Dry run."


@pytest.mark.parametrize(
    ("parameter", "declared"),
    [
        (CommandParameter("name", "str"), "name: Text"),
        (CommandParameter("name", "str", required=False), "name: Text | None = None"),
        (CommandParameter("yell", "bool", option=True, required=False), "yell: bool = False"),
        (
            CommandParameter("limit", "int", option=True, required=False),
            "limit: Text | None = None",
        ),
    ],
)
def test_the_declaration_gives_a_default_to_whatever_may_be_left_out(
    parameter: CommandParameter, declared: str
) -> None:
    assert parameter.declaration("Text") == declared
