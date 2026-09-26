# AGENTS.md — building on the bookshop example

This directory is the reference application for the xtr packages. The repository's root
`AGENTS.md` applies here too; these rules add to it.

## Before you change anything

- Read `README.md` here: it maps every feature to the file that shows it, and lists the rules
  and known gaps. Copy the pattern from that file rather than inventing one.
- This is its own uv project. Work from `examples/bookshop`; never add it to the workspace, and
  never touch the root `pyproject.toml` or `uv.lock` for it.

## Rules

- Import only the public API of an `xtr_*` package — what its `__init__` exports, or a
  documented submodule (`<pkg>.bundle`, `<pkg>.config`, `xtr_clock.testing`,
  `xtr_dependency_injection.testing`, `xtr_dependency_injection.integration.wireup`). Never
  import a library an xtr package uses internally (`cyclopts`, `rich`, `msgspec`, `wireup`,
  `taskiq`). If something is missing, the package needs an API — say so; do not reach around it.
  The one exception is a plain-wireup application using `integration.wireup`, shown in
  `demo:wireup`.
- Libraries the application chooses for itself (`pydantic` messages, `pydantic-settings`
  through `DotenvSettings`) are fine.
- Register services with decorators in scanned modules; configure bundles with `@configure` in
  `bookshop/config/`; put new bundles' configs there too. Never build a bundle's service by
  hand when the bundle provides it.
- Anything read by the container at runtime — constructor, factory, hook, command and handler
  annotations, message fields, config fields — is imported for real, never under
  `TYPE_CHECKING`.
- In bundle configs, write a literal `%` as `%%`.
- Keep `demo:*` commands and `diagnostics/` in step with what they demonstrate: they are the
  executable proof of the README.

## Verify

```sh
uv run ruff check src && uv run ruff format --check src && uv run basedpyright && uv run ty check
uv run bookshop list && uv run bookshop di:show && uv run bookshop demo:errors
APP_ENV=prod uv run bookshop di:show && APP_ENV=test uv run bookshop list
```

There are no tests in this example on purpose: the commands above exercise it.
