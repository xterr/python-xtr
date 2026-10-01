<div align="center">

# xtr

**Small, typed, async-ready building blocks for Python applications — one repository, one package each.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="managed with uv" src="https://img.shields.io/badge/managed%20with-uv-DE5FE9">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

Each directory under [`packages/`](packages) is an independent distribution with its own version,
dependencies, tests and README. They are developed together here so a change that crosses
packages is one commit, and released separately so an application installs only what it uses.

## Packages

| Package | What it is |
|---|---|
| [xtr-cache](packages/xtr-cache) | Cache pools in memory, in files, in Redis, chained or tag-aware, with stampede protection. |
| [xtr-cache-contracts](packages/xtr-cache-contracts) | The caching interfaces alone: fetch-or-compute, item pools, tags and namespaces. |
| [xtr-clock](packages/xtr-clock) | An injectable clock, a timezone-aware `DatePoint`, and a frozen clock for tests. |
| [xtr-console](packages/xtr-console) | Async-native console applications: commands as functions or classes, wired by a container. |
| [xtr-dependency-injection](packages/xtr-dependency-injection) | A bundle and kernel layer for Python, compiled to a wireup container. |
| [xtr-dotenv](packages/xtr-dotenv) | Layered `.env` files loaded into the environment, and the same layers behind a typed settings model. |
| [xtr-event-dispatcher](packages/xtr-event-dispatcher) | Events dispatched to listeners and subscribers by priority, any of them able to stop the rest. |
| [xtr-event-dispatcher-contracts](packages/xtr-event-dispatcher-contracts) | The event dispatching interfaces alone, for libraries that emit events without choosing who hears them. |
| [xtr-http-kernel](packages/xtr-http-kernel) | A request lifecycle for FastAPI applications: requests turned into responses through events, wired by a container. |
| [xtr-logging](packages/xtr-logging) | Channels, handlers, processors and formatters behind one logger interface. |
| [xtr-logging-contracts](packages/xtr-logging-contracts) | The logging interface alone, for libraries that log but should not choose how. |
| [xtr-messenger](packages/xtr-messenger) | A message bus: envelopes, stamps, a middleware chain and pluggable transports. |
| [xtr-orm](packages/xtr-orm) | Engines, sessions and versioned schema migrations for async applications, configured once per connection. |
| [xtr-password-hasher](packages/xtr-password-hasher) | Password hashing behind one interface: argon2id by default, legacy hashes verified and upgraded. |
| [xtr-security-core](packages/xtr-security-core) | The security core: users, tokens, roles, voters and the authorization decision. |
| [xtr-security-http](packages/xtr-security-http) | The HTTP edge of security: firewalls, authenticators, bearer access tokens and the request surface. |
| [xtr-security-jwt](packages/xtr-security-jwt) | Self-issued JSON Web Tokens: key sets, an encoder and a token manager for a user. |
| [xtr-security](packages/xtr-security) | The security bundle: the family facade and the container wiring that configures it. |
| [xtr-service-contracts](packages/xtr-service-contracts) | What a container drives on a service, not what the service does. No dependencies. |
| [xtr-lock](packages/xtr-lock) | Exclusive and shared locks around resources, in memory, in files, in Redis, or across several stores. |
| [xtr-scheduler](packages/xtr-scheduler) | Recurring messages on xtr-messenger: cron and intervals, catch-up after downtime, locks and saved state. |
| [xtr-rate-limiter](packages/xtr-rate-limiter) | Limits on how often anything may happen, by fixed window, sliding window or token bucket, in memory, in a cache or atomically in Redis. |

How they depend on each other (runtime dependencies only; extras are dotted):

