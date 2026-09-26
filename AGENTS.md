# AGENTS.md

Rules for agents working in this repository.

## Naming and vocabulary — hard rule

- Never write **Symfony** or **PHP** anywhere: code, identifiers, comments, docstrings, tests,
  READMEs, other docs, commit messages, `pyproject.toml` metadata (descriptions, keywords,
  classifiers), issue and PR text. This file is the only place that names either.
- Describe every package on its own terms. If a concept originated in another framework, drop
  the citation and explain what it does here.

## Structural standard

- Every library — current and future — mirrors the same component structure Symfony uses,
  translated to Python and expressed in snake_case:
  - A component is a package named `xtr-<name>` (distribution) / `xtr_<name>` (import).
  - Each library ships one **bundle** that integrates it with `xtr-dependency-injection`.
  - When another library must depend on the interface without pulling the implementation, the
    interfaces live in a companion package `xtr-<name>-contracts`.
  - Class and concept names stay equivalent to those of the corresponding component (e.g.
    `ContainerInterface`, `Bundle`, `ServiceLocator`), just PEP 8-cased.
- Keep the resemblance in shape, not in prose: docs, docstrings and errors read as if the
  library grew here.

## Package layout

```
packages/xtr-<name>/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/xtr_<name>/
│   ├── __init__.py              # module docstring, __all__, public re-exports
│   ├── py.typed
│   ├── <thing>.py               # one public class per file, file named after it
│   ├── <thing>_interface.py     # Protocol, @runtime_checkable
│   ├── exception/
│   │   ├── __init__.py
│   │   ├── <name>_error.py      # package base error
│   │   └── <specific>_error.py  # one error per file, derives from the base
│   └── bundle/
│       ├── __init__.py
│       ├── <name>_bundle.py
│       └── <name>_config.py
└── tests/
    ├── conftest.py
    ├── unit/                    # mirrors src/xtr_<name>/ exactly
    ├── integration/
    ├── fixtures/
    └── support/
```

- One public class per file; the file is named after the class in snake_case.
- Interfaces are `Protocol` subclasses decorated `@runtime_checkable`, suffixed `Interface`.
- Every exception derives from the package's single base error.
- `py.typed` ships in every package.

## Bundle rules

Read `packages/xtr-dependency-injection/README.md` for the full API. In short:

- Declare the bundle with `@as_bundle("<name>", config=<Config>)` on a `Bundle[<Config>]`
  subclass.
- Hooks are optional and each has one job: `build`, `prepend_extension`, `load_extension`,
  `process`, `async boot`, `async shutdown`.
- Declare optional peers with `@required_bundle(Target, ignore_on_invalid=True)`; hard peers
  drop the flag.
- The config type is a frozen dataclass buildable with no arguments; validate in
  `__post_init__`.
- The bundle's zero-config path must build and boot with no application configuration and do
  no I/O until a service is requested. Every bundle test suite calls
  `assert_zero_config(<Bundle>)`.
- Libraries never import `wireup` and never call the wireup integration. Only
  `xtr-dependency-injection` — through `xtr_dependency_injection.integration.wireup` — is
  allowed to.
- The library keeps working without a container: the bundle is an integration on top, not a
  requirement.

## Code conventions

- Python `>= 3.11`.
- Every module starts with `from __future__ import annotations`, a module docstring, and
  declares `__all__`.
- Prefer `@final` on public classes not meant to be subclassed, and `__slots__` where cheap.
- Google-style docstrings; explain **why**, not what the code obviously does.
- Ruff `select = ["ALL"]`; basedpyright `typeCheckingMode = "all"`; `ty` as a second opinion.
- No `# type: ignore` and no `# noqa` without a comment stating the reason.
- Typing-only imports go under `if TYPE_CHECKING:` unless the annotation is read at runtime
  (e.g. a class the container hydrates, a bundle config).

## Tests

- `pytest` with `anyio` for async; no `pytest-asyncio` strict mode.
- Test functions named `test_<behaviour>` — one behaviour per test.
- Prefer fakes over mocks; a fake carries its own contract test.
- Every bundle has a zero-config test using `assert_zero_config`.
- Unit tests mirror `src/xtr_<name>/` one-for-one under `tests/unit/`.

## Commands

The gate every package must pass, from the package directory:

```sh
uv run ruff check
uv run ruff format --check
uv run basedpyright
uv run ty check
uv run pytest
```

Or one line:

```sh
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

To run a single package against only the dependencies it declares (catches an accidental
import of a sibling), from the repository root:

```sh
uv run --package xtr-<name> --exact pytest packages/xtr-<name>
```

## Git

- Conventional commits: `<type>: <lowercase description>`.
- Types: `feature`, `fix`, `docs`, `style`, `lint`, `refactor`, `test`, `revert`, `bump`,
  `merge`, `update`, `chore`.
- Never add `Co-Authored-By:` lines for any AI assistant.
- Never `git push` on your own; the human pushes.
- Never bypass hooks (`--no-verify`, `-c core.hooksPath=/dev/null`, etc.).
- All packages share one version, moved together with `scripts/release.py bump <version>`.
