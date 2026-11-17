"""The profiler's pages: the toolbar fragment, a profile, the search, a source file."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final, cast, final
from urllib.parse import urlencode

from starlette.routing import Match

from xtr_web_profiler.profiler.collector_view import CollectorView

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from starlette.requests import Request
    from starlette.routing import BaseRoute
    from starlette.types import Scope
    from xtr_http_kernel.bridge import Response
    from xtr_http_kernel.profiler import Profile, Profiler

    from xtr_web_profiler.profiler.template_manager import TemplateManager

__all__ = ["PROFILER_PAGE_HEADER", "ProfilerController"]

PROFILER_PAGE_HEADER: Final = "X-Profiler-Page"
"""Marks a response as one of the profiler's own pages, which no policy restricts."""

_EMPTY: Final = "empty"
_LATEST: Final = "latest"
_DEFAULT_LIMIT: Final = 10
_MAX_LIMIT: Final = 100
_NOT_FOUND: Final = 404
_FOUND: Final = 302
_SEARCH_FIELDS: Final = ("ip", "url", "method", "status_code", "start", "end", "limit")
_HTML: Final = "text/html; charset=utf-8"


@final
class ProfilerController:
    """Answers every page of the profiler.

    Each page leaves its own request unprofiled, so looking at profiles never
    makes more of them. With the profiler off — the application turned it off
    under the http kernel's configuration — every page answers 404, as an
    application without the profiler would.
    """

    __slots__ = ("_manager", "_profiler", "_project_dir")

    def __init__(
        self,
        profiler: Profiler | None,
        manager: TemplateManager,
        project_dir: Path,
    ) -> None:
        """Show what ``profiler`` stored, through ``manager``'s templates.

        Args:
            profiler: What stores the profiles; ``None`` when profiling is off.
            manager: What renders the pages and the panels.
            project_dir: The project's root: the source view shows no file
                outside it.
        """
        self._profiler = profiler
        self._manager = manager
        self._project_dir = project_dir

    async def toolbar(self, request: Request, response: Response, token: str) -> Response:
        """Return the toolbar of the profile ``token``: every collector's ``toolbar`` block."""
        profiler = self._enter()
        if profiler is None:
            return _status(response, _NOT_FOUND)
        if token == _EMPTY:
            return _html(response, "")
        profile = await profiler.load_profile(token)
        if profile is None:
            return _html(response, "", _NOT_FOUND)
        url = _urls(request)
        nonces = _nonces(request)
        items = [
            {"name": name, "html": html}
            for name, template in self._manager.get_names(profile, profiler)
            if (
                html := self._manager.render_block(
                    template, "toolbar", self._panel_context(request, profile, name, url)
                )
            )
        ]
        context = {
            "token": token,
            "profile": profile,
            "items": items,
            "url": url,
            "profiler_url": url("_profiler", token=token),
            **nonces,
        }
        return _html(
            response, self._manager.render("@xtr_web_profiler/profiler/toolbar.html.j2", context)
        )

    async def stylesheet(self, response: Response) -> Response:
        """Return the toolbar's stylesheet, which a page may cache for ten minutes."""
        _ = self._enter()
        css = self._manager.render("@xtr_web_profiler/profiler/toolbar.css.j2", {})
        response.body = css.encode()
        return (
            response.with_header("content-type", "text/css; charset=utf-8")
            .with_header("cache-control", "max-age=600, private")
            .with_header(PROFILER_PAGE_HEADER, "1")
        )

    async def home(self, request: Request, response: Response) -> Response:
        """Send the browser to the latest profiles."""
        if self._enter() is None:
            return _status(response, _NOT_FOUND)
        return _redirect(response, _urls(request)("_profiler_search_results", token=_EMPTY))

    async def search(self, request: Request, response: Response) -> Response:
        """Send the browser to the profile a token names, or to the profiles the filters find."""
        if self._enter() is None:
            return _status(response, _NOT_FOUND)
        url = _urls(request)
        token = request.query_params.get("token", "").strip()
        if token:
            return _redirect(response, url("_profiler", token=token))
        target = url("_profiler_search_results", token=_EMPTY)
        query = {
            field: value for field in _SEARCH_FIELDS if (value := request.query_params.get(field))
        }
        return _redirect(response, f"{target}?{urlencode(query)}" if query else target)

    async def search_results(self, request: Request, response: Response, token: str) -> Response:
        """Return the stored profiles the filters find, newest first."""
        profiler = self._enter()
        if profiler is None:
            return _status(response, _NOT_FOUND)
        search = {field: request.query_params.get(field, "") for field in _SEARCH_FIELDS}
        limit = min(_integer(search["limit"]) or _DEFAULT_LIMIT, _MAX_LIMIT)
        results = await profiler.find(
            search["ip"] or None,
            search["url"] or None,
            limit,
            search["method"] or None,
            start=_integer(search["start"]),
            end=_integer(search["end"]),
            status_code=_integer(search["status_code"]),
        )
        context = {
            "token": token,
            "results": results,
            "search": search,
            "url": _urls(request),
            **_nonces(request),
        }
        return _html(
            response, self._manager.render("@xtr_web_profiler/profiler/results.html.j2", context)
        )

    async def panel(self, request: Request, response: Response, token: str) -> Response:
        """Return the profile ``token`` with its menu and one panel; ``latest`` is the newest."""
        profiler = self._enter()
        if profiler is None:
            return _status(response, _NOT_FOUND)
        url = _urls(request)
        profile = await self._load(profiler, token)
        if profile is None:
            context = {"token": token, "url": url, **_nonces(request)}
            page = self._manager.render("@xtr_web_profiler/profiler/info.html.j2", context)
            return _html(response, page, _NOT_FOUND)
        names = self._manager.get_names(profile, profiler)
        selected = _selected(
            request.query_params.get("panel"), profile, [name for name, _ in names]
        )
        items: list[dict[str, object]] = []
        panel_html = head_html = ""
        for name, template in names:
            context = self._panel_context(request, profile, name, url)
            items.append(
                {
                    "name": name,
                    "menu": self._manager.render_block(template, "menu", context),
                    "url": _panel_url(url, profile.token, name),
                    "selected": name == selected,
                }
            )
            if name == selected:
                panel_html = self._manager.render_block(template, "panel", context)
                head_html = self._manager.render_block(template, "head", context)
        context = {
            "token": profile.token,
            "profile": profile,
            "items": items,
            "panel": selected,
            "panel_html": panel_html,
            "head_html": head_html,
            "search": dict.fromkeys(_SEARCH_FIELDS, ""),
            "url": url,
            **_nonces(request),
        }
        return _html(
            response, self._manager.render("@xtr_web_profiler/profiler/layout.html.j2", context)
        )

    async def open_file(self, request: Request, response: Response) -> Response:
        """Return a source file of the project, the asked-for line marked."""
        if self._enter() is None:
            return _status(response, _NOT_FOUND)
        path = self._project_file(request.query_params.get("file", ""))
        if path is None:
            return _html(response, "", _NOT_FOUND)
        line = _integer(request.query_params.get("line", "")) or 1
        lines = [
            {"number": number, "text": text}
            for number, text in enumerate(path.read_text("utf-8", errors="replace").splitlines(), 1)
        ]
        context = {
            "file": str(path),
            "line": line,
            "lines": lines,
            "url": _urls(request),
            **_nonces(request),
        }
        return _html(
            response, self._manager.render("@xtr_web_profiler/profiler/open.html.j2", context)
        )

    def _enter(self) -> Profiler | None:
        """Leave this request unprofiled, and return the profiler."""
        if self._profiler is not None:
            self._profiler.disable()
        return self._profiler

    async def _load(self, profiler: Profiler, token: str) -> Profile | None:
        if token != _LATEST:
            return await profiler.load_profile(token)
        latest = await profiler.find(None, None, 1, None)
        return await profiler.load_profile(latest[0].token) if latest else None

    def _panel_context(
        self,
        request: Request,
        profile: Profile,
        name: str,
        url: Callable[..., str],
    ) -> dict[str, object]:
        token = profile.token

        def panel_url(panel: str) -> str:
            return _panel_url(url, token, panel)

        def open_file_url(file: str, line: int = 1) -> str:
            return f"{url('_profiler_open_file')}?{urlencode({'file': file, 'line': line})}"

        return {
            "collector": CollectorView(name, profile.get_collector(name)),
            "profile": profile,
            "token": token,
            "url": url,
            "panel_url": panel_url,
            "open_file_url": open_file_url,
            "route_traces": _route_traces(request, profile) if name == "router" else [],
            **_nonces(request),
        }

    def _project_file(self, file: str) -> Path | None:
        """Return the project file ``file`` names, or ``None`` outside the project or hidden.

        A part starting with ``.`` — ``..``, a ``.env``, a ``.git`` folder — is
        refused wherever it appears in what was asked for and in the path below
        the project root, so neither a climb nor a hidden file is shown.
        """
        if not file:
            return None
        candidate = Path(file)
        root = self._project_dir.resolve()
        if candidate.is_absolute():
            asked = candidate.relative_to(root) if candidate.is_relative_to(root) else None
        else:
            asked = candidate
        if asked is None or any(part.startswith(".") for part in asked.parts):
            return None
        resolved = (root / asked).resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():
            return None
        return resolved