```mermaid
graph LR
    logging[xtr-logging] --> clock[xtr-clock]
    logging --> logcon[xtr-logging-contracts]
    logging --> svccon[xtr-service-contracts]
    messenger[xtr-messenger] --> logcon
    messenger --> eventcon
    lock[xtr-lock] --> clock
    lock --> logcon
    cachecon[xtr-cache-contracts] --> clock
    cache[xtr-cache] --> cachecon
    cache --> lock
    cache -. console extra .-> console
    events[xtr-event-dispatcher] --> eventcon[xtr-event-dispatcher-contracts]
    events --> logcon
    messenger -. console extra .-> console[xtr-console]
    scheduler[xtr-scheduler] --> messenger
    scheduler --> clock
    scheduler --> lock
    scheduler --> cachecon
    scheduler --> events
    scheduler --> svccon
    scheduler -. console extra .-> console
    httpkernel[xtr-http-kernel] --> di[xtr-dependency-injection]
    httpkernel --> events
    httpkernel --> eventcon
    httpkernel --> logcon
    httpkernel -. logging extra .-> logging
    httpkernel -. console extra .-> console
    orm[xtr-orm] --> logcon
    orm -. di extra .-> di
    orm -. di extra .-> svccon
    orm -. console extra .-> console
    orm -. messenger extra .-> messenger
    ratelimiter[xtr-rate-limiter] --> clock
    ratelimiter --> eventcon
    ratelimiter -. cache extra .-> cachecon
    ratelimiter -. lock extra .-> lock
    ratelimiter -. di extra .-> di
    httpkernel -. rate-limiter extra .-> ratelimiter
    passwordhasher[xtr-password-hasher]
    passwordhasher -. console extra .-> console
    securitycore[xtr-security-core] --> passwordhasher
    securitycore --> eventcon
    securitycore --> svccon
    securityhttp[xtr-security-http] --> securitycore
    securityhttp --> httpkernel
    securityhttp --> eventcon
    securityhttp --> logcon
    securityhttp --> passwordhasher
    security[xtr-security] --> securitycore
    security --> securityhttp
    security --> passwordhasher
    security --> di
    security --> events
    security --> httpkernel
    security -. console extra .-> console
    securityjwt[xtr-security-jwt] --> security
    securityjwt --> securitycore
    securityjwt --> securityhttp
    securityjwt --> di
    securityjwt --> clock
    securityjwt --> events
    securityjwt --> eventcon
    securityjwt -. console extra .-> console
```

The contracts packages exist so a library can depend on an interface without installing its
implementation: [xtr-messenger](packages/xtr-messenger) logs through `xtr-logging-contracts`, and
the application decides whether `xtr-logging` is behind it.

## Install

Each package is published to PyPI on its own:

```sh
uv add xtr-logging
uv add "xtr-messenger[amqp]"
uv add "xtr-scheduler[cron]"
```

## Versions

Every package shares one version and is released together, even one that did not change — any
two `xtr-*` packages at the same version are known to work together. Packages require their
siblings by major version (`xtr-logging-contracts>=2.0,<3`).

[`scripts/release.py`](scripts/release.py) keeps that consistent:

```sh
uv run scripts/release.py check        # every package and this README on one version (CI runs this)
uv run scripts/release.py bump 2.0.0   # move every package and this README; on a new major, rewrite the ranges
```

A package classified `Private :: Do Not Upload` moves with the rest but is never published or
split.

## Releasing

```sh
uv run scripts/release.py bump 2.0.0
git commit -am "bump: 2.0.0" && git push
git tag 2.0.0 && git push origin 2.0.0
```

The tag starts the [release workflow](.github/workflows/release.yml): it waits for CI to pass on
the tagged commit's push to `main` — nothing is released otherwise — checks the tag against the
packages' version, publishes every package to PyPI through trusted publishing, and tags each
read-only repository `2.0.0`.

## Repositories

