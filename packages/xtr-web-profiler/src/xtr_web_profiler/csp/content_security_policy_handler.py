"""Lets the toolbar's inline script and style run under the page's content security policy."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from collections.abc import Mapping

    from starlette.datastructures import MutableHeaders

    from .nonce_generator import NonceGenerator

__all__ = [
    "CSP_HEADERS",
    "SCRIPT_NONCE_HEADER",
    "STYLE_NONCE_HEADER",
    "ContentSecurityPolicyHandler",
]

SCRIPT_NONCE_HEADER: Final = "X-Profiler-Script-Nonce"
"""Carries the host page's script nonce on the toolbar's own requests."""

STYLE_NONCE_HEADER: Final = "X-Profiler-Style-Nonce"
"""Carries the host page's style nonce on the toolbar's own requests."""

CSP_HEADERS: Final = (
    "content-security-policy",
    "content-security-policy-report-only",
    "x-content-security-policy",
)
_SCRIPT: Final = ("script-src", "script-src-elem")
_STYLE: Final = ("style-src", "style-src-elem")
_DEFAULT: Final = "default-src"
_UNSAFE_INLINE: Final = "'unsafe-inline'"


@final
class ContentSecurityPolicyHandler:
    """Adds the toolbar's nonces to a response's policy, or lifts the policy off a profiler page.

    The toolbar is an inline script and an inline style, which a page's
    policy forbids unless it allows inline code or names their nonce. Every
    script and style directive of each policy header the response carries —
    falling back to ``default-src`` where the plain directive is absent — gets
    ``'unsafe-inline'`` and the nonce, unless it already allows inline code
    outright. A browser that understands nonces ignores ``'unsafe-inline'``
    beside one, and one that does not still runs the toolbar. A response with
    no policy is left alone.

    A toolbar fragment fetched later by the page reuses the page's nonces,
    which its request carries in :data:`SCRIPT_NONCE_HEADER` and
    :data:`STYLE_NONCE_HEADER`.
    """

    __slots__ = ("_generator",)

    def __init__(self, generator: NonceGenerator) -> None:
        """Make nonces with ``generator``."""
        self._generator = generator

    def get_nonces(self, request_headers: Mapping[str, str]) -> dict[str, str]:
        """Return the script and style nonces: the request's own, or fresh ones."""
        return {
            "csp_script_nonce": request_headers.get(SCRIPT_NONCE_HEADER.lower())
            or self._generator.generate(),
            "csp_style_nonce": request_headers.get(STYLE_NONCE_HEADER.lower())
            or self._generator.generate(),
        }

    def update_response_headers(self, nonces: Mapping[str, str], headers: MutableHeaders) -> None:
        """Let ``nonces`` through every policy ``headers`` carries."""
        for name in CSP_HEADERS:
            policy = headers.get(name)
            if policy is None:
                continue
            directives = _parse(policy)
            _allow(directives, _SCRIPT, nonces["csp_script_nonce"])
            _allow(directives, _STYLE, nonces["csp_style_nonce"])
            headers[name] = _serialise(directives)

    def disable_csp(self, headers: MutableHeaders) -> None:
        """Remove every policy ``headers`` carries."""
        for name in CSP_HEADERS:
            if name in headers:
                del headers[name]


def _parse(policy: str) -> dict[str, list[str]]:
    directives: dict[str, list[str]] = {}
    for part in policy.split(";"):
        tokens = part.split()
        if tokens:
            directives[tokens[0].lower()] = tokens[1:]
    return directives


def _serialise(directives: Mapping[str, list[str]]) -> str:
    return "; ".join(" ".join([name, *values]) for name, values in directives.items())


def _allow(directives: dict[str, list[str]], names: tuple[str, ...], nonce: str) -> None:
    for name in names:
        values = directives.get(name)
        if values is None:
            # The *-elem directives fall back to their plain one in the browser
            # itself; only the plain one falls back to default-src.
            if name.endswith("-elem") or _DEFAULT not in directives:
                continue
            values = list(directives[_DEFAULT])
        if _authorizes_inline(values):
            continue
        directives[name] = [
            *(value for value in values if value != "'none'"),
            _UNSAFE_INLINE,
            f"'nonce-{nonce}'",
        ]


def _authorizes_inline(values: list[str]) -> bool:
    """Tell whether a directive already runs any inline code: inline allowed, no nonce or hash."""
    if _UNSAFE_INLINE not in values:
        return False
    return not any(
        value.startswith(("'nonce-", "'sha256-", "'sha384-", "'sha512-")) for value in values
    )
