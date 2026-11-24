<div align="center">

# xtr-orm-fixtures

**Seed a database from fixture classes: ordered, grouped and sharing references, loaded in one
transaction after an emptying in foreign-key order.**

</div>

---

A development-only package: install it in the dev dependency group, never as a runtime
dependency.

This package is being built. Its fixtures, loader, purgers, executors, console command and bundle
arrive in the commits that follow; this README grows with them.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what removing
it undoes.

- **Install** — `uv run xtr-recipes recipes:add --dev xtr-orm-fixtures`, or
  `uv add --dev xtr-orm-fixtures` then `uv run xtr-recipes recipes:sync`: fixtures seed
  development and test databases, so the package is a development dependency. The database
  driver is [xtr-orm](../xtr-orm)'s to bring, through its `postgres`, `sqlite` or `mysql` extra.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate* step below, and only that: it
  lists `OrmFixturesBundle` for `dev` and `test`, which is what this package's recipe declares.
  There is nothing for it to configure, no variable to write and nothing to ignore.
- **Activate** — import the bundle at the top of `<app>/config/bundles.py`, like every other one,
  and list it for `dev` and `test`:

  ```python
  # <app>/config/bundles.py
  from xtr_orm_fixtures.bundle import OrmFixturesBundle

  BUNDLES = {
      OrmFixturesBundle: {"dev": True, "test": True},
  }
  ```

  Production still starts without the development dependencies installed: there the kernel
  stands in for the bundle, which is not active, and sets aside every application module that
  needs this package or a library only development installs — see
  [Development-only packages](../xtr-dependency-injection/README.md#development-only-packages).
  To seed production as well — reference data, loaded with `--group` — install the package as a
  runtime dependency instead (`uv add xtr-orm-fixtures`) and list the bundle `{"all": True}`.
- **Brings along** — the orm bundle, which it requires. The console bundle is read, not required:
  `orm:fixtures:load` is registered when it is active.
- **Configure** — nothing: fixtures are found wherever the application keeps them, and what is
  emptied is each connection's table definitions, as its migrations see them. A purger factory of
  the application's joins under the name it gives, with
  `@as_alias(PurgerFactoryInterface, qualifier="mine")`; in a module production imports too, keep
  it to the environments the bundle runs in with `@when("dev", "test")`.
- **Environment** — nothing.
- **Ignore** — nothing: fixtures are code to commit.
- **Remove** — `uv run xtr-recipes recipes:remove xtr-orm-fixtures`: it runs
  `uv remove --dev xtr-orm-fixtures`, and the sync after it drops the `BUNDLES` entry. Delete the
  fixture classes, which no longer import.
- **Check** — `debug:bundles` lists `orm_fixtures` as active in `dev`;
  `orm:fixtures:load --dry-run` loads every fixture and rolls it all back.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-orm-fixtures`; run the commands below from there. The `python-xtr-orm-fixtures`
repository is a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
