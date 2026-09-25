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
| [xtr-clock](packages/xtr-clock) | An injectable clock, a timezone-aware `DatePoint`, and a frozen clock for tests. |
| [xtr-console](packages/xtr-console) | Async-native console applications: commands as functions or classes, wired by a container. |
| [xtr-dependency-injection](packages/xtr-dependency-injection) | A Symfony-style bundle and kernel layer, compiled to a wireup container. |
| [xtr-logging](packages/xtr-logging) | Channels, handlers, processors and formatters behind one logger interface. |
| [xtr-logging-contracts](packages/xtr-logging-contracts) | The logging interface alone, for libraries that log but should not choose how. |
| [xtr-messenger](packages/xtr-messenger) | A message bus: envelopes, stamps, a middleware chain and pluggable transports. |
| [xtr-service-contracts](packages/xtr-service-contracts) | What a container drives on a service, not what the service does. No dependencies. |
| [xtr-lock](packages/xtr-lock) | Planned — not implemented yet. |
| [xtr-scheduler](packages/xtr-scheduler) | Planned — not implemented yet. |

How they depend on each other (runtime dependencies only; extras are dotted):

```mermaid
graph LR
    logging[xtr-logging] --> clock[xtr-clock]
    logging --> logcon[xtr-logging-contracts]
    logging --> svccon[xtr-service-contracts]
    messenger[xtr-messenger] --> logcon
    messenger -. console extra .-> console[xtr-console]
```

The contracts packages exist so a library can depend on an interface without installing its
implementation: [xtr-messenger](packages/xtr-messenger) logs through `xtr-logging-contracts`, and
the application decides whether `xtr-logging` is behind it.

## Install

The packages are not on PyPI yet. Until they are, install one straight from this repository —
uv resolves its `xtr-*` dependencies from the same commit:

```sh
uv add "xtr-logging @ git+https://github.com/xterr/python-xtr#subdirectory=packages/xtr-logging"
```

Swap both `xtr-logging` occurrences for the package you want. Extras work as usual:
`"xtr-messenger[amqp] @ git+…"`.

This relies on uv. pip installs the package itself but looks for its `xtr-*` dependencies on
PyPI, where they are not yet.

## Development

Requires [uv](https://docs.astral.sh/uv/). The repository is a
[uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/): one lockfile, one
virtual environment, and every package installed editable, so a change in one package is
immediately visible to the packages that use it.

```sh
git clone git@github.com:xterr/python-xtr.git
cd python-xtr
uv sync --all-packages
```

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

### Adding a package

1. Create `packages/xtr-<name>/` with a `pyproject.toml`, `src/xtr_<name>/`, `README.md` and
   `LICENSE`. The workspace picks up anything matching `packages/xtr-*`.
2. Add `xtr-<name> = { workspace = true }` to `[tool.uv.sources]` in the root `pyproject.toml`.
3. Run `uv lock`.

Packages depend on each other by version range (`xtr-logging-contracts>=0.2,<0.3`) and never
declare their own `[tool.uv.sources]`; the root maps every `xtr-*` name to the workspace. If a
sibling's version leaves a range, `uv lock` fails, which is the reminder to update the range.

## Layout

```
python-xtr/
├── packages/
│   └── xtr-<name>/
│       ├── src/xtr_<name>/
│       ├── tests/
│       ├── pyproject.toml
│       ├── README.md
│       └── LICENSE
├── pyproject.toml    # workspace root: members and sources, never published
└── uv.lock           # the only lockfile
```

## License

MIT — see [LICENSE](LICENSE). Every package ships the same license in its own directory.
