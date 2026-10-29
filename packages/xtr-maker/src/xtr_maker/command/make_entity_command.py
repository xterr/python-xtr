"""``make:entity``: a new entity and its repository, or fields and relations added to one."""

from __future__ import annotations

from typing import Annotated, Final, final

from xtr_console import ConsoleStyle, ExitCode, Option, as_command, escape
from xtr_dependency_injection import (  # noqa: TC002 — the console reads annotations at runtime.
    Injected,
)

from xtr_maker.class_name import ClassName
from xtr_maker.entity import (
    EntityField,
    EntityInterviewer,
    EntityRelation,
    EntitySourceEditor,
    EntityWorkspace,
    IdType,
)
from xtr_maker.exception import InvalidArgumentError, InvalidClassNameError, TargetExistsError
from xtr_maker.file_manager import (  # noqa: TC001 — the container reads annotations at runtime.
    FileManager,
)
from xtr_maker.generator import Generator  # noqa: TC001 — the console reads annotations at runtime.
from xtr_maker.import_collector import ImportCollector
from xtr_maker.name_converter import NameConverter
from xtr_maker.template_renderer import (  # noqa: TC001 — the container reads annotations at runtime.
    TemplateRenderer,
)

__all__ = ["MakeEntityCommand"]

_ATTEMPTS: Final = 3
"""How many times the name is asked: an input that has ended answers empty every time."""

_ENTITY_TEMPLATE: Final = "entity/entity.py.jinja"
_REPOSITORY_TEMPLATE: Final = "entity/repository.py.jinja"

_REFUSED: Final = (InvalidArgumentError, InvalidClassNameError)


@final
@as_command(
    "make:entity",
    description="Write an entity and its repository, or add fields and relations to an entity.",
)
class MakeEntityCommand:
    """Writes ``entity/<name>.py`` and ``repository/<name>_repository.py``, or edits the entity.

    A new entity derives from the base ``--id`` and ``--no-audit`` pick —
    ``UUIDAuditBase`` by default — and is stored in the plural of its name;
    its repository comes with a factory scoped like the session it uses.
    An entity that exists gets the fields and relations added to its class,
    every other line kept as it was, and no repository.

    Fields and relations come from ``--field`` and ``--relation``, or, with
    neither and a terminal, from questions asked until a name is left empty.
    Nothing is written when anything is refused; the migration is left to
    ``make:migration``.
    """

    __slots__ = ("_file_manager", "_template_renderer")

    def __init__(self, file_manager: FileManager, template_renderer: TemplateRenderer) -> None:
        """Write into the package ``file_manager`` holds, rendering new entities first.

        Args:
            file_manager: The application package the entities live in.
            template_renderer: What renders a new entity before fields are added to it.
        """
        self._file_manager = file_manager
        self._template_renderer = template_renderer

    async def __call__(  # noqa: PLR0913 — the console's parameters: one per argument and option.
        self,
        io: ConsoleStyle,
        generator: Injected[Generator],
        name: str | None = None,
        *,
        fields: Annotated[
            list[str] | None, Option(name="--field", help="name:type[:settings][?], repeatable.")
        ] = None,
        relations: Annotated[
            list[str] | None,
            Option(name="--relation", help="name:kind:Target[?][,inverse=name|none], repeatable."),
        ] = None,
        id_type: Annotated[str | None, Option(name="--id", help="uuid, uuid7 or bigint.")] = None,
        no_audit: bool = False,
    ) -> int:
        """Write a new entity and its repository, or add to the entity that exists.

        Args:
            io: Where the command writes, and asks.
            generator: What writes the files, all or none.
            name: The entity's class name, such as ``Book``; ``catalog.Book``
                puts it under ``entity/catalog/``.
            fields: Columns to add, such as ``title:string:120``.
            relations: Relations to add, such as ``author:many_to_one:Author``.
            id_type: A new entity's key: ``uuid`` (the default), ``uuid7`` or ``bigint``.
            no_audit: Leave ``created_at`` and ``updated_at`` out of a new entity.
        """
        try:
            entity = self._entity_name(io, name)
            workspace = self._workspace(entity, generator, id_type, audit=not no_audit)
            if fields or relations or not io.interactive:
                for typed in fields or ():
                    workspace.add_field(EntityField.parse(typed))
                for typed in relations or ():
                    workspace.add_relation(EntityRelation.parse(typed, entity.short_name))
            else:
                _interview(io, workspace)
        except _REFUSED as error:
            io.error(escape(str(error)))
            return ExitCode.INVALID
        except TargetExistsError as error:
            io.error(escape(str(error)))
            return ExitCode.FAILURE
        if not workspace.changed:
            io.note(f"Nothing was added to {entity.short_name}.")
            return ExitCode.SUCCESS
        try:
            _ = workspace.queue()
            repository = self._repository(entity, generator) if workspace.is_new else None
        except TargetExistsError as error:
            io.error(escape(str(error)))
            return ExitCode.FAILURE
        generator.write_changes(io)
        written = (
            entity.short_name if repository is None else f"{entity.short_name} and {repository}"
        )
        io.success(f"{'Updated' if repository is None else 'Wrote'} {written}.")
        io.text("Next:")
        io.text("  - Run make:migration to write the revision the change needs.")
        io.text("  - Then run orm:migrations:migrate -n to apply it.")
        return ExitCode.SUCCESS

    def _entity_name(self, io: ConsoleStyle, typed: str | None) -> ClassName:
        """Return the entity ``typed`` names, asking for it when it was left out.

        Raises:
            InvalidArgumentError: When no name was given and nothing may be asked.
            InvalidClassNameError: When the name cannot name a class, or no
                answer could after the last attempt.
        """
        if typed is not None:
            return self._entity_class(typed)
        if not io.interactive:
            raise InvalidArgumentError(
                "Name the entity to write: make:entity <name>, such as make:entity Book."
            )
        question = "The entity's class name (such as [cyan]Book[/])"
        for _ in range(_ATTEMPTS - 1):
            try:
                return self._entity_class(io.ask(question))
            except InvalidClassNameError as error:
                io.error(escape(str(error)))
        return self._entity_class(io.ask(question))

    def _entity_class(self, typed: str) -> ClassName:
        return ClassName.create(typed, root_package=self._file_manager.root_package, kind="entity")

    def _workspace(
        self, entity: ClassName, generator: Generator, id_type: str | None, *, audit: bool
    ) -> EntityWorkspace:
        """Return the workspace editing ``entity``: read from disk, or rendered new.

        Raises:
            InvalidArgumentError: When ``--id`` names no key, or ``--id`` or
                ``--no-audit`` is given for an entity that exists.
        """
        path = self._file_manager.package_dir / entity.path
        if self._file_manager.exists(path):
            if id_type is not None or not audit:
                raise InvalidArgumentError(
                    f"{entity.short_name} exists: --id and --no-audit only choose a new"
                    " entity's base."
                )
            editor = EntitySourceEditor(self._file_manager.read(path), entity)
            return EntityWorkspace(self._file_manager, generator, editor, is_new=False)
        source = self._template_renderer.render(
            _ENTITY_TEMPLATE, _entity_context(entity, _id_type(id_type), generator, audit=audit)
        )
        editor = EntitySourceEditor(source, entity)
        return EntityWorkspace(self._file_manager, generator, editor, is_new=True)

    @staticmethod
    def _repository(entity: ClassName, generator: Generator) -> str:
        """Queue the entity's repository, and return its class name."""
        repository = ClassName.create(
            ".".join((*entity.package[1:], entity.short_name)),
            root_package=entity.root_package,
            kind="repository",
            suffix="Repository",
        )
        imports = ImportCollector(entity.root_package)
        if generator.final_classes:
            _ = imports.add("typing", "final")
        context = {
            "repository_base": imports.add(
                "advanced_alchemy.repository", "SQLAlchemyAsyncRepository"
            ),
            "session": imports.add("sqlalchemy.ext.asyncio", "AsyncSession"),
            "as_service": imports.add("xtr_dependency_injection", "as_service"),
            "entity_class": imports.add(entity.module, entity.short_name),
            "factory": repository.snake_name,
        }
        _ = generator.generate_class(
            repository, _REPOSITORY_TEMPLATE, {**context, "imports": imports.render()}
        )
        return repository.short_name


