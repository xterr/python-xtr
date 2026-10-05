"""Translating a visibility into the permission bits a filesystem understands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_storage.visibility import Visibility

__all__ = ["VisibilityConverterInterface"]


@runtime_checkable
class VisibilityConverterInterface(Protocol):
    """Turns a visibility into permission bits, and permission bits back into one.

    A filesystem has no notion of public and private — it has a number, and the
    number a deployment calls public is its own decision: one site serves files
    through a web server running as another user and needs the group bit, another
    hands nothing out and wants the narrowest mode that still works. A converter
    is where that decision lives, so the adapter above it only ever speaks of
    visibility.

    Files and directories are asked separately because a directory needs its
    execute bit to be entered at all, so the mode that makes a file readable
    makes a directory useless.

    The inverse direction is a guess and is meant to be: a filesystem holds no
    record of what a mode was *intended* to mean, and a file written by another
    process carries whatever that process's umask left. An implementation says
    which modes it recognises as private and reads the rest as public, so that
    setting a visibility and reading it back agrees with itself.
    """

    def for_file(self, visibility: Visibility) -> int:
        """Return the permission bits a file of this visibility should carry.

        Args:
            visibility: Who should be able to read the file.

        Returns:
            The mode, as the number a permission change takes.
        """
        ...

    def for_directory(self, visibility: Visibility) -> int:
        """Return the permission bits a directory of this visibility should carry.

        Args:
            visibility: Who should be able to list and enter the directory.

        Returns:
            The mode, as the number a permission change takes.
        """
        ...

    def inverse_for_file(self, mode: int) -> Visibility:
        """Return the visibility a file's permission bits stand for.

        Args:
            mode: The file's permission bits, with any type bits already removed.

        Returns:
            The visibility those bits are read as.
        """
        ...

    def inverse_for_directory(self, mode: int) -> Visibility:
        """Return the visibility a directory's permission bits stand for.

        Args:
            mode: The directory's permission bits, with any type bits already
                removed.

        Returns:
            The visibility those bits are read as.
        """
        ...

    def default_for_directories(self) -> int:
        """Return the permission bits a directory nobody asked about should carry.

        A write creates the directories on the way to its file, and the call that
        asked for it usually says nothing about them. This is the answer for that
        case, so those directories get a mode the deployment chose rather than
        whatever the process umask happens to be.
        """
        ...
