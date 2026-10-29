"""An application written under a test's temporary directory, run through its own console.

Every maker's integration test follows the same steps: write a small
application, boot its kernel with the maker bundle and the library's bundle,
run the maker through the console with scripted answers, then import what it
wrote and boot again to see the kernel discover it::

    with TemporaryApp(tmp_path, bundles=(MessengerBundle,)) as app:
        code, output = await app.run(["make:message"], inputs=["place order", ""])
        module = app.import_generated("message.place_order")
        async with await app.boot() as booted:
            ...
"""

from __future__ import annotations

import importlib
import os
import sys
from typing import TYPE_CHECKING, final
from uuid import uuid4

from xtr_console import SHELL_VERBOSITY, Application, ApplicationTester
from xtr_dependency_injection import Kernel

from xtr_maker.bundle import MakerBundle

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path
    from types import ModuleType, TracebackType
    from typing import Self

    from xtr_dependency_injection import BootedKernel
    from xtr_dependency_injection.bundle.bundle import AnyBundle

__all__ = ["TemporaryApp"]

_WIDTH = 200
"""Wide enough that no line the makers print wraps."""


@final
class TemporaryApp:
    """A uniquely named application package under ``src/``, importable while the block runs.

    Its kernel activates the maker bundle — the console comes with it — plus
    ``bundles``, in every environment. ``modules`` are written into the package
    first, keyed by their dotted name inside it (``"config.packages.messenger"``),
    their packages created; the kernel scans the whole package, so an
    ``@configure`` among them applies. The kernel reads its environment
    variables from ``environ`` alone, never the process's.

    Leaving the block takes the project off ``sys.path`` and forgets every
    module of the package, so the next test imports its own.
    """

    def __init__(
        self,
        root: Path,
        *,
        bundles: Sequence[type[AnyBundle]] = (),
        modules: Mapping[str, str] | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        """Write the application into ``root``.

        Args:
            root: The project directory, typically the test's ``tmp_path``.
            bundles: The bundles to activate beside the maker bundle.
            modules: Source of extra modules, by dotted name inside the package.
            environ: The environment variables the kernel reads.
        """
        self.project_dir = root.resolve()
        self.package = f"maker_app_{uuid4().hex}"
        self.package_dir = self.project_dir / "src" / self.package
        self.environ = dict(environ or {})
        self._bundles: dict[type[AnyBundle], Mapping[str, bool]] = {
            bundle: {"all": True} for bundle in (MakerBundle, *bundles)
        }
        self._verbosity = os.environ.get(SHELL_VERBOSITY)
        _ = (self.project_dir / "pyproject.toml").write_text(
            f'[project]\nname = "{self.package}"\n', encoding="utf-8"
        )
        self._write_package(self.package_dir)
        for dotted, source in (modules or {}).items():
            *packages, module = dotted.split(".")
            directory = self.package_dir.joinpath(*packages)
            for depth in range(1, len(packages) + 1):
                self._write_package(self.package_dir.joinpath(*packages[:depth]))
            _ = (directory / f"{module}.py").write_text(source, encoding="utf-8")

    def __enter__(self) -> Self:
        """Put the project's ``src/`` first on ``sys.path``."""
        sys.path.insert(0, str(self.project_dir / "src"))
        importlib.invalidate_caches()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Take the project off ``sys.path``, forget its modules, and restore the verbosity."""
        sys.path.remove(str(self.project_dir / "src"))
        prefix = f"{self.package}."
        owned = [name for name in sys.modules if name == self.package or name.startswith(prefix)]
        for name in owned:
            del sys.modules[name]
        if self._verbosity is None:
            _ = os.environ.pop(SHELL_VERBOSITY, None)
        else:
            os.environ[SHELL_VERBOSITY] = self._verbosity

    def kernel(self) -> Kernel:
        """Return the application's kernel, in ``test``, reading ``environ`` only."""
        return Kernel(self.package, env="test", bundles=self._bundles, environ=self.environ)

    async def boot(self) -> BootedKernel:
        """Boot the kernel over what the package holds now, written files included."""
        importlib.invalidate_caches()
        return await self.kernel().boot()

    async def run(
        self, argv: Sequence[str], *, inputs: Sequence[str] = (), interactive: bool = True
    ) -> tuple[int, str]:
        """Run ``argv`` through the booted kernel's console, answering questions from ``inputs``.

        Returns:
            The exit code, and everything printed — standard output, then
            standard error — as plain text.
        """
        async with await self.boot() as booted:
            application = await booted.container.get(Application)
            tester = ApplicationTester(application, width=_WIDTH)
            code = await tester.execute(argv, inputs=inputs, interactive=interactive)
        return code, tester.display + tester.error_display

    def import_generated(self, module: str) -> ModuleType:
        """Import ``module``, dotted inside the package, as the application would."""
        importlib.invalidate_caches()
        return importlib.import_module(f"{self.package}.{module}")

    def read(self, path: str) -> str:
        """Return the text of ``path``, relative to the package directory."""
        return (self.package_dir / path).read_text(encoding="utf-8")

    @staticmethod
    def _write_package(directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        init = directory / "__init__.py"
        if not init.exists():
            _ = init.write_text('"""A package of the application."""\n', encoding="utf-8")
