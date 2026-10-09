from __future__ import annotations

from xtr_cli import WebEntryPoint


def test_a_script_is_run_as_it_is_and_told_where_to_serve_through_variables() -> None:
    argv, environment = WebEntryPoint("script", "shop-web").command("10.0.0.5", 9000, reload=True)

    assert argv == ("uv", "run", "shop-web")
    assert environment == {"WEB_HOST": "10.0.0.5", "WEB_PORT": "9000", "WEB_RELOAD": "1"}


def test_a_script_left_to_its_defaults_is_given_no_variable() -> None:
    assert WebEntryPoint("script", "shop-web").command(None, None, reload=False)[1] == {}


def test_an_asgi_object_is_handed_to_uvicorn_with_defaults() -> None:
    argv, environment = WebEntryPoint("asgi", "shop.app:app").command(None, None, reload=False)

    assert argv == (
        "uv", "run", "uvicorn", "shop.app:app", "--host", "127.0.0.1", "--port", "8000",
    )  # fmt: skip
    assert environment == {}


def test_an_asgi_object_reloads_where_asked() -> None:
    argv, _ = WebEntryPoint("asgi", "shop.app:app").command("10.0.0.5", 9000, reload=True)

    assert argv[-5:] == ("--host", "10.0.0.5", "--port", "9000", "--reload")


def test_the_label_is_what_entrypoint_takes() -> None:
    assert WebEntryPoint("asgi", "shop.app:app").label == "shop.app:app"
