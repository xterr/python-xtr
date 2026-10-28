<div align="center">

# xtr-cli

**A new xtr application — a console application or a web application — ready to run in one command, and served in another.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

An application on the xtr packages starts the same way every time: a project manifest, a kernel,
an entry point that loads the environment and runs the console, a web entry point that serves
the application from the same kernel. Then each package's *Use in an application* steps — the
bundle list, the configuration files, the `.env` and ignore lines.

The packages already describe their own steps as recipes, which
[xtr-recipes](../xtr-recipes) applies. So this tool writes only what no recipe can — the
manifest, the kernel and the entry points — installs the packages with `uv`, and lets each
package's recipe configure itself. The project it leaves boots, passes its own tests, and is
already in the state `recipes:sync --check` expects.

## Install

Nothing to install: run it with `uvx`.

```sh
uvx xtr-cli new shop
```

Or install it once, and call it `xtr`:

```sh
uv tool install xtr-cli
xtr new shop
```

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/) on the `PATH`, and `git` unless
`--no-git` is given.

## Quick start

```console
$ uvx xtr-cli new shop --webapp

shop — the webapp template
--------------------------

 • directory: /home/ada/shop
 • python:    3.13

write pyproject.toml
…
run   uv add -- 'xtr-dependency-injection>=5.0,<6' …
run   uv add --dev -- 'xtr-recipes>=5.0,<6' pytest httpx ruff basedpyright ty
run   uv run xtr-recipes recipes:sync
run   git init --quiet

 [OK] shop is ready in /home/ada/shop
```

```sh
cd shop
uv run shop-web             # serve it
uv run shop debug:bundles   # what is active
uv run pytest
```

## Commands

```sh
xtr project:new <directory> [options]   # alias: new — into a new or empty directory
xtr project:init [options]              # alias: init — into the current directory
xtr server:start [options]              # alias: serve — run the project's web application
```

