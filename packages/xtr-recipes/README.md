<div align="center">

# xtr-recipes

**Applies a package's use-in-an-application steps to a project, and undoes them when the package goes away.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

Adding a package to an application is a short list of chores: list its bundle, write a
configuration file, set an environment variable, add an ignore line. Every package already
describes that list in its *Use in an application* section. A recipe is that description made
declarative, shipped beside the package, so one command does the chores — and, read backwards,
undoes them when the package is removed.

A recipe is declarative only: bundles to list, files to write, environment and ignore lines to
add, and notes to print. No recipe step and no template is ever executed. The one thing imported
is the bundle class a recipe lists — and only from a module under the declaring distribution's own
import package, never an arbitrary module a manifest names — so its `@required_bundle` declarations
can be read to decide whether listing it is redundant; nothing else a dependency ships is imported
or run. Because applying a recipe is a diff against a committed lock file, it does not matter how a
package arrived, and running it twice changes nothing the second time.

## Install

```sh
uv add --dev xtr-recipes
```

Requires Python 3.11+. It depends on [xtr-console](../xtr-console) for its command line and on
[xtr-dependency-injection](../xtr-dependency-injection) to read an application's bundle list. It
installs no runtime weight into the application: it is a tool a developer and a CI job run, not
a dependency the application boots.

## Commands

Each command reads the project at `--project-dir`, defaulting to the nearest directory at or
above the current one that holds a `pyproject.toml`. The application package is
`[tool.xtr-recipes] app` when set, otherwise `[project].name` normalised to an import name; it
must resolve to `src/<app>/` or `<app>/`, or the command stops with a `ProjectNotFoundError`
naming the setting.

```sh
uv run xtr-recipes recipes:sync                    # configure new, update changed, undo removed
uv run xtr-recipes recipes:sync --check            # exit 1 if a sync would change anything (CI); writes nothing
uv run xtr-recipes recipes:sync --dry-run          # print what it would do; writes nothing
uv run xtr-recipes recipes:show [<package>]        # the project's recipes, or one recipe in full
uv run xtr-recipes recipes:install <package> [--force]   # re-apply one; --force overwrites edited files
uv run xtr-recipes recipes:add <requirement>       # uv add <requirement>, then sync afresh
uv run xtr-recipes recipes:remove <package>        # uv remove <package>, then sync afresh
```

### `recipes:sync`

The whole run is planned before any of it is carried out, so three ways of asking share one code
path. The default prints the plan and applies it; `--dry-run` prints it and stops; `--check`
writes nothing and exits non-zero when the plan would change the project, which is what a
continuous integration job asks. A plan made only of headings, kept files and bundle notes has
something to say and nothing to do, so `--check` passes on it.

A sync does three things to the recipes of the project's direct dependencies
(`[project].dependencies` only; dependency groups are left out, and so is a transitive package
the application did not choose):

- **configure** a dependency not yet in the lock — write its files, add its env and ignore
  blocks, list its bundle, print its notes;
- **update** a dependency whose recipe changed since the lock — re-render its files, apply the
  bundle, env and ignore differences;
- **unconfigure** a locked package no longer depended on — delete the files it wrote, move an
  edited or adopted one to `<file>.removed`, clear its blocks, remove its bundle entry, drop its
  lock entry.

A plan reads as one block per package, under a heading naming the action:

```console
configure xtr-messenger
  write src/bookshop/config/messenger.py
  write .env
  bundle MessengerBundle listed
  steps:
    - Name the transports in config/messenger.py and route your messages to them: a message routed nowhere is neither sent nor handled.
  check:
    - bookshop debug:bundles — messenger is listed and active
    - bookshop debug:config messenger — the resolved transports and routing
  run:
    - bookshop messenger:consume <transport>
write src/bookshop/bundles.py
write xtr.lock
```

The bundle list and the lock belong to the whole run — each written once, or deleted once when
nothing is left to put in it — so they are the only unindented steps besides the headings.

### `recipes:show`

Writes nothing. Named without a package it lists every recipe the project has something to say
about, with its standing — `locked`, `not configured`, `outdated`, `removed`, or
`skipped: install <package>[di]` for a package installed without the extra that ships its bundle
class. Named with a package it prints that one recipe in full: its bundles, files, env keys,
ignore lines and notes, exactly as the recipe ships them.