This repository is where everything is developed. Each published package is also copied, once
CI passes on a push to `main`, into a repository of its own — `xterr/python-<package>`, e.g.
[python-xtr-logging](https://github.com/xterr/python-xtr-logging) — which carries only that
package's directory and history, and its release tags. Those copies are read-only: pull requests
there are closed automatically, so send issues and pull requests here.

## Development

Requires [uv](https://docs.astral.sh/uv/). The repository is a
[uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/): one lockfile, one
virtual environment, and every package installed editable, so a change in one package is
immediately visible to the packages that use it.

```sh
git clone git@github.com:xterr/python-xtr.git
cd python-xtr
uv sync --all-packages
uv run pre-commit install
```

The pre-commit hook runs ruff on what you commit and the tests of every package you touched.
[CI](.github/workflows/ci.yml) runs everything, for every package, on Python 3.11 and 3.14.

Work inside a package directory; each carries its own pytest, ruff, basedpyright and ty settings:

```sh
cd packages/xtr-logging
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
uv run ty check
```

To run one package against only the dependencies it declares, from the repository root:

```sh
uv run --package xtr-logging --exact pytest packages/xtr-logging
```

This is the check that catches a package importing a sibling it never listed in its
`pyproject.toml` — something the shared environment would otherwise hide.

### Creating a package

Every package follows the same shape. Rules that apply to code, tests, docs and commit
messages live in [AGENTS.md](AGENTS.md); this section is the mechanical checklist.

A package contains: a `pyproject.toml` at the current shared version, a
`src/xtr_<name>/` importable package with `py.typed`, tests under `tests/`, a `README.md`
starting with the package's one-line pitch, and a `LICENSE`. A package integrates with
[xtr-dependency-injection](packages/xtr-dependency-injection) through a bundle under
`src/xtr_<name>/bundle/`.

#### Directory template

```
packages/xtr-<name>/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/xtr_<name>/
│   ├── __init__.py
│   ├── py.typed
│   ├── <thing>.py                 # one public class per file
│   ├── <thing>_interface.py       # @runtime_checkable Protocol
│   ├── exception/
│   │   ├── __init__.py
│   │   ├── <name>_error.py        # package base error
│   │   └── <specific>_error.py
│   └── bundle/
│       ├── __init__.py
│       ├── <name>_bundle.py
│       └── <name>_config.py
└── tests/
    ├── conftest.py
    ├── unit/
    ├── integration/
    ├── fixtures/
    └── support/
```

#### `pyproject.toml`

```toml
[project]
name = "xtr-<name>"
version = "2.0.0"
description = "<one-line pitch, on this project's own terms>."
readme = "README.md"
requires-python = ">=3.11"
license = "MIT"
license-files = ["LICENSE"]
authors = [
    { name = "Xterr", email = "me@xterr.dev" }
]
keywords = ["<name>"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Typing :: Typed",
]
dependencies = []

[project.optional-dependencies]
di = [
    "xtr-dependency-injection>=2.0,<3",
]

# Advertises the bundle so debug:bundles can name it when installed but not listed.
# Advertising activates nothing: an application lists the bundles it wants.
[project.entry-points."xtr_dependency_injection.bundles"]
<name> = "xtr_<name>.bundle:<Name>Bundle"

[dependency-groups]
dev = [
    "basedpyright>=1.21",
    "ruff>=0.8",
    "pytest>=8",
    "pytest-cov>=5",
    "anyio>=4.0",
    "ty>=0.0.83",
    "xtr-dependency-injection>=2.0,<3",
]

[build-system]
requires = ["uv_build>=0.9.18,<0.10.0"]
build-backend = "uv_build"

[tool.basedpyright]
typeCheckingMode = "all"
pythonVersion = "3.11"
pythonPlatform = "All"
include = ["src", "tests"]
exclude = ["**/__pycache__", "**/.venv", "**/build", "**/dist", ".tmp"]
reportUnusedCallResult = "warning"
reportUnnecessaryTypeIgnoreComment = "error"
reportUnusedVariable = "error"
reportMissingParameterType = "error"
reportPrivateUsage = "error"

[tool.ruff]
target-version = "py311"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["ALL"]
ignore = [
    "COM812", "ISC001", "D203", "D213", "CPY001", "FBT001", "FBT002", "TD002", "TD003", "FIX002",
    # Errors compose their message from typed fields; the string at a raise site is a reason.
    "TRY003", "EM101", "EM102",
    # Add when the package logs through the logging contract, whose context mapping
    # the standard library's format-argument checks misread:
    # "PLE1205", "PLE1206",
]
fixable = ["ALL"]
unfixable = []

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101", "ARG", "PLR2004", "SLF001", "D"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.ty.src]
include = ["src", "tests"]

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
addopts = ["-ra", "--strict-config", "--strict-markers"]
filterwarnings = ["error"]

[tool.coverage.run]
source = ["src"]
branch = true

[tool.coverage.report]
# CI runs the tests with --cov; a change taking coverage below this fails there.
fail_under = 95
```

Packages never declare their own `[tool.uv.sources]`; the root maps every `xtr-*` name to
the workspace.

#### `src/xtr_<name>/__init__.py`

```python
"""<one-line pitch, on this project's own terms>."""

from __future__ import annotations

__all__ = []
```

An empty `src/xtr_<name>/py.typed` sits next to it.

#### Bundle and config

The bundle is optional — a library without a container works as it stands — but the shape is
fixed so every application configures every package the same way. Read
[`packages/xtr-dependency-injection/README.md`](packages/xtr-dependency-injection/README.md)
for what each hook means; the template below is a working starting point.

```python
# src/xtr_<name>/bundle/<name>_config.py
"""Configuration for the <name> bundle."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["<Name>Config"]


@dataclass(frozen=True, slots=True)
class <Name>Config:
    """Values the bundle builds from. Must be buildable with no arguments."""

    # example field; delete or replace
    option: str = "default"

    def __post_init__(self) -> None:
        """Validate combinations that dataclass defaults cannot express."""
```

```python
# src/xtr_<name>/bundle/<name>_bundle.py
"""The xtr-<name> bundle."""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_dependency_injection import Bundle, ContainerBuilder, ServiceConfigurator, as_bundle

from .<name>_config import <Name>Config

__all__ = ["<Name>Bundle"]


@final
@as_bundle("<name>", config=<Name>Config)
class <Name>Bundle(Bundle[<Name>Config]):
    """Registers the <name> services under the container."""

    @override
    def load_extension(
        self,
        config: <Name>Config,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register services on the container from ``config``."""
        del builder, config, services  # replace with real registrations
```

```python
# src/xtr_<name>/bundle/__init__.py
"""The xtr-dependency-injection bundle for xtr-<name>."""

from __future__ import annotations

from .<name>_bundle import <Name>Bundle
from .<name>_config import <Name>Config

__all__ = ["<Name>Bundle", "<Name>Config"]
```

A package with a bundle also advertises it — the `[project.entry-points]` block in the
`pyproject.toml` above — and its README carries a *Use in an application* section (see the
skeleton below). Drop both for a package without a bundle.

#### Tests

Unit tests mirror `src/xtr_<name>/` one-for-one under `tests/unit/`. Every bundle has a
zero-config test:

```python
# tests/unit/bundle/test_<name>_bundle.py
"""The <name> bundle honours the zero-config contract."""

from __future__ import annotations

import pytest
from xtr_dependency_injection.testing import assert_zero_config

from xtr_<name>.bundle import <Name>Bundle


@pytest.mark.anyio
async def test_it_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(<Name>Bundle)
```

```python
# tests/conftest.py
"""Shared test fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
```

#### README skeleton

````markdown
<div align="center">

# xtr-<name>

**<one-line pitch>.**

</div>

---

## Why?

## Install

```sh
uv add xtr-<name>
```

## Quick start

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what
removing it undoes.

- **Install** — `uv add "xtr-<name>[di]"`; the other extras and what each is for.
- **Activate** — `<Name>Bundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`, imported
  from `xtr_<name>.bundle` — or "nothing to do" when another bundle requires it.
- **Brings along** — the bundles its `@required_bundle` pulls in, and when.
- **Configure** — what the zero-config path gives; then the `<app>/config/<name>.py`
  `@configure` function that changes it, linking to *Kernel / bundle*.
- **Environment** — variables the application must set, or "nothing".
- **Ignore** — `.gitignore` lines for files it writes into the project, or "nothing".
- **Remove** — every step above, undone, ending with `uv remove xtr-<name>`.
- **Check** — the command that shows it working, usually `debug:bundles`.

Add **Entry point**, **Load** or **Run** only when the package needs one.

## Kernel / bundle

## Development

## License

MIT — see [LICENSE](LICENSE).
````

#### Registering the package

1. Add `xtr-<name> = { workspace = true }` to `[tool.uv.sources]` in the root
   [`pyproject.toml`](pyproject.toml).
2. Add a row to the [Packages table](#packages) at the top of this README.
3. Run `uv lock` from the repository root.
4. Create the empty `xterr/python-xtr-<name>` repository on GitHub (CI's split job
   populates it once CI passes on a push to `main`), and add it to the split GitHub App's installation
   before pushing. The app's token is requested for every read-only repository at once, so
   one repository it cannot reach fails the split for all of them.
5. Register a pending trusted publisher for `xtr-<name>` on PyPI before its first release.

If a sibling's version leaves a range, `uv lock` fails; that is the reminder to update the
range.

## Layout

```
python-xtr/
├── .github/workflows/  # ci (with the split into the read-only copies), release
├── packages/
│   └── xtr-<name>/
│       ├── .github/    # only for the read-only copy: closes its pull requests
│       ├── src/xtr_<name>/
│       ├── tests/
│       ├── pyproject.toml
│       ├── README.md
│       └── LICENSE
├── examples/bookshop/  # an application on every package — its own uv project, on the shared version
├── scripts/release.py  # one version for every package
├── pyproject.toml      # workspace root: members and sources, never published
└── uv.lock             # the packages' lockfile; the example has its own
```

## License

MIT — see [LICENSE](LICENSE). Every package ships the same license in its own directory.