| Option | Default | |
|---|---|---|
| `--webapp` | | a web application rather than a console application — see [Templates](#templates) |
| `--name` | the directory's name | the distribution and console script; dashes become underscores for the import package |
| `--python` | the Python running this tool | the `3.<minor>` the project is pinned to; 3.11 or later |
| `--no-git` | | do not run `git init`; `init` never re-initialises an existing repository |
| `--dry-run` | | print every file and command, and write nothing |
| `--local-packages` | | install the xtr packages, editable, from a directory of their sources |

**Nothing is asked.** Every option has a default, so the same command line makes the same project
at a terminal, in a script or in CI. More packages are added afterwards, from inside the project,
with `uv run xtr-recipes recipes:add <package>`.

The directory must be missing, or hold nothing but `.git` and editor metadata: nothing is ever
written over. A name that would not import — a keyword, a module of the standard library — is
refused before anything is written.

### What it runs

1. Writes the template's files.
2. `uv add` the template's packages; every unversioned xtr requirement is pinned to this tool's
   major version, so the files and the packages are from the same release.
3. `uv add --dev` the tools: `xtr-recipes`, `pytest`, `ruff`, `basedpyright`, `ty`.
4. `uv run xtr-recipes recipes:sync` — each package's recipe writes `<app>/config/bundles.py`, its
   configuration files, its `.env` and `.gitignore` blocks, and `xtr.lock`; the steps it cannot
   make are printed.
5. `git init`; nothing is committed.

A step that fails stops the run; what was made so far is left in place, and the error names the
command to run by hand.

### Serving

```sh
cd shop
uvx xtr-cli serve                       # or `xtr serve` once installed
uvx xtr-cli serve --port 9000 --no-reload
```

`serve` finds the project — the nearest `pyproject.toml` at or above the current directory, or
`--project-dir` — and its web entry point, then runs it in the project's own environment with
`uv run`. The server restarts on every source change; `--no-reload` turns that off.

| Option | Default | |
|---|---|---|
| `--project-dir` | the nearest project | the project to serve |
| `--entrypoint` | found in the project | a console script, or an ASGI application as `module:attribute` |
| `--host` | the entry point's own | where to listen |
| `--port` | the entry point's own | the port to listen on |
| `--reload` / `--no-reload` | `--reload` | restart on every source change |
| `--dry-run` | | print the command, and run nothing |

The web entry point is found by reading the project's files, never by importing them:

1. **A web console script** — a `[project.scripts]` entry whose module imports `uvicorn`,
   `hypercorn` or `granian`, or whose name ends in `-web` or `-server`. It is run as it is, so
   whatever it does before serving — loading the `.env` files, for one — still happens. The host,
   the port and reloading reach it as `WEB_HOST`, `WEB_PORT` and `WEB_RELOAD=1`, which the
   `webapp` template's `<name>-web` reads.
2. **An ASGI application** — only when there is no such script: a module-level
   `FastAPI()`, `Starlette()` or `Litestar()`, handed to `uv run uvicorn module:attribute`, on
   `127.0.0.1:8000` unless told otherwise. `uvicorn` must be installed in the project, and
   nothing the application does at startup outside that module runs.

Several candidates are offered to choose from; with `-n` the command fails and lists them for
`--entrypoint`. Ctrl-C stops the server and waits for it to finish shutting down, so the
application's shutdown hooks run.

## Templates

| Template | Made by | Packages | Scripts |
|---|---|---|---|
| `cli` | `xtr new <directory>` | `xtr-dependency-injection`, `xtr-console`, `xtr-dotenv` | `<name>` |
| `webapp` | `xtr new <directory> --webapp` | the same, and `xtr-logging`, `xtr-http-kernel`, `xtr-orm[postgres]`, `xtr-messenger[amqp]`, `xtr-http-client`, `xtr-notifier`, `xtr-security`, `fastapi`, `uvicorn` | `<name>`, `<name>-web` |

Both write `pyproject.toml` (with ruff, basedpyright, ty and pytest configured), `.python-version`,
`.gitignore`, `README.md`, `src/<app>/kernel.py`, `src/<app>/__main__.py`, an example
`app:hello` command and a test that builds the kernel. `webapp` adds `src/<app>/web/` — the
FastAPI application served with `setup(app, kernel)`, its routes and a uvicorn entry point — a
kernel built with `concurrent_scoped_access=True` for the security bundle, and a test that
requests the home page.

Each package's recipe configures it: the `webapp` project starts with a `compose.yaml` running
PostgreSQL — published on `5432` by `compose.override.yaml` — that `DATABASE_URL` points at,
`MESSENGER_DSN` pointing at a RabbitMQ on this machine, and both notifier DSNs at `null://null`.
Nothing connects until it is used, so the project boots and passes its tests with neither
running. Every other package — `xtr-cache`, `xtr-scheduler`, `xtr-security-jwt` — is a
`recipes:add` away.

## Errors

Everything this library raises derives from `CliError`, and carries what went wrong as typed
attributes. A command reports it and exits `1`.

| Error | Raised when |
|---|---|
| `DirectoryNotEmptyError` | the directory is a file, or holds anything but version-control and editor metadata |
| `AmbiguousWebEntryPointError` | `serve` found several web entry points, and no question may be asked |
| `InvalidProjectNameError` | the name normalises to nothing, or to a keyword, a non-identifier or a standard-library module |
| `InvalidTemplateError` | a shipped `template.toml` does not parse, holds an unknown key, names a missing file, or a placeholder is unknown |
| `ProjectNotFoundError` | `serve` was run outside a project |
| `StepFailedError` | `uv` or `git` exited with a failure; the later steps were not run |
| `UnknownTemplateError` | `TemplateCatalog.load` is given a name no template ships under |
| `UnsupportedPythonError` | `--python` is not `3.<minor>` with a minor of 11 or more |
| `WebEntryPointNotFoundError` | the project has nothing to serve, or `--entrypoint` names nothing it has |

## Layout

```
xtr_cli/
├── command/                 project:new, project:init and server:start
├── command_support.py       what both commands share: settings, plan, apply, report
├── project_name.py          the distribution and import names
├── project_settings.py      everything decided about the project
├── template.py              a template.toml and its files
├── template_catalog.py      the shipped templates
├── scaffolder.py            settings into a plan, a plan into a project
├── scaffold_plan.py         the files and commands, before anything is made
├── web_entry_point.py       what serves an application, and the command starting it
├── web_entry_point_finder.py the project around a directory, and its web entry point
├── subprocess_runner.py     uv, git and the server, run as real processes
├── templates/               cli/ and webapp/
└── exception/               CliError, the root of everything this library raises
```

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-cli`; run the commands below from there.

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

`tests/integration/test_scaffold.py` makes each template for real, from the working tree's
packages, and runs the project's own checks and commands. It needs `uv` and the network for the
third-party packages, and is skipped unless `XTR_CLI_SCAFFOLD=1` is set.

## License

MIT — see [LICENSE](LICENSE).