A package the project no longer installs but the lock still records — removed from the
dependencies and not yet synced away — is read from the lock instead: its recorded bundles, files,
env keys and ignore lines, so what a sync is about to undo can still be inspected. Only a package
with neither an installed recipe nor a lock entry is a `RecipeNotInstalledError`.

### `recipes:install`

Re-applies one package's recipe unconditionally and leaves the rest of the lock alone — the way
to restore a config file that went missing, which a sync would skip because the recipe is
unchanged. By default a file you have edited is left in place and the new content is written
beside it as `<file>.new`; `--force` overwrites the file instead.

### `recipes:add` / `recipes:remove`

Convenience over two steps: `recipes:add` runs `uv add <requirement>` then syncs; `recipes:remove`
runs `uv remove <package>` then syncs. `uv` is found on `PATH` and run in the project directory;
a non-zero exit from it stops before the sync. The sync runs as a fresh process
(`uv run xtr-recipes recipes:sync`), because installing or removing has changed the environment
under the running interpreter.

## The manifest

A recipe lives in the package that ships the bundle, at `src/xtr_<name>/recipe/`, versioned with
it. `recipe/` is a real package (an `__init__.py` with a docstring and `__all__: list[str] = []`),
so `uv build` puts its `manifest.toml` and `files/` tree in the wheel. The manifest is TOML, read
with `tomllib`:

```toml
[bundles]
# "<module>:<Class>" = the environment flags it is listed with, exactly as in BUNDLES.
"xtr_messenger.bundle:MessengerBundle" = { all = true }

[files]
# destination under the application package = template under recipe/
"config/messenger.py" = "files/config/messenger.py.tmpl"

[env]
# written only when the key is absent from .env; "" means no default, so it is written commented out
MESSENGER_DSN = ""

[gitignore]
lines = []

[notes]
steps = []
check = ["<script> debug:bundles — messenger is listed and active"]
run   = ["<script> messenger:consume <transport>"]
```

- Every table is optional. An unknown table or key, a malformed `"<module>:<Class>"` target, or a
  value of the wrong type raises `InvalidManifestError` naming the package and the key at fault.
- Templates are named `*.tmpl` so a file still holding placeholders is not imported, linted or
  type-checked as part of the package. A template substitutes `${app}` — the application import
  name — with `string.Template.substitute`; an unknown placeholder is an error, and a literal `$`
  is written `$$`.
- A `<script>` token in a note is replaced with the application's first `[project.scripts]` name,
  so a printed check reads as a command you can actually run; with no script declared the token is
  left as it is.
- The three note lists stay apart because they are acted on differently: `steps` are changes to
  application code a declarative recipe cannot make, `check` shows the package working, `run` puts
  it to work. Notes are printed after a recipe is applied and never written to disk.
- A destination under `config/` also ensures `<app>/config/__init__.py` exists (a docstring and
  `__all__: list[str] = []`), created if missing, adopted if present, never deleted.

Recipes are discovered through the `xtr_recipes` entry-point group, named after the bundle, the
same way bundles are found through `xtr_dependency_injection.bundles`:

```toml
[project.entry-points."xtr_recipes"]
messenger = "xtr_messenger.recipe"
```

## The lock

`xtr.lock` sits in the project root, is committed, and is the record of what each recipe applied —
enough on its own to undo a recipe after `uv remove`, so it stores paths relative to the project
directory, `/`-separated. It is JSON with sorted keys, two-space indent and a trailing newline, so
it diffs cleanly; a sync rewrites it only when it actually changed.

```json
{
  "xtr-messenger": {
    "recipe": "<sha256>",
    "bundles": {"xtr_messenger.bundle:MessengerBundle": "listed"},
    "files": {"src/bookshop/config/messenger.py": {"sha256": "…", "adopted": false}},
    "env": ["MESSENGER_DSN"],
    "gitignore": []
  }
}
```

- `recipe` is a sha256 over the manifest and every template in sorted path order — not the package
  version. Every package shares one version, so hashing the content is what keeps a release bump
  from "updating" every recipe and churning the lock. A sync re-applies a recipe only when this
  hash moves.
- A bundle's state is `listed` when the sync added it, `adopted` when it was already in `BUNDLES`,
  or `required` when another listed bundle requires it so the sync leaves it out.
