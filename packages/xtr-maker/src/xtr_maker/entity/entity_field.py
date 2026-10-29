"""EntityField: one column ``make:entity`` adds, read from ``--field`` or from the answers."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, ClassVar, Final, final

from xtr_maker.exception import InvalidArgumentError

from .field_type import FieldType
from .mapped_attribute import MappedAttribute
from .property_name import PropertyName

if TYPE_CHECKING:
    from xtr_maker.import_collector import ImportCollector

__all__ = ["EntityField"]

_PYTHON_TYPES: Final[dict[FieldType, tuple[str, str]]] = {
    FieldType.STRING: ("builtins", "str"),
    FieldType.TEXT: ("builtins", "str"),
    FieldType.INTEGER: ("builtins", "int"),
    FieldType.BIG_INTEGER: ("builtins", "int"),
    FieldType.SMALL_INTEGER: ("builtins", "int"),
    FieldType.BOOLEAN: ("builtins", "bool"),
    FieldType.FLOAT: ("builtins", "float"),
    FieldType.DECIMAL: ("decimal", "Decimal"),
    FieldType.DATE: ("datetime", "date"),
    FieldType.DATETIME: ("datetime", "datetime"),
    FieldType.TIME: ("datetime", "time"),
    FieldType.JSON: ("builtins", "dict[str, object]"),
    FieldType.UUID: ("uuid", "UUID"),
    FieldType.BINARY: ("builtins", "bytes"),
}
"""The type each kind holds in Python; an enum holds its own class."""

_COLUMN_TYPES: Final[dict[FieldType, tuple[str, str]]] = {
    FieldType.STRING: ("sqlalchemy", "String"),
    FieldType.TEXT: ("sqlalchemy", "Text"),
    FieldType.INTEGER: ("sqlalchemy", "Integer"),
    FieldType.BIG_INTEGER: ("sqlalchemy", "BigInteger"),
    FieldType.SMALL_INTEGER: ("sqlalchemy", "SmallInteger"),
    FieldType.BOOLEAN: ("sqlalchemy", "Boolean"),
    FieldType.FLOAT: ("sqlalchemy", "Float"),
    FieldType.DECIMAL: ("sqlalchemy", "Numeric"),
    FieldType.DATE: ("sqlalchemy", "Date"),
    FieldType.DATETIME: ("advanced_alchemy.types", "DateTimeUTC"),
    FieldType.TIME: ("sqlalchemy", "Time"),
    # SQLAlchemy's own JSON, which every dialect stores: the toolkit's JsonB cannot be put
    # in a table at all under SQLAlchemy 2.1, so an entity holding one would not import.
    FieldType.JSON: ("sqlalchemy", "JSON"),
    FieldType.UUID: ("advanced_alchemy.types", "GUID"),
    FieldType.ENUM: ("sqlalchemy", "Enum"),
    FieldType.BINARY: ("sqlalchemy", "LargeBinary"),
}
"""The column type each kind is stored in."""


@final
@dataclass(frozen=True, slots=True)
class EntityField:
    """A column: its attribute, its kind, whether it may be null, and its kind's settings.

    Attributes:
        name: The attribute, and the column.
        type: What it holds.
        nullable: Whether the column may be left empty.
        length: The longest ``string`` it holds.
        precision: How many digits a ``decimal`` has.
        scale: How many of them follow the decimal point.
        enum_class: The ``enum``'s class, dotted: ``app.entity.enum.Status``.

    Raises:
        InvalidArgumentError: When the name cannot name an attribute, a setting
            is out of range, or the enum class cannot be imported or is not an
            ``Enum``.
    """

    DEFAULT_LENGTH: ClassVar[int] = 255
    DEFAULT_PRECISION: ClassVar[int] = 10
    DEFAULT_SCALE: ClassVar[int] = 2

    name: str
    type: FieldType
    nullable: bool = False
    length: int = DEFAULT_LENGTH
    precision: int = DEFAULT_PRECISION
    scale: int = DEFAULT_SCALE
    enum_class: str | None = None

    def __post_init__(self) -> None:
        """Refuse a column no database, or no import, could hold."""
        _ = PropertyName.check(self.name)
        if self.length < 1:
            raise InvalidArgumentError(f"The length of {self.name!r} must be at least 1.")
        if self.precision < 1 or not 0 <= self.scale <= self.precision:
            raise InvalidArgumentError(
                f"The decimal {self.name!r} needs a precision of at least 1"
                " and a scale between 0 and its precision."
            )
        if self.type is FieldType.ENUM:
            _ = EntityField.enum_type(self.enum_class or "")

    @classmethod
    def parse(cls, typed: str) -> EntityField:
        """Read ``name:type[:settings][?]``, as ``--field`` takes it.

        ``title:string:120``, ``price:decimal:10:2``, ``published_at:datetime?``
        (``?``: nullable), ``status:enum:app.entity.enum.Status``. A name alone
        gets the kind its name suggests.

        Raises:
            InvalidArgumentError: When it does not read as a field.
        """
        text = typed.strip()
        nullable = text.endswith("?")
        name, *rest = (part.strip() for part in text.removesuffix("?").split(":"))
        kind = FieldType.guess(name) if not rest else _field_type(rest[0])
        settings = rest[1:]
        limits = {FieldType.STRING: 1, FieldType.DECIMAL: 2, FieldType.ENUM: 1}.get(kind, 0)
        if len(settings) > limits or (kind is FieldType.ENUM and not settings):
            raise InvalidArgumentError(
                f"{typed!r} does not read as a field: write name:type[:settings][?],"
                " such as title:string:120, price:decimal:10:2 or status:enum:app.Status."
            )
        if kind is FieldType.ENUM:
            return cls(name, kind, nullable, enum_class=settings[0])
        numbers = [_number(setting, typed) for setting in settings]
        if kind is FieldType.STRING and numbers:
            return cls(name, kind, nullable, length=numbers[0])
        if kind is FieldType.DECIMAL and numbers:
            scale = numbers[1] if len(numbers) > 1 else cls.DEFAULT_SCALE
            return cls(name, kind, nullable, precision=numbers[0], scale=scale)
        return cls(name, kind, nullable)

    @staticmethod
    def enum_type(dotted: str) -> type[Enum]:
        """Return the ``Enum`` subclass ``dotted`` names, importing its module.

        Raises:
            InvalidArgumentError: When it names no importable ``Enum`` subclass.
        """
        module, _, name = dotted.strip().rpartition(".")
        try:
            found: object = getattr(importlib.import_module(module), name) if module else None
        except (ImportError, AttributeError, ValueError):
            found = None
        if not isinstance(found, type) or not issubclass(found, Enum) or found.__name__ != name:
            raise InvalidArgumentError(
                f"{dotted!r} names no enum: write the dotted path of an Enum subclass"
                " its module defines, such as app.entity.enum.Status."
            )
        return found

    def attribute(self, imports: ImportCollector) -> MappedAttribute:
        """Return the attribute's line, adding what it uses to ``imports``."""
        python = self._python_type(imports)
        arguments = [self._column_type(imports)]
        if self.nullable:
            arguments.append("nullable=True")
        return MappedAttribute(
            self.name,
            f"{python} | None" if self.nullable else python,
            imports.add("sqlalchemy.orm", "mapped_column"),
            tuple(arguments),
            imports.add("sqlalchemy.orm", "Mapped"),
        )

    def _python_type(self, imports: ImportCollector) -> str:
        if self.type is FieldType.ENUM:
            enum = EntityField.enum_type(self.enum_class or "")
            return imports.add(enum.__module__, enum.__name__)
        module, name = _PYTHON_TYPES[self.type]
        return name if module == "builtins" else imports.add(module, name)

    def _column_type(self, imports: ImportCollector) -> str:
        column = imports.add(*_COLUMN_TYPES[self.type])
        match self.type:
            case FieldType.STRING:
                return f"{column}({self.length})"
            case FieldType.DECIMAL:
                return f"{column}({self.precision}, {self.scale})"
            case FieldType.DATETIME:
                return f"{column}(timezone=True)"
            case FieldType.ENUM:
                return f"{column}({self._python_type(imports)})"
            case _:
                return column


def _field_type(typed: str) -> FieldType:
    try:
        return FieldType(typed.strip().lower())
    except ValueError:
        raise InvalidArgumentError(
            f"There is no field type {typed!r}; the types are {', '.join(FieldType)}."
        ) from None


def _number(typed: str, field: str) -> int:
    try:
        return int(typed)
    except ValueError:
        raise InvalidArgumentError(f"{typed!r} in {field!r} is not a whole number.") from None
