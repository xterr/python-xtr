"""Every context variable the libraries declare is classified, and per-unit state is detached.

A server may start a connection's task from a copy of an earlier connection's context, taken
mid-request. A variable holding one unit of work's state — its unit, its log unit, the
messages it holds back — must then be set back for the new connection, which is what
registering it as detached does. A variable added without a decision is how one connection
starts inside another's unit, so each one is classified here, with the reason, and the test
fails on any that is not, any entry naming a variable that no longer exists, and any per-unit
variable no bundle registers as detached.

The checker reads the sources as syntax only, so it runs without importing any package.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

_ROOT = Path(__file__).resolve().parents[1]

Kind = Literal["per-unit", "per-call", "process-wide", "inherited-marker"]

CLASSIFIED: dict[str, Kind] = {
    # A closed record of the computations under way, set and reset with its token in one call.
    "xtr_cache.adapter.contracts_mixin:_COMPUTING": "per-call",
    # The lock slots held by the call under way, set and reset with its token in one call.
    "xtr_cache.lock_registry:_HELD": "per-call",
    # The clock in force; a clock is meant to cross connections and units.
    "xtr_clock.clock:Clock._current": "process-wide",
    # The connection a served request belongs to.
    "xtr_dependency_injection.integration._resolvers:_SERVED": "per-unit",
    # The units of work open in this context.
    "xtr_dependency_injection.runtime._unit_scope:_current": "per-unit",
    # Whether a singleton is being built, set and reset around the build.
    "xtr_dependency_injection.runtime._unit_scope:_BUILDING_SINGLETON": "per-call",
    # The unit a bound call resolves from, set before every read and reset after the call.
    "xtr_dependency_injection.runtime.bind_callable:_bound_unit": "per-call",
    # A traced dispatcher's open trace, one per unit of work (debug only).
    "xtr_event_dispatcher.debug.traceable_event_dispatcher:TraceableEventDispatcher._unit": (
        "per-unit"
    ),
    # The logging context bound to the unit it was bound in.
    "xtr_logging.log_context:_CONTEXT": "per-unit",
    # The log unit open in this context.
    "xtr_logging.log_unit:_CURRENT": "per-unit",
    # Always None: only its token, kept on the log unit, is spent once to end it.
    "xtr_logging.log_unit:_BEGUN": "inherited-marker",
    # The logger's own re-entry depth, set and reset with its token in one call.
    "xtr_logging.logger:_depth": "per-call",
    # Set only in the fresh context a receive loop owns; what that loop starts must see it.
    "xtr_messenger._own_context:_RECEIVE_LOOP": "inherited-marker",
    # The messages held back until the current one was handled.
    "xtr_messenger.middleware.dispatch_after_current_bus_middleware:_held": "per-unit",
    # Whether the message under way is checked for a transaction left open.
    "xtr_orm.messenger.open_transaction_logger_middleware:_handling": "per-unit",
    # The transaction the message under way began.
    "xtr_orm.messenger.transaction_middleware:_begun": "per-unit",
    # Whether a unit's reads stick to the primary after one of its writes (declared upstream).
    "advanced_alchemy.routing:stick_to_primary_var": "per-unit",
    # Closed records of the decisions under way, each set and reset with its token in one call.
    "xtr_security_core.authorization.access_decision_manager:_decision_stack": "per-call",
    "xtr_security_core.authorization.authorization_checker:_token_stack": "per-call",
    "xtr_security_core.authorization.traceable_access_decision_manager:_current_logs": "per-call",
    # Set and reset with its token around one mapping declaration or one refusal collection.
    "xtr_serializer.mapping._declaration_sites:_DECLARING": "per-call",
    "xtr_serializer.mapping._deferred_refusals:_KEPT": "per-call",
    # The subjects whose locks the call under way holds, set and reset with its token.
    "xtr_workflow._subject_locks:_HELD": "per-call",
}

_DECLARED_NAMES = ("DETACHED_VARIABLE", "detached_variable")


def _sources(root: Path) -> Iterator[tuple[str, ast.Module]]:
    """Yield every library module under ``root``'s packages, by its dotted name."""
    for path in sorted(root.glob("packages/*/src/**/*.py")):
        source = path.parent.parts.index("src") if "src" in path.parent.parts else -1
        parts = path.with_suffix("").parts[source + 1 :]
        name = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        yield name, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _is_context_var(node: ast.expr | None) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (isinstance(func, ast.Name) and func.id == "ContextVar") or (
        isinstance(func, ast.Attribute) and func.attr == "ContextVar"
    )


def _assignments(tree: ast.Module) -> Iterator[tuple[str | None, ast.expr, ast.expr | None]]:
    """Yield ``(enclosing class, target, value)`` for every assignment in ``tree``."""

    def walk(
        node: ast.AST, owner: str | None
    ) -> Iterator[tuple[str | None, ast.expr, ast.expr | None]]:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                yield from walk(child, child.name)
                continue
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    yield owner, target, child.value
            elif isinstance(child, ast.AnnAssign):
                yield owner, child.target, child.value
            yield from walk(child, owner)

    return walk(tree, None)


def _key(module: str, owner: str | None, target: ast.expr) -> str | None:
    """Name the variable ``target`` binds: ``module:name``, ``module:Class.name``."""
    if isinstance(target, ast.Name):
        return f"{module}:{target.id}" if owner is None else f"{module}:{owner}.{target.id}"
    if (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "self"
    ):
        return None if owner is None else f"{module}:{owner}.{target.attr}"
    return None


def _imports(tree: ast.Module) -> dict[str, str]:
    """Map each name ``tree`` imports to what it is: ``module`` or ``module:name``."""
    names: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            for alias in node.names:
                names[alias.asname or alias.name] = f"{node.module}:{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names[alias.asname or alias.name.split(".")[0]] = alias.name
    return names