- `files` records each written file's hash and whether it was adopted. The hash tells an untouched
  file from one you have since edited; an adopted file is one that was already there when the
  recipe first ran and so is never deleted on removal.
- `env` and `gitignore` hold only the keys and lines the sync wrote inside its own marked block.
  A key or line that was already set outside the block is adopted, is not recorded, and is never
  removed.

## Bundles, env and ignore

`<app>/bundles.py` is regenerated, not patched. It is read with the standard library's `ast`:
each `from <module> import <Class>` maps a name, and the single `BUNDLES = {...}` assignment gives
the ordered entries with their flags from `ast.literal_eval`. A `BUNDLES` built any other way, a
key that is not an imported name, non-literal flags, or any statement besides the docstring,
imports, `__all__` and `BUNDLES` raises `BundlesNotEditableError` rather than deleting it. The file
is rewritten in a canonical form — the docstring exactly as written,
`from __future__ import annotations`, one import per entry in import order, `__all__ = ["BUNDLES"]`,
and the `BUNDLES` mapping — that passes `ruff check` and `ruff format --check`; an unchanged entry
set leaves the file alone. Comments on entries are not kept.

A recipe's bundle is **left out when another bundle in the final list requires it**, transitively,
hard or soft, through the `@required_bundle` declarations
[xtr-dependency-injection](../xtr-dependency-injection) reads. This is recomputed every sync, so a
bundle recorded as `required` becomes `listed` again once the bundle that required it is removed.
Only a requirer listed for every environment counts: one limited to `dev` and `test` would leave
its peers inactive in `prod`, so the recipe's bundle is listed anyway.
A bundle whose class cannot be imported — the package was installed without the `di` extra — is
skipped with a message naming the extra; the package is not locked, so the next sync retries once
the extra is installed. A package already configured whose bundle stops importing is left exactly
as the lock has it — a broken installation is no reason to undo what was applied.

Environment variables and ignore lines are written as marked blocks in the project's `.env` and
`.gitignore`:

```
# >>> xtr-messenger
# MESSENGER_DSN=
# <<< xtr-messenger
```

An env key with no default is written commented out, so the variable stays unset rather than being
set to the empty string — the difference between a clear "not set" error at boot and a value that
is silently wrong. A value you fill in inside the block is kept when the recipe is applied again.
Removing a package deletes its whole block and nothing else.

## Adoption

The first sync of an existing project changes as little as it can. A bundle already in `BUNDLES`,
a config file already on disk, an env key already assigned, an ignore line already present is
recorded as adopted and left untouched. An adopted file is never overwritten by a later update and
never deleted on removal; an adopted env key or ignore line is never recorded and so never cleared.
When its package is removed, an edited or adopted config file still imports that package, so it is
renamed to `<file>.removed` (`.removed.1` and on when one is already there): the application keeps
loading, and your content is kept for you to delete or reuse.
A file you edit after the recipe wrote it is recognised by its hash: an update writes the new
content to `<file>.new` beside it and reports it, rather than overwriting your work. Use
`recipes:install <package> --force` to take the recipe's version instead.

## In continuous integration

Run `recipes:sync --check` in CI. It writes nothing and exits non-zero when the committed
`xtr.lock`, bundle list, config files, `.env` or `.gitignore` have drifted from what the installed
recipes would produce — the sign that someone added a dependency without syncing, or edited a
generated file by hand.

```sh
uv run xtr-recipes recipes:sync --check
```

## Shipping a recipe

A package that ships a bundle ships a recipe beside it. Add `recipe/__init__.py`, a
`recipe/manifest.toml`, any templates under `recipe/files/`, and the entry point:

```toml
[project.entry-points."xtr_recipes"]
<name> = "xtr_<name>.recipe"
```

Fill the manifest from the package's README *Use in an application* section, and nothing invented:
`[bundles]` from *Activate*, `[files]` from *Configure* (only when the README names an
`<app>/config/<name>.py` the application needs — a zero-config bundle ships no file), `[env]` from
*Environment*, `[gitignore]` from *Ignore*, and `[notes]` from the code changes, *Check* and *Run*
the recipe cannot do itself. The root repository test checks that every package advertising a
bundle also advertises a recipe of the same name, that its manifest parses, that each listed
bundle is one the package advertises, and that every template exists.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-recipes`; run the commands below from there.

```sh
uv sync --all-extras
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
