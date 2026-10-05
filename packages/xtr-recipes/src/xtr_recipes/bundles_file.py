"""BundlesFile: reading an application's ``bundles.py`` and writing it back."""

from __future__ import annotations

import ast
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, final

from .bundle_entry import BundleEntry
from .exception import BundlesNotEditableError

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping, Sequence

__all__ = ["BundlesFile"]

_BUNDLES = "BUNDLES"
_ALL = "__all__"
_FILE_NAME = "bundles.py"
_FUTURE = "__future__"
_DEFAULT_DOCSTRING = "The root bundles, each mapped to the environments it is active in."
_NOT_IMPORTED = "is not a class imported with `from <module> import <Class>`"


@final
@dataclass(frozen=True, slots=True)
class BundlesFile:
    """An application's bundle list, read as data and written back whole.

    The file is parsed with :mod:`ast` and never imported, so reading it costs
    nothing and cannot run application code. What is kept is what the generated
    form holds: the module docstring and the ordered entries. Per-entry
    comments are not, which is why the file is regenerated rather than patched
    — a shape this reader cannot account for raises
    :class:`~xtr_recipes.exception.BundlesNotEditableError` instead of being
    rewritten and losing something.

    Every change returns a new value, so the one on disk is only touched by
    :meth:`write`.

    Attributes:
        entries: The bundles in the order the file lists them.
        docstring: The module docstring as its source spells it, quotes and
            prefix included, so it is written back byte for byte; ``None``
            when the file has none and the default should be written.
        path: The file these entries were read from, when they were read from
            one; an error raised while rendering names it.
    """

    entries: tuple[BundleEntry, ...] = ()
    docstring: str | None = None
    path: Path | None = None

    @classmethod
    def read(cls, path: Path) -> BundlesFile:
        """Read ``path``, or report an empty list when it does not exist yet.

        Args:
            path: The ``bundles.py`` to read.

        Returns:
            The file as data; an empty list with no docstring when absent.

        Raises:
            BundlesNotEditableError: The file does not parse, or builds its
                mapping in a way this reader cannot account for.
        """
        if not path.is_file():
            return cls(path=path)
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as error:
            raise BundlesNotEditableError(path, f"it does not parse: {error.msg}", ()) from error
        _refuse_other_code(path, tree)
        return cls(
            entries=_read_entries(path, tree),
            docstring=_docstring_source(source, tree),
            path=path,
        )

    def with_entries(self, entries: Iterable[BundleEntry]) -> BundlesFile:
        """Return a copy listing exactly ``entries``, in the order given."""
        return replace(self, entries=tuple(entries))

    def adding(self, entries: Iterable[BundleEntry]) -> BundlesFile:
        """Return a copy with every target not already listed appended.

        A target already listed is left as it is, flags included: the
        application owner chose those environments.
        """
        listed = {entry.target for entry in self.entries}
        added = tuple(entry for entry in entries if entry.target not in listed)
        return replace(self, entries=self.entries + added)

    def removing(self, targets: Iterable[str]) -> BundlesFile:
        """Return a copy without the entries whose target is in ``targets``."""
        removed = set(targets)
        return replace(
            self,
            entries=tuple(entry for entry in self.entries if entry.target not in removed),
        )

    def render(self, first_party: Collection[str]) -> str:
        """Render the canonical file, ready for ``ruff check`` and ``ruff format``.

        Args:
            first_party: The application's own top-level package names; an
                entry whose module starts with one of them is imported in the
                second import block, as an import sorter would place it.

        Returns:
            The whole file, ending in a newline.

        Raises:
            BundlesNotEditableError: Two entries would import the same class
                name from different modules, which one mapping cannot spell.
        """
        third_party, own = self._import_blocks(first_party)
        blocks = [
            _docstring_block(self.docstring),
            f"from {_FUTURE} import annotations",
            *(block for block in (third_party, own) if block),
            f'__all__ = ["{_BUNDLES}"]',
            _mapping_block(self.entries),
        ]
        return "\n\n".join(blocks) + "\n"

    def write(self, path: Path, first_party: Collection[str]) -> bool:
        """Write the canonical file to ``path`` unless it already says this.

        Args:
            path: Where to write.
            first_party: As in :meth:`render`.

        Returns:
            Whether the file changed.

        Raises:
            BundlesNotEditableError: As in :meth:`render`.
        """
        rendered = self.render(first_party)
        if path.is_file() and path.read_text(encoding="utf-8") == rendered:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(rendered, encoding="utf-8")
        return True

    def _import_blocks(self, first_party: Collection[str]) -> tuple[str, str]:
        """Group the entries into the two import blocks, sorted by module."""
        modules: dict[str, list[str]] = {}
        origin: dict[str, str] = {}
        for entry in self.entries:
            known = origin.setdefault(entry.class_name, entry.module)
            if known != entry.module:
                raise BundlesNotEditableError(
                    self.path or Path(_FILE_NAME),
                    f"{entry.class_name} would be imported from both {known} and {entry.module}",
                    (f"{known}:{entry.class_name}", entry.target),
                )
            classes = modules.setdefault(entry.module, [])
            if entry.class_name not in classes:
                classes.append(entry.class_name)
        third_party: list[str] = []
        own: list[str] = []
        for module in sorted(modules):
            block = own if module.partition(".")[0] in first_party else third_party
            block.append(f"from {module} import {', '.join(sorted(modules[module]))}")
        return "\n".join(third_party), "\n".join(own)