_INSTANCE = "an instance's detached_variable"
"""Where a per-instance declaration is said to live: only one class declares one."""


def _declarations(module: str, tree: ast.Module, imported: Mapping[str, str]) -> dict[str, str]:
    """Map where each ``DETACHED_VARIABLE`` of ``tree`` lives to the variable it names."""
    declared: dict[str, str] = {}
    for owner, target, value in _assignments(tree):
        name = target.id if isinstance(target, ast.Name) else getattr(target, "attr", None)
        if name not in _DECLARED_NAMES or not isinstance(value, ast.Tuple) or not value.elts:
            continue
        first = value.elts[0]
        where = _INSTANCE if name == "detached_variable" else module
        if isinstance(first, ast.Name):
            declared[where] = imported.get(first.id, f"{module}:{first.id}")
        elif isinstance(first, ast.Attribute) and owner is not None:
            declared[where] = f"{module}:{owner}.{first.attr}"
    return declared


def _registrations(module: str, tree: ast.Module, imported: Mapping[str, str]) -> Iterator[str]:
    """Yield what each ``register_detached_variable`` call of ``tree`` registers.

    A variable it names, or where the declaration it star-unpacks lives.
    """
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "register_detached_variable"
            and node.args
        ):
            continue
        argument = node.args[0]
        if isinstance(argument, ast.Name):
            yield imported.get(argument.id, f"{module}:{argument.id}")
        elif isinstance(argument, ast.Starred) and isinstance(argument.value, ast.Attribute):
            held = argument.value
            if held.attr == "detached_variable":
                yield _INSTANCE
            elif held.attr == "DETACHED_VARIABLE" and isinstance(held.value, ast.Name):
                yield imported.get(held.value.id, held.value.id).replace(":", ".")


def collect(root: Path) -> tuple[set[str], set[str]]:
    """Return every context variable the packages under ``root`` declare, and those detached.

    A variable counts as detached when a ``register_detached_variable`` call names it, or
    star-unpacks the ``DETACHED_VARIABLE`` of the module declaring it (or an instance's
    ``detached_variable``). A detached variable declared upstream counts as found.
    """
    found: set[str] = set()
    declared: dict[str, str] = {}
    registered: set[str] = set()
    for module, tree in _sources(root):
        imported = _imports(tree)
        found.update(
            key
            for owner, target, value in _assignments(tree)
            if _is_context_var(value) and (key := _key(module, owner, target)) is not None
        )
        declared.update(_declarations(module, tree, imported))
        registered.update(_registrations(module, tree, imported))
    detached = {variable for variable in registered if ":" in variable}
    detached.update(variable for where, variable in declared.items() if where in registered)
    return found | detached, detached


def problems(found: set[str], detached: set[str], classified: Mapping[str, Kind]) -> list[str]:
    """Say what is wrong with ``classified`` against what the sources declare."""
    issues = [f"unclassified: {name}" for name in sorted(found - set(classified))]
    issues += [f"stale: {name}" for name in sorted(set(classified) - found)]
    issues += [
        f"per-unit but not detached: {name}"
        for name, kind in sorted(classified.items())
        if kind == "per-unit" and name in found and name not in detached
    ]
    issues += [
        f"detached but not per-unit: {name}"
        for name in sorted(detached)
        if name in classified and classified[name] != "per-unit"
    ]
    return issues


def test_every_context_variable_is_classified_and_per_unit_state_is_detached() -> None:
    found, detached = collect(_ROOT)

    assert problems(found, detached, CLASSIFIED) == []


def _tree(root: Path, module: str, source: str) -> None:
    path = root / "packages" / "xtr-scratch" / "src" / Path(*module.split(".")).with_suffix(".py")
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(source, encoding="utf-8")


_DECLARING_STATE = (
    "from contextvars import ContextVar\n"
    '_unit = ContextVar("u", default=None)\n'
    "DETACHED_VARIABLE = (_unit, None)\n"
)


def test_an_unclassified_context_variable_fails(tmp_path: Path) -> None:
    _tree(
        tmp_path,
        "xtr_scratch.state",
        'from contextvars import ContextVar\nx: ContextVar[int] = ContextVar("x")\n',
    )

    found, detached = collect(tmp_path)

    assert problems(found, detached, {}) == ["unclassified: xtr_scratch.state:x"]


def test_a_per_unit_variable_no_bundle_registers_fails(tmp_path: Path) -> None:
    _tree(tmp_path, "xtr_scratch.state", _DECLARING_STATE)

    found, detached = collect(tmp_path)

    assert problems(found, detached, {"xtr_scratch.state:_unit": "per-unit"}) == [
        "per-unit but not detached: xtr_scratch.state:_unit"
    ]


def test_a_registered_declaration_makes_its_variable_detached(tmp_path: Path) -> None:
    _tree(tmp_path, "xtr_scratch.state", _DECLARING_STATE)
    _tree(
        tmp_path,
        "xtr_scratch.bundle",
        "from xtr_scratch import state\nregister_detached_variable(*state.DETACHED_VARIABLE)\n",
    )

    found, detached = collect(tmp_path)

    assert problems(found, detached, {"xtr_scratch.state:_unit": "per-unit"}) == []


def test_a_stale_entry_fails(tmp_path: Path) -> None:
    _tree(tmp_path, "xtr_scratch.state", "X = 1\n")

    found, detached = collect(tmp_path)

    assert problems(found, detached, {"xtr_scratch.state:gone": "per-call"}) == [
        "stale: xtr_scratch.state:gone"
    ]
