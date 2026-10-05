"""Fakes and builders the unit tests share."""

from __future__ import annotations

from .command_harness import (
    CONFIG,
    DECLARED,
    MESSENGER,
    MESSENGER_MANIFEST,
    RENDERED,
    TARGET,
    TEMPLATE,
    ProcessRecorder,
    build_tester,
    install_recipes,
    messenger_project,
    record_processes,
    snapshot,
)
from .fake_recipe_source import FakeRecipeSource, recipe_content
from .project_builder import build_project

__all__ = [
    "CONFIG",
    "DECLARED",
    "MESSENGER",
    "MESSENGER_MANIFEST",
    "RENDERED",
    "TARGET",
    "TEMPLATE",
    "FakeRecipeSource",
    "ProcessRecorder",
    "build_project",
    "build_tester",
    "install_recipes",
    "messenger_project",
    "recipe_content",
    "record_processes",
    "snapshot",
]
