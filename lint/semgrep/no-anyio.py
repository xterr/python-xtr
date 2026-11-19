# ruff: noqa: D100, E402, ERA001, F401, I001, INP001, PLR0402 -- a semgrep test target, not a module
# Each import is a case for lint/semgrep/no-anyio.yml, annotated with what the rule must find.
# Run with `semgrep --test lint/semgrep`.
import asyncio
import importlib

# ruleid: no-anyio
import anyio

# ruleid: no-anyio
import anyio.to_thread

# ruleid: no-anyio
import anyio as backend

# ruleid: no-anyio
import anyio.lowlevel as lowlevel

# ruleid: no-anyio
from anyio import sleep

# ruleid: no-anyio
from anyio import Path, create_task_group

# ruleid: no-anyio
from anyio.lowlevel import checkpoint

# ruleid: no-anyio
importlib.import_module("anyio")

# ruleid: no-anyio
importlib.import_module("anyio.to_thread")

# ruleid: no-anyio
__import__("anyio")

# ok: no-anyio
import anyio_extras

# ok: no-anyio
importlib.import_module("anyiox")

# ok: no-anyio
from asyncio import timeout

# A third-party API that only takes an anyio object, agreed with a human first.
import anyio  # nosemgrep: no-anyio
