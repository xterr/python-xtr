<div align="center">

# xtr-maker

**Console commands that write application code for the xtr libraries.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

Every message, schedule, webhook, entity, command or listener starts as the same few files: a
class in the right folder, its imports, its decorator, a handler beside it. The `make:*`
commands write those files for you — named and placed the way the rest of the application is,
formatted the way the linter wants, and refused rather than overwritten when one already exists.

The makers themselves are still being written. What ships today is the generator they share:

- `ClassName` turns what a person types (`place order`, `ordering.PlaceOrder`) into a class
  name, a module and a file path under the folder for its kind.
- `ImportCollector` gathers the imports a file needs and writes them grouped and sorted.
- `TemplateRenderer` renders a template and refuses Python source that does not parse.
- `FileManager` finds the application package and writes files inside the project only.
- `Generator` queues the files to write and writes them all at once, refusing any that exists.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what removing it undoes.

- **Install** — `uv add --dev xtr-maker`: the makers write code while you develop, never in
  production.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate* step below: it lists
  `MakerBundle` for the `dev` environment.
- **Activate** — `MakerBundle: {"dev": True}` in `BUNDLES` in `<app>/config/bundles.py`, imported
  from `xtr_maker.bundle`.
- **Brings along** — the console bundle, and the messenger, scheduler, webhook, orm and event
  dispatcher bundles when their packages are installed.
- **Configure** — optional: with no configuration the code goes into the kernel's own package.
  `<app>/config/packages/maker.py`, a `@configure` function returning `MakerConfig`, picks
  another `root_package`, or turns off `final_classes`.
- **Environment** — nothing.
- **Ignore** — nothing: what the makers write is code to commit.
- **Remove** — drop the `BUNDLES` entry, delete `<app>/config/packages/maker.py`, then
  `uv remove --dev xtr-maker`. The code the makers wrote stays yours.
- **Check** — `debug:bundles` lists `maker` as active in `dev`.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-maker`; run the commands below from there. The `python-xtr-maker`
repository is a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync
uv run ruff check
uv run ruff format --check
uv run basedpyright
uv run ty check
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