def _urls(request: Request) -> Callable[..., str]:
    def url(name: str, /, **params: object) -> str:
        return str(request.url_for(name, **params))

    return url


def _panel_url(url: Callable[..., str], token: str, panel: str) -> str:
    return f"{url('_profiler', token=token)}?{urlencode({'panel': panel})}"


def _nonces(request: Request) -> dict[str, str]:
    return {
        "csp_script_nonce": request.headers.get("x-profiler-script-nonce", ""),
        "csp_style_nonce": request.headers.get("x-profiler-style-nonce", ""),
    }


def _selected(asked: str | None, profile: Profile, names: list[str]) -> str | None:
    if asked in names:
        return asked
    if "exception" in names and profile.get_collector("exception").get("has_exception") is True:
        return "exception"
    return names[0] if names else None


def _route_traces(request: Request, profile: Profile) -> list[dict[str, object]]:
    """Return how each route of the application matched the profiled request."""
    if not profile.has_collector("request"):
        return []
    data: Mapping[str, object] = profile.get_collector("request")
    scope: Scope = {
        "type": "http",
        "path": str(data.get("path", "/")),
        "method": profile.method,
        "root_path": "",
        "path_params": {},
        "headers": [],
    }
    application = cast("object", request.app)
    routes = cast("Sequence[BaseRoute]", getattr(application, "routes", ()))
    traces: list[dict[str, object]] = []
    for route in routes:
        match, _ = route.matches(scope)
        traces.append(
            {
                "name": cast("str | None", getattr(route, "name", None)),
                "path": cast("str", getattr(route, "path", "")),
                "methods": sorted(cast("set[str] | None", getattr(route, "methods", None)) or ()),
                "match": {Match.FULL: "full", Match.PARTIAL: "method"}.get(match, "none"),
            }
        )
    return traces


def _integer(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def _html(response: Response, body: str, status: int = 200) -> Response:
    response.body = body.encode()
    return (
        response.with_status(status)
        .with_header("content-type", _HTML)
        .with_header(PROFILER_PAGE_HEADER, "1")
    )


def _status(response: Response, status: int) -> Response:
    response.body = b""
    return response.with_status(status)


def _redirect(response: Response, location: str) -> Response:
    response.body = b""
    return (
        response.with_status(_FOUND)
        .with_header("location", location)
        .with_header(PROFILER_PAGE_HEADER, "1")
    )
