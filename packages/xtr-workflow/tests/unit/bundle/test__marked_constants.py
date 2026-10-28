"""A class's annotated constants are read one annotation at a time, each with its markers.

An annotation naming what its module imports only for the type checker cannot
be evaluated at runtime: it is read as carrying no marker, unless its source
shows it carries some — then the class is refused. From 3.14 on, the same holds
of the annotations a module defers.
"""

from __future__ import annotations

import importlib
import sys
from typing import cast

import pytest

from tests.fixtures import declared_workflows as declared
from xtr_workflow.bundle._marked_constants import MarkedConstant, marked_constants
from xtr_workflow.decorator import Transition
from xtr_workflow.exception import LogicError

_DECLARED = declared.__name__
_DEFERRED = "tests.fixtures.deferred_declared_workflows"

deferred_annotations = pytest.mark.skipif(
    sys.version_info < (3, 14), reason="a module's annotations are deferred from 3.14 on"
)


def _deferred(name: str) -> type:
    """Return a class of the module whose annotations are deferred, imported from 3.14 on only."""
    return cast("type", vars(importlib.import_module(_DEFERRED))[name])


def test_the_class_own_constants_come_before_those_it_inherits() -> None:
    constants = marked_constants(declared.InheritedTransitionsWorkflow)

    assert [constant.label for constant in constants] == [
        f"{_DECLARED}.InheritedTransitionsWorkflow.BACK",
        f"{_DECLARED}.TransitionsBase.GO",
    ]


def test_an_annotation_only_the_type_checker_can_read_carries_no_marker() -> None:
    assert marked_constants(declared.TaskQueueWorkflow) == [
        MarkedConstant("_current", f"{_DECLARED}.TaskQueueWorkflow._current", ()),
        MarkedConstant(
            "QUEUE",
            f"{_DECLARED}.TaskQueueWorkflow.QUEUE",
            (Transition(froms="new", tos="queued"),),
        ),
    ]


@deferred_annotations
def test_a_deferred_annotation_only_the_type_checker_can_read_carries_no_marker() -> None:
    current, _ = marked_constants(_deferred("DeferredTaskQueueWorkflow"))

    assert current == MarkedConstant(
        "_current", f"{_DEFERRED}.DeferredTaskQueueWorkflow._current", ()
    )


@deferred_annotations
def test_beside_it_a_deferred_marker_is_read_as_evaluated_even_holding_a_lambda() -> None:
    _, queue = marked_constants(_deferred("DeferredTaskQueueWorkflow"))

    (marker,) = queue.markers
    assert isinstance(marker, Transition)
    assert (marker.froms, marker.tos, callable(marker.guard)) == ("new", "queued", True)


@deferred_annotations
def test_a_deferred_marker_naming_what_only_the_type_checker_imports_is_refused() -> None:
    with pytest.raises(LogicError) as raised:
        _ = marked_constants(_deferred("DeferredTaskStepWorkflow"))

    assert str(raised.value) == (
        f'The annotation of "{_DEFERRED}.DeferredTaskStepWorkflow.GO" cannot be read at runtime '
        "(name 'TaskStep' is not defined); import what it names outside TYPE_CHECKING."
    )
