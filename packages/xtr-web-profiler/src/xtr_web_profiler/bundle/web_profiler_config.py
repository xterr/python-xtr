"""Configuration for :class:`~xtr_web_profiler.bundle.WebProfilerBundle`."""

from __future__ import annotations

import re
from dataclasses import dataclass

from xtr_web_profiler.exception.invalid_argument_error import InvalidArgumentError

__all__ = ["WebProfilerConfig"]


@dataclass(frozen=True, slots=True)
class WebProfilerConfig:
    """What an application may change about the toolbar and the profiler pages.

    Attributes:
        toolbar: Whether HTML pages get the debug toolbar.
        ajax_replace: Whether a background request whose response names a
            profile reloads the toolbar with that profile.
        intercept_redirects: Whether a redirect answering a page is shown as a
            page of its own — with the toolbar, and a link to follow it — so
            the request that redirected can be inspected before it is left.
        excluded_ajax_paths: A regular expression; background requests to a
            matching path are left out of the toolbar's list.
        file_link_format: How a file and line open in an editor — ``{file}``
            is the file, ``{line}`` the line, as in
            ``"pycharm://open?file={file}&line={line}"`` or
            ``"vscode://file/{file}:{line}"``. ``None`` opens them in the
            profiler's own source view.

    Raises:
        InvalidArgumentError: When ``excluded_ajax_paths`` is not a regular
            expression, or ``file_link_format`` does not name the file.
    """

    toolbar: bool = True
    ajax_replace: bool = False
    intercept_redirects: bool = False
    excluded_ajax_paths: str = "^/(_wdt|_profiler)"
    file_link_format: str | None = None

    def __post_init__(self) -> None:
        """Refuse values the toolbar would misread."""
        try:
            _ = re.compile(self.excluded_ajax_paths)
        except re.error as error:
            message = (
                f"excluded_ajax_paths is {self.excluded_ajax_paths!r}, "
                "which is not a regular expression"
            )
            raise InvalidArgumentError(message) from error
        if self.file_link_format is not None and "{file}" not in self.file_link_format:
            message = (
                f"file_link_format must name the file with {{file}}: {self.file_link_format!r}"
            )
            raise InvalidArgumentError(message)