def _interview(io: ConsoleStyle, workspace: EntityWorkspace) -> None:
    """Ask for properties until a name is left empty, reporting each refused one."""
    interviewer = EntityInterviewer(io, workspace.entity.entity.short_name)
    while True:
        try:
            member = interviewer.next_member(workspace.taken)
            match member:
                case None:
                    return
                case EntityField():
                    workspace.add_field(member)
                case EntityRelation():
                    workspace.add_relation(member)
        except (*_REFUSED, TargetExistsError) as error:
            io.error(escape(str(error)))


def _id_type(typed: str | None) -> IdType:
    if typed is None:
        return IdType.UUID
    try:
        return IdType(typed.strip().lower())
    except ValueError:
        raise InvalidArgumentError(
            f"There is no key type {typed!r}; the types are {', '.join(IdType)}."
        ) from None


def _entity_context(
    entity: ClassName, id_type: IdType, generator: Generator, *, audit: bool
) -> dict[str, object]:
    """Return what the entity template reads: its imports, base, table and readable name."""
    imports = ImportCollector(entity.root_package)
    if generator.final_classes:
        _ = imports.add("typing", "final")
    base = imports.add("advanced_alchemy.base", id_type.base(audit=audit))
    return {
        "imports": imports.render(),
        "base": base,
        "provided": ("``id``, ``created_at`` and ``updated_at`` come" if audit else "``id`` comes"),
        "table": NameConverter.as_table_name(entity.short_name),
        "readable_name": " ".join(word.lower() for word in NameConverter.words(entity.short_name)),
        "final_classes": generator.final_classes,
        "class_name": entity.short_name,
        "module": entity.module,
    }
