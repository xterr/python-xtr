"""FileManager: where the application lives on disk, and the only way makers write to it."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING, Final, final

from xtr_console import escape

from .exception import AppPackageNotFoundError, UnsafePathError

if TYPE_CHECKING:
    from xtr_console import ConsoleStyle

__all__ = ["FileManager"]

_INIT: Final = "__init__.py"


@final
class FileManager:
    """The project directory, the application package in it, and the files makers write there.

    The application package is found where the import system finds it — the
    very folder the kernel scans — whatever the project's layout. It is looked
    for when a maker first needs it, never when the manager is built, so a
    console whose package cannot be found still starts.

    Every path written is checked first: one outside the project directory or
    a symbolic link is refused, so a name typed at a prompt cannot reach
    anywhere else on disk. Each write says what it did — ``created``,
    ``updated`` or ``no change`` — with the path relative to the project.
    """

    __slots__ = ("_project_dir", "_root_package")

    def __init__(self, project_dir: Path, root_package: str) -> None:
        """Write inside ``project_dir``, into the package ``root_package``.

        Args:
            project_dir: The directory holding the application's ``pyproject.toml``.
            root_package: The application package, dotted.
        """
        self._project_dir = project_dir.resolve()
        self._root_package = root_package

    @property
    def project_dir(self) -> Path:
        """The project directory, resolved."""
        return self._project_dir

    @property
    def root_package(self) -> str:
        """The application package, dotted."""
        return self._root_package

    @property
    def package_dir(self) -> Path:
        """The application package's directory.

        Raises:
            AppPackageNotFoundError: When the import system finds no package
                of that name.
        """
        try:
            found = importlib.util.find_spec(self._root_package)
        # A missing parent package raises ImportError; a module whose
        # ``__spec__`` is None raises ValueError: neither is a package to write into.
        except (ImportError, ValueError):
            found = None
        locations = found.submodule_search_locations if found is not None else None
        location = next(iter(locations or ()), None)
        if location is None:
            raise AppPackageNotFoundError(self._root_package, str(self._project_dir))
        return Path(location).resolve()

    def absolute(self, path: Path | str) -> Path:
        """Return ``path`` — relative to the project directory, or absolute — as an absolute path.

        Raises:
            UnsafePathError: When ``path`` lies outside the project directory.
        """
        resolved = (self._project_dir / path).resolve()
        if resolved != self._project_dir and self._project_dir not in resolved.parents:
            raise UnsafePathError(str(path), "it lies outside the project directory")
        return resolved

    def relative(self, path: Path | str) -> str:
        """Return ``path`` relative to the project directory, ``/``-separated."""
        return self.absolute(path).relative_to(self._project_dir).as_posix()

    def exists(self, path: Path | str) -> bool:
        """Report whether ``path`` exists, a broken symbolic link included."""
        target = self._project_dir / path
        return target.is_symlink() or target.exists()

    def read(self, path: Path | str) -> str:
        """Return the text of ``path``.

        Raises:
            UnsafePathError: When ``path`` lies outside the project directory.
        """
        return self.absolute(path).read_text(encoding="utf-8")

    def dump(self, path: Path | str, content: str, io: ConsoleStyle) -> None:
        """Write ``content`` to ``path``, creating its directories, and say what changed.

        Raises:
            UnsafePathError: When ``path`` is a symbolic link or lies outside
                the project directory.
        """
        if (self._project_dir / path).is_symlink():
            raise UnsafePathError(str(path), "it is a symbolic link")
        target = self.absolute(path)
        existed = target.is_file()
        if existed and target.read_text(encoding="utf-8") == content:
            self._report(io, "no change", target)
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = target.write_text(content, encoding="utf-8", newline="\n")
        self._report(io, "updated" if existed else "created", target)

    def ensure_package(self, directory: Path | str, io: ConsoleStyle) -> None:
        """Make ``directory`` and every folder above it, up to the application package, packages.

        A folder with no ``__init__.py`` gets one declaring nothing, so the
        module a maker writes there imports by its dotted name, and the
        container scanning the application finds it.

        Raises:
            AppPackageNotFoundError: When the application package cannot be found.
            UnsafePathError: When ``directory`` lies outside the application
                package.
        """
        package_dir = self.package_dir
        target = self.absolute(directory)
        if target != package_dir and package_dir not in target.parents:
            raise UnsafePathError(str(directory), "it lies outside the application package")
        relative = target.relative_to(package_dir)
        for depth in range(1, len(relative.parts) + 1):
            folder = package_dir.joinpath(*relative.parts[:depth])
            if not self.exists(folder / _INIT):
                dotted = ".".join((self._root_package, *relative.parts[:depth]))
                self.dump(folder / _INIT, _package_source(dotted), io)

    def _report(self, io: ConsoleStyle, action: str, target: Path) -> None:
        relative = target.relative_to(self._project_dir).as_posix()
        io.text(f" [green]{action}[/]: {escape(relative)}")


def _package_source(dotted: str) -> str:
    """Return the ``__init__.py`` of a package that only groups modules."""
    return (
        f'"""The ``{dotted}`` package."""\n\n'
        "from __future__ import annotations\n\n"
        "__all__: list[str] = []\n"
    )
