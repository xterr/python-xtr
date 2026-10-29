"""EntityWorkspace: the entity a ``make:entity`` run edits, and every other entity it touches."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_maker.class_name import ClassName
from xtr_maker.exception import InvalidArgumentError

from .entity_source_editor import EntitySourceEditor
from .relation_writer import RelationWriter

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_maker.file_manager import FileManager
    from xtr_maker.generator import Generator

    from .entity_field import EntityField
    from .entity_relation import EntityRelation

__all__ = ["EntityWorkspace"]


@final
class EntityWorkspace:
    """The entity being made or edited, the entities its relations reach, and their changes.

    Every entity is edited in memory, read from disk the first time a
    relation reaches it; :meth:`queue` hands the generator the ones that
    changed, so a run that is refused partway writes nothing.
    """

    __slots__ = ("_editors", "_entity", "_file_manager", "_generator", "_is_new", "_originals")

    def __init__(
        self,
        file_manager: FileManager,
        generator: Generator,
        entity: EntitySourceEditor,
        *,
        is_new: bool,
    ) -> None:
        """Edit ``entity``, reaching other entities through ``file_manager``.

        Args:
            file_manager: Where the other entities are read from.
            generator: What every changed file is queued with.
            entity: The entity the run adds to.
            is_new: Whether ``entity`` is not on disk yet.
        """
        self._file_manager = file_manager
        self._generator = generator
        self._entity = entity
        self._is_new = is_new
        self._editors: dict[str, EntitySourceEditor] = {entity.entity.module: entity}
        self._originals: dict[str, str] = {entity.entity.module: entity.source}

    @property
    def entity(self) -> EntitySourceEditor:
        """The entity the run adds to."""
        return self._entity

    @property
    def is_new(self) -> bool:
        """Whether the entity is written for the first time, rather than edited."""
        return self._is_new

    @property
    def changed(self) -> bool:
        """Whether there is anything to write."""
        return self._is_new or any(
            editor.source != self._originals[module] for module, editor in self._editors.items()
        )

    def taken(self, name: str) -> bool:
        """Report whether the entity already has a property ``name``."""
        return self._entity.has_attribute(name)

    def add_field(self, field: EntityField) -> None:
        """Add ``field`` to the entity.

        Raises:
            InvalidArgumentError: When the entity already has its name.
        """
        imports = self._entity.imports()
        self._entity.add_attribute(field.attribute(imports), imports)

    def add_relation(self, relation: EntityRelation) -> None:
        """Add ``relation`` to the entity, and its inverse to the entity it reaches.

        Raises:
            InvalidArgumentError: When the other entity does not exist, or a
                name the relation adds is taken.
            InvalidClassNameError: When the other entity's name cannot name a class.
            TargetExistsError: When the association table's module exists.
        """
        target = self._editor(relation.target)
        RelationWriter(self._generator).write(relation, self._entity, target)

    def queue(self) -> tuple[Path, ...]:
        """Queue every entity that changed — the new one always — and return their paths.

        Raises:
            TargetExistsError: When the new entity's module appeared meanwhile.
        """
        queued: list[Path] = []
        for module, editor in self._editors.items():
            is_new = self._is_new and editor is self._entity
            if is_new or editor.source != self._originals[module]:
                path = self._file_manager.package_dir / editor.entity.path
                queued.append(self._generator.dump_file(path, editor.source, replace=not is_new))
        return tuple(queued)

    def _editor(self, typed: str) -> EntitySourceEditor:
        """Return the editor of the entity ``typed`` names, reading it the first time.

        Raises:
            InvalidArgumentError: When no module holds that entity.
        """
        entity = ClassName.create(
            typed, root_package=self._entity.entity.root_package, kind="entity"
        )
        found = self._editors.get(entity.module)
        if found is not None:
            return found
        path = self._file_manager.package_dir / entity.path
        if not self._file_manager.exists(path):
            raise InvalidArgumentError(
                f"There is no entity {entity.short_name} in {self._file_manager.relative(path)};"
                f" make it first with make:entity {entity.short_name}."
            )
        source = self._file_manager.read(path)
        editor = EntitySourceEditor(source, entity)
        self._editors[entity.module] = editor
        self._originals[entity.module] = source
        return editor
