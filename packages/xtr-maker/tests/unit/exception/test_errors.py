"""Unit tests for the typed attribute contracts of every error."""

from __future__ import annotations

from xtr_maker import (
    AppPackageNotFoundError,
    GeneratedSourceError,
    InvalidArgumentError,
    InvalidClassNameError,
    MakerError,
    TargetExistsError,
    UnsafePathError,
)


def test_invalid_class_name_error_carries_name_and_reason() -> None:
    error = InvalidClassNameError("None", "it is a Python keyword")

    assert (error.name, error.reason) == ("None", "it is a Python keyword")
    assert str(error) == "'None' cannot name a class: it is a Python keyword"
    assert isinstance(error, MakerError)
    assert isinstance(error, ValueError)


def test_target_exists_error_carries_the_path() -> None:
    error = TargetExistsError("src/app/x.py")

    assert error.path == "src/app/x.py"
    assert str(error).startswith("src/app/x.py already exists")
    assert isinstance(error, MakerError)
    assert isinstance(error, FileExistsError)


def test_generated_source_error_names_the_template_and_line() -> None:
    error = GeneratedSourceError("message/message.py.jinja", "invalid syntax", 3)

    assert (error.template, error.reason, error.line) == (
        "message/message.py.jinja",
        "invalid syntax",
        3,
    )
    assert str(error).startswith("message/message.py.jinja:3: ")
    assert isinstance(error, MakerError)


def test_generated_source_error_without_a_line_names_the_template() -> None:
    error = GeneratedSourceError("x.py.jinja", "bad")

    assert str(error) == "x.py.jinja: the rendered source does not parse: bad"


def test_unsafe_path_error_carries_path_and_reason() -> None:
    error = UnsafePathError("../x.py", "it lies outside the project directory")

    assert (error.path, error.reason) == ("../x.py", "it lies outside the project directory")
    assert isinstance(error, MakerError)
    assert isinstance(error, OSError)


def test_app_package_not_found_error_carries_the_package_and_where_it_was_looked_for() -> None:
    error = AppPackageNotFoundError("acme.shop", "/srv/project")

    assert (error.root_package, error.project_dir) == ("acme.shop", "/srv/project")
    assert "/srv/project/src/acme/shop/" in str(error)
    assert isinstance(error, MakerError)


def test_invalid_argument_error_is_a_value_error() -> None:
    assert isinstance(InvalidArgumentError("x"), ValueError)
    assert isinstance(InvalidArgumentError("x"), MakerError)
