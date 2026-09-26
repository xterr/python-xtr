"""Where variables come from when the process environment lacks them: a secrets directory."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, final

from typing_extensions import override
from xtr_dependency_injection import Autowire, EnvVarLoaderInterface, as_service

__all__ = ["SecretsDirectoryLoader"]


@final
@as_service
class SecretsDirectoryLoader(EnvVarLoaderInterface):
    """One file per variable, the file named after it — the layout mounted secrets take.

    Implementing ``EnvVarLoaderInterface`` is all it takes: the kernel autoconfigures it.
    Loaders are asked, in registration order, only for a variable the environment does not
    set (or sets empty), and each loads once — until ``ServicesResetter.reset()``, so a
    worker picks up a rotated secret between messages. It is a service like any other: its
    constructor is injected.
    """

    def __init__(self, directory: Annotated[str, Autowire(param="shop.secrets_dir")]) -> None:
        """Read the files in ``directory``."""
        self._directory = Path(directory)

    @override
    def load_env_vars(self) -> Mapping[str, str]:
        if not self._directory.is_dir():
            return {}
        return {
            entry.name: entry.read_text(encoding="utf-8").strip()
            for entry in sorted(self._directory.iterdir())
            if entry.is_file() and not entry.name.startswith(".")
        }