def _read_entries(path: Path, tree: ast.Module) -> tuple[BundleEntry, ...]:
    """Read the entries of the one module-level ``BUNDLES`` mapping."""
    imported = _imported_names(tree)
    mapping = _bundles_mapping(path, tree)
    entries: list[BundleEntry] = []
    for key, value in zip(mapping.keys, mapping.values, strict=True):
        target = imported.get(key.id) if isinstance(key, ast.Name) else None
        if target is None:
            shown = "a `**` unpacking" if key is None else ast.unparse(key)
            raise BundlesNotEditableError(path, f"{_BUNDLES} key {shown} {_NOT_IMPORTED}", ())
        entries.append(BundleEntry(target=target, flags=_read_flags(path, value, target)))
    return tuple(entries)


def _docstring_source(source: str, tree: ast.Module) -> str | None:
    """Return the module docstring exactly as the file spells it, or ``None``."""
    if ast.get_docstring(tree, clean=False) is None:
        return None
    first = tree.body[0]
    return ast.get_source_segment(source, first)


def _refuse_other_code(path: Path, tree: ast.Module) -> None:
    """Refuse a statement the generated form would not write back.

    The file is regenerated from its entries, so anything else in it — a
    constant, a condition, a function — would be deleted without a word.
    """
    for index, node in enumerate(tree.body):
        if index == 0 and isinstance(node, ast.Expr) and ast.get_docstring(tree) is not None:
            continue
        if isinstance(node, ast.Import | ast.ImportFrom):
            continue
        if isinstance(node, ast.Assign | ast.AnnAssign) and _assigns(node, (_BUNDLES, _ALL)):
            continue
        raise BundlesNotEditableError(
            path,
            f"line {node.lineno} holds code the regenerated file would not keep",
            (),
        )


def _imported_names(tree: ast.Module) -> dict[str, str]:
    """Map every name an absolute ``from`` import binds to ``"module:Name"``."""
    names: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.level != 0:
            continue
        module = node.module
        if module is None or module == _FUTURE:
            continue
        for alias in node.names:
            if alias.name != "*":
                names[alias.asname or alias.name] = f"{module}:{alias.name}"
    return names


def _bundles_mapping(path: Path, tree: ast.Module) -> ast.Dict:
    """Return the dict literal the single module-level ``BUNDLES`` is given."""
    assigned = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign | ast.AnnAssign) and _assigns(node, (_BUNDLES,))
    ]
    if len(assigned) != 1:
        raise BundlesNotEditableError(
            path,
            f"it holds {len(assigned)} module-level {_BUNDLES} assignments, not one",
            (),
        )
    mapping = assigned[0]
    if not isinstance(mapping, ast.Dict):
        raise BundlesNotEditableError(path, f"{_BUNDLES} is not written as a dict literal", ())
    return mapping


def _assigns(node: ast.Assign | ast.AnnAssign, names: Collection[str]) -> bool:
    """Tell whether ``node`` assigns one of ``names``."""
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return any(isinstance(target, ast.Name) and target.id in names for target in targets)


def _read_flags(path: Path, value: ast.expr | None, target: str) -> Mapping[str, bool]:
    """Evaluate one entry's flags, refusing anything but names mapped to bools."""
    try:
        flags = ast.literal_eval(value) if value is not None else None
    except (ValueError, TypeError) as error:
        raise BundlesNotEditableError(
            path,
            f"the flags of {target} are not literal values",
            (),
        ) from error
    if not isinstance(flags, dict) or not all(
        isinstance(name, str) and isinstance(flag, bool) for name, flag in flags.items()
    ):
        raise BundlesNotEditableError(
            path,
            f"the flags of {target} are not environment names mapped to true or false",
            (),
        )
    return flags


def _docstring_block(docstring: str | None) -> str:
    """Render the module docstring as read, writing the default one when there is none."""
    return f'"""{_DEFAULT_DOCSTRING}"""' if docstring is None else docstring


def _mapping_block(entries: Sequence[BundleEntry]) -> str:
    """Render the ``BUNDLES`` assignment, one line per entry."""
    if not entries:
        return f"{_BUNDLES} = {{}}"
    lines = "".join(f"    {entry.class_name}: {_flags_source(entry.flags)},\n" for entry in entries)
    return f"{_BUNDLES} = {{\n{lines}}}"


def _flags_source(flags: Mapping[str, bool]) -> str:
    """Render one entry's flags as the source a formatter would leave alone."""
    return "{" + ", ".join(f'"{name}": {flag}' for name, flag in flags.items()) + "}"
