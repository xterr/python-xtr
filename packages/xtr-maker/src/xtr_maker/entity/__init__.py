"""What ``make:entity`` is made of: fields, relations, and the editor adding them to a class.

* :class:`EntityField` and :class:`EntityRelation` — a column and a relation,
  read from ``--field`` / ``--relation`` or built from answers.
* :class:`EntitySourceEditor` — an entity module, attributes and imports added
  to it, everything else kept byte for byte.
* :class:`RelationWriter` — a relation as the keys, ``relationship`` attributes
  and association table each side needs.
* :class:`EntityWorkspace` — every entity one run touches, written together.
"""

from __future__ import annotations

from .entity_field import EntityField
from .entity_interviewer import EntityInterviewer
from .entity_relation import EntityRelation
from .entity_source_editor import EntitySourceEditor
from .entity_workspace import EntityWorkspace
from .field_type import FieldType
from .id_type import IdType
from .import_merger import ImportMerger
from .mapped_attribute import MappedAttribute
from .needed_import import NeededImport
from .property_name import PropertyName
from .relation_kind import RelationKind
from .relation_writer import RelationWriter

__all__ = [
    "EntityField",
    "EntityInterviewer",
    "EntityRelation",
    "EntitySourceEditor",
    "EntityWorkspace",
    "FieldType",
    "IdType",
    "ImportMerger",
    "MappedAttribute",
    "NeededImport",
    "PropertyName",
    "RelationKind",
    "RelationWriter",
]
