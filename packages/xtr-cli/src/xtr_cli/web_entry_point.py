"""WebEntryPoint: what serves an application, and the command that starts it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, final

__all__ = ["DEFAULT_HOST", "DEFAULT_PORT", "WebEntryPoint"]

DEFAULT_HOST: Final = "127.0.0.1"
"""Where an application found as an ASGI object is served when no host is given."""

DEFAULT_PORT: Final = 8000
"""The port an application found as an ASGI object is served on when none is given."""


@final
@dataclass(frozen=True, slots=True)
class WebEntryPoint:
    """One way to serve an application: a console script, or an ASGI object.

    A **script** is the application's own web entry point, run as it is —
    whatever it does before serving, loading its ``.env`` files among it, still
    happens. It is told the host, the port and whether to reload through
    ``WEB_HOST``, ``WEB_PORT`` and ``WEB_RELOAD``, the variables the ``webapp``
    template's entry point reads; a script that reads none of them serves where
    it always does.

    An **ASGI object** — a module-level ``FastAPI()``, ``Starlette()`` or
    ``Litestar()`` — is handed to ``uvicorn`` directly, which then has to be
    installed in the project. Nothing runs before it is imported, so the
    application's own environment loading does not either.

    Attributes:
        kind: ``"script"`` or ``"asgi"``.
        target: The script's name, or the ASGI object as ``module:attribute``.
    """

    kind: Literal["script", "asgi"]
    target: str

    @property
    def label(self) -> str:
        """The entry point as ``--entrypoint`` takes it."""
        return self.target

    def command(
        self, host: str | None, port: int | None, *, reload: bool
    ) -> tuple[tuple[str, ...], dict[str, str]]:
        """Return the command serving this entry point, and the variables set for it.

        Args:
            host: Where to listen, or ``None`` for the entry point's default.
            port: The port to listen on, or ``None`` for the entry point's default.
            reload: Whether to restart the server when a source file changes.
        """
        if self.kind == "script":
            environment: dict[str, str] = {}
            if host is not None:
                environment["WEB_HOST"] = host
            if port is not None:
                environment["WEB_PORT"] = str(port)
            if reload:
                environment["WEB_RELOAD"] = "1"
            return ("uv", "run", self.target), environment
        argv = (
            "uv",
            "run",
            "uvicorn",
            self.target,
            "--host",
            host if host is not None else DEFAULT_HOST,
            "--port",
            str(port if port is not None else DEFAULT_PORT),
        )
        return ((*argv, "--reload") if reload else argv), {}
