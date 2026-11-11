from __future__ import annotations

import subprocess
import sys

import xtr_ai


def test_every_public_name_is_importable() -> None:
    for name in xtr_ai.__all__:
        assert getattr(xtr_ai, name) is not None


def test_importing_the_library_imports_neither_the_bundle_nor_a_provider_sdk() -> None:
    probe = (
        "import sys, xtr_ai; "
        "loaded = [m for m in sys.modules if m.startswith(("
        "'xtr_ai.bundle', 'xtr_dependency_injection', 'openai', 'anthropic', 'sqlalchemy'"
        "))]; "
        "print(loaded)"
    )

    output = subprocess.run(
        [sys.executable, "-c", probe], check=True, capture_output=True, text=True
    ).stdout

    assert output.strip() == "[]"
