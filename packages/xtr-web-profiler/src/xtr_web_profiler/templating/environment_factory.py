"""The template environment every profiler page and panel is rendered in."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, cast

from jinja2 import Environment, StrictUndefined, select_autoescape

from .dump import dump
from .template_loader import TemplateLoader

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["create_environment"]

_UNITS: Final = ("B", "KiB", "MiB", "GiB", "TiB")
_STEP: Final = 1024.0


def create_environment(file_link_format: str | None = None) -> Environment:
    """Return the environment the profiler renders with.

    Templates load through :class:`TemplateLoader`, so ``"@<package>/<path>"``
    reaches any installed package's templates; every value is escaped unless
    marked safe, and an undefined name fails rather than rendering empty.

    Filters every template may use:

    - ``profiler_dump`` — a value a collector kept, as browsable HTML;
    - ``format_bytes`` — ``1536`` as ``1.5 KiB``;
    - ``format_ms`` — ``12.345`` as ``12.3 ms``;
    - ``format_time`` — seconds since the epoch, as an ISO date in UTC;
    - ``file_link`` — a file and line as an editor link, or ``None`` when no
      ``file_link_format`` is set: ``{{ frame.file | file_link(frame.line) }}``.

    Args:
        file_link_format: How a file and line open in an editor, ``{file}``
            and ``{line}`` standing for them.
    """
    environment = Environment(
        loader=TemplateLoader(),
        autoescape=select_autoescape(default=True, default_for_string=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    def file_link(file: str, line: int = 1) -> str | None:
        if file_link_format is None:
            return None
        return file_link_format.replace("{file}", file).replace("{line}", str(line))

    # The engine types its filter table by its own filters; any callable is one.
    filters = cast("dict[str, Callable[..., object]]", environment.filters)
    filters["profiler_dump"] = dump
    filters["format_bytes"] = format_bytes
    filters["format_ms"] = format_ms
    filters["format_time"] = format_time
    filters["file_link"] = file_link
    return environment


def format_bytes(value: float | None) -> str:
    """Return a size in bytes in the largest binary unit it fills, or ``n/a``."""
    if value is None:
        return "n/a"
    size = float(value)
    for unit in _UNITS:
        if size < _STEP or unit == _UNITS[-1]:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= _STEP
    return f"{size:.1f} {_UNITS[-1]}"  # pragma: no cover — the loop always returns


def format_ms(value: float | None) -> str:
    """Return a duration in milliseconds to one decimal, or ``n/a``."""
    return "n/a" if value is None else f"{value:.1f} ms"


def format_time(value: float | None) -> str:
    """Return seconds since the epoch as ``YYYY-MM-DD HH:MM:SS`` in UTC, or ``n/a``."""
    if value is None:
        return "n/a"
    return datetime.fromtimestamp(value, UTC).strftime("%Y-%m-%d %H:%M:%S")
