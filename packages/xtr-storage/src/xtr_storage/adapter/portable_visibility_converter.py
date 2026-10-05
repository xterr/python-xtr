"""The permission bits that mean public and private on any ordinary filesystem."""

from __future__ import annotations

from typing import final

from xtr_storage.visibility import Visibility

__all__ = ["PortableVisibilityConverter"]


@final
class PortableVisibilityConverter:
    """Four modes and a default, chosen to work the same wherever they land.

    The defaults are the ones an ordinary deployment wants: a public file is
    readable by everyone and writable by its owner, a private one is the owner's
    alone, and each directory adds the execute bit it needs to be entered.
    Directories default to private, because a write creates them without being
    asked and the safe answer to an unasked question is the narrower one.

    Every value is adjustable, since what "public" has to mean depends on who
    serves the files: a web server running as another user needs the group or
    world bits that a site handing nothing out would rather not grant.

    Reading a mode back is the inexact direction, and the rule is deliberately
    blunt: a mode reads as private when it is exactly the mode this converter
    writes for private, and as public otherwise. That keeps the two directions
    in agreement — set a visibility, read it back, get the same answer — while
    making no claim about a file this storage never wrote, which carries
    whatever umask the process that created it had. The only thing this
    converter can honestly say about such a file is that its bits are not the
    ones it locks a file with.
    """

    __slots__ = ("_default_directory_visibility", "_directory_modes", "_file_modes")

    _file_modes: dict[Visibility, int]
    _directory_modes: dict[Visibility, int]
    _default_directory_visibility: Visibility

    def __init__(
        self,
        *,
        file_public: int = 0o644,
        file_private: int = 0o600,
        directory_public: int = 0o755,
        directory_private: int = 0o700,
        default_for_directories: Visibility = Visibility.PRIVATE,
    ) -> None:
        """Record the four modes and which one an unasked-for directory gets.

        The modes are kept as two lookup tables rather than four fields so that
        translating a visibility is a total mapping: a visibility this converter
        was not built for fails loudly on the lookup instead of silently taking
        one of the two branches an ``if`` would offer.

        Args:
            file_public: The mode a file readable by everyone carries.
            file_private: The mode a file readable by its owner alone carries,
                and the only mode read back as private.
            directory_public: The mode a directory everyone may enter carries.
            directory_private: The mode a directory its owner alone may enter
                carries, and the only directory mode read back as private.
            default_for_directories: The visibility a directory gets when the
                call that created it named none.
        """
        self._file_modes = {Visibility.PUBLIC: file_public, Visibility.PRIVATE: file_private}
        self._directory_modes = {
            Visibility.PUBLIC: directory_public,
            Visibility.PRIVATE: directory_private,
        }
        self._default_directory_visibility = default_for_directories

    def for_file(self, visibility: Visibility) -> int:
        """Return the mode a file of this visibility carries."""
        return self._file_modes[visibility]

    def for_directory(self, visibility: Visibility) -> int:
        """Return the mode a directory of this visibility carries."""
        return self._directory_modes[visibility]

    def inverse_for_file(self, mode: int) -> Visibility:
        """Return private when ``mode`` is exactly the private file mode, else public."""
        return self._inverse(mode, self._file_modes[Visibility.PRIVATE])

    def inverse_for_directory(self, mode: int) -> Visibility:
        """Return private when ``mode`` is exactly the private directory mode, else public."""
        return self._inverse(mode, self._directory_modes[Visibility.PRIVATE])

    def default_for_directories(self) -> int:
        """Return the mode a directory nobody named a visibility for carries."""
        return self._directory_modes[self._default_directory_visibility]

    @staticmethod
    def _inverse(mode: int, private: int) -> Visibility:
        """Read one mode, private being the one exact match and public the rest."""
        return Visibility.PRIVATE if mode == private else Visibility.PUBLIC
