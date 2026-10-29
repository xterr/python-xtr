# AGENTS.md

Rules for agents working in this repository.

## Tools — hard rule

Read, search and change files only through the **jetbrains_pycharm** MCP:

| Task | Use | Never |
|---|---|---|
| Read a file | `read_file` | `cat`, `head`, `sed -n`, the native Read |
| Find files | `search_file`, `list_directory_tree` | `find`, `ls` |
| Search code | `search_text`, `search_regex`, `search_symbol` | `grep`, `rg` |
| Change or create files | `apply_patch`, `create_new_file`, `rename_refactoring` | `sed`, native Edit/Write, Python or shell patch scripts |
| Check a file | `lint_files`, `get_file_problems` | — |

The shell is for running commands only: `uv`, the gate, `git`. If the MCP does not respond,
say so before falling back to anything else.

## Naming and vocabulary — hard rule

- Never write **Symfony** or **PHP** anywhere: code, identifiers, comments, docstrings, tests,
  READMEs, other docs, commit messages, `pyproject.toml` metadata (descriptions, keywords,
  classifiers), issue and PR text. This file is the only place that names either.
  The exceptions are attribution: a package's `LICENSE`, which under its own copyright line
  carries, word for word, the copyright line of every project its code is translated from,
  whatever that line names; the root `CREDITS.md`, which names those projects; and the root
  README's *Credits* section, which points to it.
- Describe every package on its own terms. If a concept originated in another framework, drop
  the citation and explain what it does here.
- Never use the word **spec** in a name: no `Spec` class suffix, no `*_spec` / `*_specs` module,
  function, variable or fixture. A configuration object is a `...Config` (e.g.
  `LocalAdapterConfig`), and a module grouping several is named `*_configs.py`. Docstrings and
  comments say "configuration", not "spec".

## Structural standard

- Every library — current and future — mirrors the same component structure Symfony uses,
  translated to Python and expressed in snake_case:
  - A component is a package named `xtr-<name>` (distribution) / `xtr_<name>` (import).
  - A library ships at most one **bundle** that integrates it with `xtr-dependency-injection`.
    Not every package needs one:
    - A standalone library ships its own bundle, inside the package (`xtr_<name>/bundle/`).
    - A component family ships its integration as a separate **bundle package**: `xtr-security`
      is the bundle for the security family — `xtr-security-core`, `xtr-security-http` and
      `xtr-password-hasher`. The family's components ship no bundle; only the bundle package
      configures and wires them.
    - An add-on built on a family ships its own bundle and depends on the family's bundle, never
      the other way round: `xtr-security-jwt`'s `JwtBundle` requires the security bundle and
      registers its authenticator into it through the bundle's extension points. The family's
      bundle does not know the add-on exists.
    - A contracts package never ships a bundle.
  - When another library must depend on the interface without pulling the implementation, the
    interfaces live in a companion package `xtr-<name>-contracts`.
  - Class and concept names stay equivalent to those of the corresponding component (e.g.
    `ContainerInterface`, `Bundle`, `ServiceLocator`), just PEP 8-cased.
  - Folders mirror the corresponding component's folders, snake_cased (`AccessToken/` →
    `access_token/`), with these translations:
    - `Attribute/` → `decorator/`: what the component declares with an attribute is a decorator
      (or an `Annotated` marker) here — `IsGranted`, `CurrentUser`, `as_command`.
    - `DependencyInjection/` → `bundle/`: the bundle, its configuration and its compiler passes
      live there, flat; everything else — factories a bundle uses, firewalls, commands — lives in
      the library's own folders. `Command/` → `command/` at the package root.
    - `Resources/config/` has no counterpart: services are registered in code by the bundle.
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
│   ├── decorator/               # decorators and Annotated markers
│   ├── command/                 # console commands
│   ├── .agents/skills/xtr-<name>/  # agent skill, shipped in the wheel (see Agent skills)
│   │   ├── SKILL.md
│   │   └── references/          # optional, for what does not fit SKILL.md
│   └── bundle/                  # only in a package that ships a bundle; flat
│       ├── __init__.py
│       ├── <name>_bundle.py
│       ├── <name>_config.py     # (+ `*_configs.py` for tagged unions)
│       └── <what>_pass.py       # compiler passes, when the bundle needs any
└── tests/
    ├── conftest.py
    ├── unit/                    # mirrors src/xtr_<name>/ exactly
    ├── integration/
    ├── fixtures/
    └── support/
