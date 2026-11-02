"""The open and click tracking an email asks its mail provider for."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Final, final

from xtr_mime import UnstructuredHeader

if TYPE_CHECKING:
    from xtr_mime import Headers

__all__ = ["TrackingHeader"]

# What is trimmed around a flag and its value: whitespace and the null byte.
_TRIMMED: Final = " \t\n\r\0\x0b"


@final
class TrackingHeader(UnstructuredHeader):
    """``X-Track``: whether a provider tracks opens and clicks; ``None`` keeps its default.

    A provider transport turns it into the provider's own setting, and an explicit setting
    of the provider wins over it; a transport without tracking sends it as it is, to no
    effect. It is found by name, so a plain ``X-Track: opens=false; clicks=false`` header —
    an application-wide default, or an email read back from MIME — means the same; a
    tracking header set on the email itself wins over such a default.
    """

    NAME: ClassVar[str] = "X-Track"

    __slots__: ClassVar[tuple[str, ...]] = ("_clicks", "_opens")

    def __init__(self, opens: bool | None = None, clicks: bool | None = None) -> None:
        """Ask for opens and clicks to be tracked, or not; ``None`` keeps the default."""
        super().__init__(self.NAME, f"opens={_flag(opens)}; clicks={_flag(clicks)}")
        self._opens: bool | None = opens
        self._clicks: bool | None = clicks

    @classmethod
    def from_headers(cls, headers: Headers) -> TrackingHeader | None:
        """Return the tracking ``headers`` ask for, ``None`` if they carry no ``X-Track``.

        A tracking header is returned itself. A plain one is read as ``opens=<flag>;
        clicks=<flag>``, each flag ``true``, ``false`` or ``default``: whatever cannot be read —
        an unknown key, a flag that is none of those, a header that is not text — keeps the
        default, and the last of a repeated key wins.
        """
        header = headers.get(cls.NAME)
        if header is None:
            return None
        if isinstance(header, TrackingHeader):
            return header
        flags: dict[str, bool | None] = {"opens": None, "clicks": None}
        body = header.get_body()
        for part in body.split(";") if isinstance(body, str) else ():
            key, equals, value = part.strip(_TRIMMED).partition("=")
            if equals and key in flags:
                flags[key] = {"true": True, "false": False}.get(value.strip(_TRIMMED))
        return cls(flags["opens"], flags["clicks"])

    def get_opens(self) -> bool | None:
        """Return whether opens are tracked, ``None`` for the provider's default."""
        return self._opens

    def get_clicks(self) -> bool | None:
        """Return whether clicks are tracked, ``None`` for the provider's default."""
        return self._clicks


def _flag(flag: bool | None) -> str:
    match flag:
        case None:
            return "default"
        case True:
            return "true"
        case False:
            return "false"
