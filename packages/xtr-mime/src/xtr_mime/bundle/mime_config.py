"""Configuration for :class:`~xtr_mime.bundle.MimeBundle`."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from xtr_mime.exception import InvalidArgumentError

__all__ = ["MimeConfig"]


@dataclass(frozen=True, slots=True)
class MimeConfig:
    """How the bundle builds the container's MIME types table.

    Buildable with no arguments: an application listing the bundle without configuring it gets
    the standard library's built-in table.

    ```python
    MimeConfig(extra_map={"application/mbox": ["mbox"]})
    ```

    Attributes:
        extra_map: Extensions by MIME type, each without its leading dot, ranked before the
            standard table's — what :class:`~xtr_mime.MimeTypes` takes as ``extra_map``.
    """

    extra_map: Mapping[str, Sequence[str]] = field(default_factory=dict[str, Sequence[str]])

    def __post_init__(self) -> None:
        """Refuse an extra map the table would read wrongly.

        A key is a ``type/subtype``; a value is a sequence of extensions, not one string, which
        the table would read character by character; an extension is not empty and carries no
        leading dot, which the table would keep as part of it.

        Raises:
            InvalidArgumentError: When the extra map cannot be read.
        """
        for mime_type, extensions in self.extra_map.items():
            kind, slash, subtype = mime_type.partition("/")
            if not (kind and slash and subtype):
                raise InvalidArgumentError(
                    f"extra_map is keyed by type/subtype MIME types, got {mime_type!r}"
                )
            if isinstance(extensions, str):
                raise InvalidArgumentError(
                    f"extra_map maps {mime_type!r} to a sequence of extensions, not one string"
                )
            for extension in extensions:
                if not extension or extension.startswith("."):
                    raise InvalidArgumentError(
                        f"extra_map gives {mime_type!r} the extension {extension!r}: an extension "
                        f"is not empty, and written without its leading dot"
                    )
