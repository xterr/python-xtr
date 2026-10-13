"""A matcher over the path of a request."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final, final
from urllib.parse import unquote

from typing_extensions import override

from xtr_http_foundation.request_matcher_interface import RequestMatcherInterface

from ._compiled_regexp import compiled_regexp

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["PathRequestMatcher"]

_ROOT_PATH: Final = "root_path"
"""Where the server reports the path the application itself is reached under."""


def _path_below_the_application(request: ServerRequestInterface) -> str:
    """Return the path the application sees, free of per cent escapes.

    An application mounted under a path is reached at that path plus its own,
    and a rule is written about its own: moving the mount must not rewrite every
    matcher. The server reports the mount among the environment parameters.

    The escapes are undone so that a rule is written about the characters that
    were asked for rather than about one of the several ways of writing them;
    ``/admin/fo o`` therefore matches ``/admin/fo%20o``.
    """
    path = request.get_uri().get_path()
    mounted_at = request.get_server_params().get(_ROOT_PATH)
    if isinstance(mounted_at, str) and mounted_at and path.startswith(mounted_at):
        path = path[len(mounted_at) :]

    return unquote(path)


@final
class PathRequestMatcher(RequestMatcherInterface):
    """Claims a request whose path matches an expression.

    The expression is searched for in the path rather than having to describe
    the whole of it, so ``/admin`` is the rule for anything under that path and
    ``^/admin/[0-9]+$`` the rule for exactly one shape of it. Nothing in the
    expression is a path parameter: ``^/{_locale}/login$`` matches a path
    holding those very braces, not one holding a language.

    A newline in a path matches ``.``, since a path is one value rather than
    several lines — so an expression bounded by ``^`` and ``$`` cannot be
    slipped past with an escaped control character.
    """

    __slots__ = ("_regexp",)

    def __init__(self, regexp: str) -> None:
        """Record the expression a request's path has to match.

        Args:
            regexp: The expression, read when the matcher is built.

        Raises:
            InvalidArgumentError: When it does not read as one; it names the
                expression.
        """
        self._regexp = compiled_regexp(regexp, re.DOTALL)

    @override
    async def matches(self, request: ServerRequestInterface) -> bool:
        """Tell whether the path of ``request`` matches this matcher's expression."""
        return self._regexp.search(_path_below_the_application(request)) is not None
