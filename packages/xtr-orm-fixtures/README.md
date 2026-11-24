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
