"""How one named storage is built: its adapter, its defaults, and its wrapping."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from xtr_dependency_injection import Reference

from xtr_storage.exception import InvalidArgumentError
from xtr_storage.visibility import Visibility

from .adapter_configs import AdapterEntry, LocalAdapterConfig

__all__ = ["StorageDefinition"]


@dataclass(frozen=True, slots=True)
class StorageDefinition:
    """One storage in full: which backend it is, and how it behaves in front of it.

    The adapter is the only thing a storage cannot do without, so it has a
    default — files under the project's ``var`` — and everything else layers on
    top of it. ``prefix`` roots the storage inside its backend, ``read_only``
    forbids every write, and the visibility and url fields become the standing
    options the storage was built with, the defaults each call is laid over.

    A ``public_url_generator`` or ``temporary_url_generator`` is a
    :class:`Reference` to a service the container provides, for a deployment that
    hands out addresses through a component of its own rather than the backend.

    Attributes:
        adapter: What the storage stores through.
        visibility: The default visibility a write gives a file.
        directory_visibility: The default visibility a write gives a directory.
        retain_visibility: Whether a copy or a move keeps what the source had.
        public_url: One prefix files are reachable from, or several to spread
            them over.
        public_url_generator: A service that builds lasting addresses.
        temporary_url_generator: A service that builds expiring addresses.
        read_only: Whether every write is refused.
        prefix: A path the storage is rooted at inside its backend.
        allow_relative_path_traversal: Whether ``..`` in a path may climb.
    """

    adapter: AdapterEntry = field(default_factory=LocalAdapterConfig)
    visibility: Visibility | str | None = None
    directory_visibility: Visibility | str | None = None
    retain_visibility: bool = True
    public_url: str | Sequence[str] | None = None
    public_url_generator: Reference | None = None
    temporary_url_generator: Reference | None = None
    read_only: bool = False
    prefix: str | None = None
    allow_relative_path_traversal: bool = True

    def __post_init__(self) -> None:
        """Refuse a visibility that names nothing, an empty prefix, or a bad url.

        Raises:
            InvalidArgumentError: When the prefix is empty, or a public url entry
                is not a non-empty string.
            InvalidVisibilityError: When a visibility string names no visibility.
        """
        if self.visibility is not None:
            _ = Visibility.parse(self.visibility)
        if self.directory_visibility is not None:
            _ = Visibility.parse(self.directory_visibility)
        if self.prefix is not None and self.prefix == "":
            raise InvalidArgumentError("a storage prefix must not be empty; leave it unset instead")
        self._validate_public_url()

    def _validate_public_url(self) -> None:
        """Refuse a public url that is not a non-empty string or list of them."""
        setting = self.public_url
        if setting is None or isinstance(setting, str):
            if setting == "":
                raise InvalidArgumentError("a public url must not be empty")
            return

        entries = list(setting)
        if not entries or any(not isinstance(entry, str) or entry == "" for entry in entries):  # pyright: ignore[reportUnnecessaryIsInstance] -- configs are written by hand; the annotation is not enforced
            raise InvalidArgumentError(
                "a public url must be a non-empty url or a non-empty list of urls",
            )
