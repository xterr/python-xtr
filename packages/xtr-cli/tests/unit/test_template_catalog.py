from __future__ import annotations

import ast

import pytest

from xtr_cli import TemplateCatalog, UnknownTemplateError

_VALUES = {"name": "web-shop", "app": "web_shop", "python": "3.13", "minor": "13"}


def _kernel_call(name: str) -> ast.Call:
    """Return the ``Kernel(...)`` call of the template's rendered ``kernel.py``."""
    source = dict(TemplateCatalog.default().load(name).render(_VALUES))["src/web_shop/kernel.py"]
    calls = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Kernel"
    ]
    assert len(calls) == 1
    return calls[0]


def test_the_shipped_templates_are_cli_and_webapp() -> None:
    assert TemplateCatalog.default().names() == ("cli", "webapp")


@pytest.mark.parametrize("name", ["cli", "webapp"])
def test_every_shipped_template_renders(name: str) -> None:
    template = TemplateCatalog.default().load(name)

    paths = {path for path, _ in template.render(_VALUES)}

    assert {"AGENTS.md", "bin/console", "pyproject.toml", "src/web_shop/kernel.py"} <= paths
    assert "src/web_shop/__main__.py" in paths
    assert all(step for step in template.steps(_VALUES))


@pytest.mark.parametrize("name", ["cli", "webapp"])
def test_every_shipped_template_writes_an_executable_console_wrapper(name: str) -> None:
    console = dict(TemplateCatalog.default().load(name).render(_VALUES))["bin/console"]

    assert console.startswith("#!/usr/bin/env sh\n")
    assert "exec uv run web-shop" in console
    assert "$$" not in console


@pytest.mark.parametrize("name", ["cli", "webapp"])
def test_every_shipped_template_writes_rules_for_a_coding_agent(name: str) -> None:
    agents = dict(TemplateCatalog.default().load(name).render(_VALUES))["AGENTS.md"]

    assert agents.startswith("# AGENTS.md — rules for a coding agent working in web-shop\n")
    assert "$$" not in agents


@pytest.mark.parametrize("name", ["cli", "webapp"])
def test_every_shipped_kernel_is_built_from_its_own_package(name: str) -> None:
    call = _kernel_call(name)

    assert [ast.unparse(argument) for argument in call.args] == ["__package__"]
    assert "name" not in {keyword.arg for keyword in call.keywords}


def test_the_web_kernel_leaves_the_web_application_out_relative_to_its_package() -> None:
    keywords = {keyword.arg: keyword.value for keyword in _kernel_call("webapp").keywords}

    assert ast.literal_eval(keywords["exclude"]) == (".web.app",)


@pytest.mark.parametrize("name", ["cli", "webapp"])
def test_no_shipped_template_writes_what_a_recipe_writes(name: str) -> None:
    paths = {path for path, _ in TemplateCatalog.default().load(name).render(_VALUES)}

    assert not paths & {"src/web_shop/config/bundles.py", ".env", "xtr.lock"}


def test_the_web_template_keeps_the_console() -> None:
    template = TemplateCatalog.default().load("webapp")
    pyproject = dict(template.render(_VALUES))["pyproject.toml"]

    assert "xtr-console" in template.dependencies
    assert 'web-shop = "web_shop.__main__:main"' in pyproject
    assert 'web-shop-web = "web_shop.web.__main__:main"' in pyproject


def test_the_console_template_starts_with_the_kernel_the_console_and_the_environment() -> None:
    template = TemplateCatalog.default().load("cli")

    assert template.dependencies == ("xtr-dependency-injection", "xtr-console", "xtr-dotenv")


def test_the_web_template_starts_with_the_web_application_packages() -> None:
    template = TemplateCatalog.default().load("webapp")

    assert {
        "xtr-logging",
        "xtr-http-kernel",
        "xtr-orm[postgres]",
        "xtr-messenger[amqp]",
        "xtr-http-client",
        "xtr-notifier",
        "xtr-security",
    } <= set(template.dependencies)


def test_an_unknown_template_names_the_shipped_ones() -> None:
    with pytest.raises(UnknownTemplateError, match="choose cli, webapp") as raised:
        _ = TemplateCatalog.default().load("nowhere")

    assert raised.value.available == ("cli", "webapp")
