from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support import write_project
from xtr_cli import (
    ProjectNotFoundError,
    WebEntryPoint,
    WebEntryPointFinder,
    WebEntryPointNotFoundError,
)

if TYPE_CHECKING:
    from pathlib import Path

_SERVER = "import uvicorn\n\ndef main() -> None:\n    uvicorn.run('shop.web.app:app')\n"
_APP = "from fastapi import FastAPI\n\napp = FastAPI()\n"


@pytest.fixture
def finder() -> WebEntryPointFinder:
    return WebEntryPointFinder()


def test_the_project_is_the_nearest_directory_holding_a_manifest(tmp_path: Path) -> None:
    project = write_project(tmp_path / "shop", {}, {"src/shop/web/app.py": ""})

    assert WebEntryPointFinder.project_dir(project / "src" / "shop" / "web") == project


def test_no_manifest_anywhere_above_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The tests run inside a project, so the manifest looked for is one no directory holds.
    monkeypatch.setattr("xtr_cli.web_entry_point_finder._PYPROJECT", "no-such-manifest.toml")

    with pytest.raises(ProjectNotFoundError):
        _ = WebEntryPointFinder.project_dir(tmp_path)


def test_a_script_whose_module_imports_a_server_is_the_entry_point(
    tmp_path: Path, finder: WebEntryPointFinder
) -> None:
    project = write_project(
        tmp_path,
        {"shop": "shop.__main__:main", "serve-it": "shop.web.__main__:main"},
        {"src/shop/__main__.py": "def main() -> None: ...\n", "src/shop/web/__main__.py": _SERVER},
    )

    assert finder.find(project) == (WebEntryPoint("script", "serve-it"),)


@pytest.mark.parametrize("server", ["from hypercorn.asyncio import serve", "import granian.server"])
def test_other_servers_count_too(tmp_path: Path, finder: WebEntryPointFinder, server: str) -> None:
    project = write_project(tmp_path, {"run": "shop.serve:main"}, {"shop/serve.py": f"{server}\n"})

    assert finder.find(project) == (WebEntryPoint("script", "run"),)


def test_a_script_named_as_a_web_entry_point_counts_without_a_readable_module(
    tmp_path: Path, finder: WebEntryPointFinder
) -> None:
    project = write_project(tmp_path, {"shop-web": "shop.missing:main"}, {})

    assert finder.find(project) == (WebEntryPoint("script", "shop-web"),)


def test_with_a_web_script_no_asgi_object_is_offered(
    tmp_path: Path, finder: WebEntryPointFinder
) -> None:
    project = write_project(
        tmp_path,
        {"shop-web": "shop.web.__main__:main"},
        {"src/shop/web/__main__.py": _SERVER, "src/shop/web/app.py": _APP},
    )

    assert [entry.kind for entry in finder.find(project)] == ["script"]


def test_without_a_web_script_module_level_asgi_objects_are_found(
    tmp_path: Path, finder: WebEntryPointFinder
) -> None:
    project = write_project(
        tmp_path,
        {"shop": "shop.cli:main"},
        {
            "src/shop/__init__.py": "import starlette.applications as s\n\nsite = s.Starlette()\n",
            "src/shop/api.py": "from litestar import Litestar\n\napi: Litestar = Litestar([])\n",
            "src/shop/cli.py": "def main() -> None: ...\n",
            "src/shop/__main__.py": _APP,
            "src/shop/broken.py": "app = (\n",
            "src/shop/inner.py": "def build():\n    app = FastAPI()\n    return app\n",
            "tests/test_app.py": _APP,
            ".venv/lib/app.py": _APP,
        },
    )

    assert [entry.target for entry in finder.find(project)] == ["shop.api:api", "shop:site"]


def test_a_flat_project_is_searched_from_its_root(
    tmp_path: Path, finder: WebEntryPointFinder
) -> None:
    project = write_project(
        tmp_path,
        {},
        {"main.py": _APP, "venv/pyvenv.cfg": "", "venv/app.py": _APP, "my-scripts/app.py": _APP},
    )

    assert finder.find(project) == (WebEntryPoint("asgi", "main:app"),)


def test_an_unreadable_manifest_offers_only_asgi_objects(
    tmp_path: Path, finder: WebEntryPointFinder
) -> None:
    _ = (tmp_path / "pyproject.toml").write_text("[project", encoding="utf-8")
    _ = (tmp_path / "app.py").write_text(_APP, encoding="utf-8")

    assert finder.find(tmp_path) == (WebEntryPoint("asgi", "app:app"),)


def test_nothing_to_serve_finds_nothing(tmp_path: Path, finder: WebEntryPointFinder) -> None:
    project = write_project(tmp_path, {"shop": "shop:main"}, {"shop/__init__.py": "x = 1\n"})

    assert finder.find(project) == ()


def test_an_entrypoint_naming_a_script_resolves_to_it(tmp_path: Path) -> None:
    project = write_project(tmp_path, {"shop": "shop:main"}, {})

    assert WebEntryPointFinder.resolve(project, "shop") == WebEntryPoint("script", "shop")


def test_an_entrypoint_naming_a_module_attribute_resolves_to_an_asgi_object(
    tmp_path: Path,
) -> None:
    resolved = WebEntryPointFinder.resolve(write_project(tmp_path, {}, {}), "shop.web.app:app")

    assert resolved == WebEntryPoint("asgi", "shop.web.app:app")


@pytest.mark.parametrize(
    ("given", "reason"),
    [("nope", "no script 'nope'"), ("shop web:app", "not a module:attribute"), ("a:", "not a")],
)
def test_an_entrypoint_naming_nothing_is_refused(tmp_path: Path, given: str, reason: str) -> None:
    with pytest.raises(WebEntryPointNotFoundError, match=reason):
        _ = WebEntryPointFinder.resolve(write_project(tmp_path, {}, {}), given)
