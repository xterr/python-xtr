"""Configuration for :class:`~xtr_maker.bundle.maker_bundle.MakerBundle`."""

from __future__ import annotations

from dataclasses import dataclass

from xtr_maker.exception.invalid_argument_error import InvalidArgumentError

__all__ = ["MakerConfig"]


@dataclass(frozen=True, slots=True)
class MakerConfig:
    """Where the makers write, and how the classes they write are declared.

    Attributes:
        root_package: The dotted application package the makers write into.
            ``None`` takes the kernel's package, ``kernel.package``; set it
            only to write into another one.
        final_classes: Whether generated classes are marked ``@final``.

    Raises:
        InvalidArgumentError: When ``root_package`` is not a dotted Python
            identifier.
    """

    root_package: str | None = None
    final_classes: bool = True

    def __post_init__(self) -> None:
        """Refuse a package no import statement could name."""
        if self.root_package is not None and not all(
            part.isidentifier() for part in self.root_package.split(".")
        ):
            message = f"root_package {self.root_package!r} is not a dotted Python identifier"
            raise InvalidArgumentError(message)