```

- One public class per file; the file is named after the class in snake_case.
  The one exception: the variants of a tagged configuration union — the configurations a `type`
  field picks between — may share a `*_configs.py` module named after what they configure.
- Interfaces are `Protocol` subclasses decorated `@runtime_checkable`, suffixed `Interface`.
- Every exception derives from the package's single base error.
- `py.typed` ships in every package.

## Bundle rules

These apply to every package that ships a bundle. Read
`packages/xtr-dependency-injection/README.md` for the full API. In short:

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
  A setting only the application can supply — a signing key, a credential — is checked where it
  is used, never at build: the bundle builds and boots without it (so the console still runs,
  to mint or inspect it), and the service needing it raises an error naming the setting the
  first time it is used. Never generate such a setting on the application's behalf.
- Never inject the whole container. A service, command, listener or factory declares the
  services it needs as typed parameters (`Injected[...]`, `Target(...)`, `Sequence[T]`,
  `Mapping[..., T]`, `ServiceLocator[T]` for a name-keyed lookup); a service whose dependency may
  be absent is registered only when that dependency is, not given the container to probe it.
- Libraries never import `wireup` and never call the wireup integration. Only
  `xtr-dependency-injection` — through `xtr_dependency_injection.integration.wireup` — is
  allowed to.
- The library keeps working without a container: the bundle is an integration on top, not a
  requirement. A component a bundle package wires must work on its own too.
  This is about coupling, not about defaults: library code never depends on the container to
  exist, and every class can be built by hand from its constructor. It does not mean every
  class must be buildable with no arguments. A class, service or command that needs a
  dependency takes it as a required parameter, and whoever builds it — the container or the
  caller — supplies it. Never invent a sentinel default, a fallback implementation or a
  "no container" code path just so a class builds bare; without its dependency it fails
  loudly at construction (for a command, xtr-console reports the missing parameter).
- Advertise the bundle in `pyproject.toml` under
  `[project.entry-points."xtr_dependency_injection.bundles"]`, named after the bundle. It is
  only reported by `debug:bundles`, never activated. The kernel's own bundle
  (`xtr-dependency-injection`) is the one exception: it is never advertised under this entry
  point, because it is the container the entry point is read by — it is always present, so
  announcing it to `debug:bundles` as a discoverable peer would be redundant and misleading.
- The README of the package that ships the bundle carries a **Use in an application** section
  (a component wired by a bundle package points to that package's section instead), placed before
  *Kernel / bundle*, with the bullets of the root README's skeleton: Install, Recipe, Activate,
  Brings along, Configure, Environment, Ignore, Remove, Check. The **Recipe** bullet comes right
  after *Install* and names exactly the steps that package's `recipe/` performs — the subset of
  *Activate*, *Configure*, *Environment* and *Ignore* the recipe can make declaratively, and no
  step it cannot. A recipe that only writes a `config/bundles.py` entry and a `.gitignore` line says so;
  it does not claim to do *Configure* when the package has no recipe-written configuration. Keep
  it true when the bundle, its config defaults, its peers or its extras change — and, because the
  recipe is that same list made declarative, keep the package's `recipe/` true whenever those
  bullets change.

## Agent skills

A package an application depends on directly ships an agent skill that teaches a coding agent
to use it: `src/xtr_<name>/.agents/skills/xtr-<name>/SKILL.md`. It lives inside the import
package so it ships in the wheel, at the version it describes; `uvx library-skills` links it
into an application.

- Who ships one follows the bundle rules: a standalone library ships its own; a component
  family's skill lives in its bundle package (`xtr-security` covers `xtr-security-core`,
  `xtr-security-http` and `xtr-password-hasher`); an add-on ships its own and points to the
  family's. Contracts packages ship none. A skill is optional, never required by CI.
- Frontmatter has two single-line keys: `name` — equal to the directory name, `xtr-<name>` or
  `xtr-<name>-<topic>` — and `description`, at most 1024 characters, saying what the package
  is for and, after "Use when", the situations that should load it.
- Body: Quick reference, task sections with working examples, Testing, Use in an application
  (the README section as steps), Errors, Do not. Keep `SKILL.md` short; move depth to
  `references/*.md` and link it.
  The two `xtr-dependency-injection` skills (`xtr-dependency-injection` and
  `xtr-dependency-injection-bundle-authoring`) are exempt from the *Use in an application* body
  section: the kernel ships no recipe-driven bundle an application activates — it *is* the
  container every other bundle plugs into — so there are no *Activate*, *Configure*, *Environment*
  or *Ignore* steps to restate.
- Every name and example must exist in the source and run. Keep the skill true when the API,
  the bundle, its config or its README's *Use in an application* section changes.
- The naming rules above apply to skills as they do to code.
- `tests/test_skills.py` at the root checks every skill that exists.

## Adding a package to an application

- Start with `uv run xtr-recipes recipes:add <requirement>` (or `uv run xtr-recipes recipes:sync`
  after a plain `uv add`): it applies what the package's **Use in an application** *Activate*,
  *Configure*, *Environment* and *Ignore* bullets list, and prints the steps it cannot make.
- A development-only package takes `recipes:add --dev`: its bundles are listed for `dev` only, and
  by name (`"module:Class": {"dev": True}`), so a deployment, which does not install it, never
  imports them.
- Do the steps the recipe prints under `steps`, and any remaining **Use in an application** bullet
  the recipe does not cover; do not invent steps the README does not list.
- Confirm with `debug:bundles`: the bundle is `active`, and nothing you meant to activate is
  under **Installed, not active**.
- Removing a package is the same read backwards — `uv run xtr-recipes recipes:remove <package>`,
  then undo any printed step.

## Code conventions

- Python `>= 3.11`.
- Every module starts with `from __future__ import annotations`, a module docstring, and
  declares `__all__`.
- Prefer `@final` on public classes not meant to be subclassed, and `__slots__` where cheap.
- Anything involving a clock ALWAYS uses `xtr-clock`: declare it as a dependency of the
  package, take `clock: ClockInterface | None = None` defaulting to `SystemClock()` (the
  shape the core `SignatureHasher` uses), and freeze a `MockClock` in tests. Never
  hand-roll a time reader, a `_clock` module, or scattered `datetime.now()` / `time()`
  calls.
- Name every parameter for exactly what it holds — never for what it produces, never a
  shortening of it: a factory parameter ends in `_factory` and matches its interface
  (`stream_factory: StreamFactoryInterface`, not `streams`); mass-noun names for typed
  collaborators (`streams`, `messages`, `responses`, `uris`) are banned; anything else
  carries its full role name.
- Google-style docstrings; explain **why**, not what the code obviously does.
- Ruff `select = ["ALL"]`; basedpyright `typeCheckingMode = "all"`; `ty` as a second opinion.
- No `# type: ignore` and no `# noqa` without a comment stating the reason.
- Typing-only imports go under `if TYPE_CHECKING:` unless the annotation is read at runtime
  (e.g. a class the container hydrates, a bundle config).

## Tests

- `pytest` with `anyio` for async; no `pytest-asyncio` strict mode.
- Test functions named `test_<behaviour>` — one behaviour per test.
- Prefer fakes over mocks; a fake carries its own contract test.
- Every bundle has a zero-config test using `assert_zero_config`; a package without a bundle
  has none.
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

Running commands — hard rule:

- Do not wrap commands in long `timeout`s (`timeout 900`, `timeout 600`, …). The shell tool
  already has its own timeout. A package gate takes seconds; a hung command under a long
  `timeout` just blocks everyone for its full length. Run the gate bare, or with a short
  `timeout` (at most a minute or two) when a hang is a real risk.
- Run a package suite once per change set; iterate with the targeted test files.
- Never run two `--exact` commands at the same time: they share one `.venv` and uninstall each
  other's dependencies mid-run. Run them one after another, then `uv sync`.

## Git

- Conventional commits: `<type>: <lowercase description>`.
- Types: `feature`, `fix`, `docs`, `style`, `lint`, `refactor`, `test`, `revert`, `bump`,
  `merge`, `update`, `chore`.
- Never add `Co-Authored-By:` lines for any AI assistant.
- Never `git push` on your own; the human pushes.
- Never bypass hooks (`--no-verify`, `-c core.hooksPath=/dev/null`, etc.).
- All packages share one version, moved together with `scripts/release.py bump <version>`.

## Worktrees

Work asked for "in another worktree" — or any change that must not land on the branch checked
out here, where someone else's work may be in progress — goes in a git worktree under
`.worktrees/` at the repository root.

- Create it from the branch it builds on, usually `main`, never from the checked-out branch:
  `git worktree add .worktrees/<name> -b <type>/<topic> main`. Confirm the base with
  `git -C .worktrees/<name> log --oneline -1`.
- It sits inside the project so the jetbrains_pycharm MCP reaches it: every tool path starts
  with `.worktrees/<name>/`, and the tools rule above applies there as it does here.
  `/.worktrees/` is ignored, so the worktree never shows up in this checkout's status.
- It has its own `.venv`. Run `uv sync --all-packages --all-extras` in it before anything else,
  and run every `uv` command there with `VIRTUAL_ENV` unset (`export VIRTUAL_ENV=`), or it
  warns and may reach for this checkout's environment instead of its own.
- Gates, `--exact` runs and the example application all run from inside the worktree. Leave
  nothing behind in it you would not commit; pytest's `.tmp` directories are ignored and go too.
- Once the branch is merged, remove it from this checkout:
  `git worktree remove .worktrees/<name>`. Deleting the branch is the human's call.
