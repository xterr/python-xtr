"""Generator: the files one maker run writes, queued, then written together."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .exception import TargetExistsError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from xtr_console import ConsoleStyle

    from .class_name import ClassName
    from .file_manager import FileManager
    from .template_renderer import TemplateRenderer

__all__ = ["Generator"]


@final
class Generator:
    """Queues the files a maker run writes, and writes them once every one is known.

    A maker renders all its files before any is written: a name already
    taken, or a template that renders broken source, then stops the run with
    nothing on disk. A file that exists, or one already queued, is refused —
    makers add code, they never replace it.

    Every template receives ``final_classes``: whether a generated class is
    marked ``@final``. :meth:`generate_class` adds the class's ``class_name``
    and ``module``.
    """

    __slots__ = ("_file_manager", "_final_classes", "_generated", "_pending", "_template_renderer")

    def __init__(
        self,
        file_manager: FileManager,
        template_renderer: TemplateRenderer,
        *,
        final_classes: bool = True,
    ) -> None:
        """Write through ``file_manager`` what ``template_renderer`` renders.

        Args:
            file_manager: Where the files go, and how they are written.
            template_renderer: What turns a template into a file's content.
            final_classes: Whether generated classes are marked ``@final``.
        """
        self._file_manager = file_manager
        self._template_renderer = template_renderer
        self._final_classes = final_classes
        self._pending: dict[Path, str] = {}
        self._generated: list[Path] = []

    @property
    def generated_files(self) -> tuple[Path, ...]:
        """Every file queued by this generator, written or not, in the order queued."""
        return tuple(self._generated)

    @property
    def final_classes(self) -> bool:
        """Whether generated classes are marked ``@final``.

        A maker reads it to import ``final`` only for a template that uses it.
        """
        return self._final_classes

    def generate_class(
        self, class_name: ClassName, template: str, context: Mapping[str, object] | None = None
    ) -> Path:
        """Queue the module of ``class_name``, rendered from ``template``.

        Returns:
            The module's absolute path.

        Raises:
            TargetExistsError: When the module exists or is already queued.
            GeneratedSourceError: When the template renders source that does
                not parse.
        """
        target = self._file_manager.package_dir / class_name.path
        values = {
            "class_name": class_name.short_name,
            "module": class_name.module,
            **(context or {}),
        }
        return self.generate_file(target, template, values)

    def generate_file(
        self, path: Path | str, template: str, context: Mapping[str, object] | None = None
    ) -> Path:
        """Queue ``path`` (relative to the project directory, or absolute) from ``template``.

        Returns:
            The file's absolute path.

        Raises:
            TargetExistsError: When the file exists or is already queued.
            GeneratedSourceError: When the template renders source that does
                not parse.
        """
        target = self._free(path)
        values = {"final_classes": self._final_classes, **(context or {})}
        return self._queue(target, self._template_renderer.render(template, values))

    def dump_file(self, path: Path | str, contents: str) -> Path:
        """Queue ``path`` — relative to the project directory, or absolute — with ``contents``.

        Returns:
            The file's absolute path.

        Raises:
            TargetExistsError: When the file exists or is already queued.
        """
        return self._queue(self._free(path), contents)

    def has_pending_operations(self) -> bool:
        """Report whether a file is queued and not yet written."""
        return bool(self._pending)

    def write_changes(self, io: ConsoleStyle) -> None:
        """Write every queued file, in the order queued, and empty the queue.

        A module inside the application package gets the ``__init__.py``
        files it needs to import by its dotted name.
        """
        for target, contents in self._pending.items():
            if target.suffix == ".py" and self._file_manager.package_dir in target.parents:
                self._file_manager.ensure_package(target.parent, io)
            self._file_manager.dump(target, contents, io)
        self._pending.clear()

    def _free(self, path: Path | str) -> Path:
        """Return ``path`` as an absolute path no file holds and none is queued for."""
        target = self._file_manager.absolute(path)
        if target in self._pending or self._file_manager.exists(target):
            raise TargetExistsError(self._file_manager.relative(target))
        return target

    def _queue(self, target: Path, contents: str) -> Path:
        self._pending[target] = contents
        self._generated.append(target)
        return target
