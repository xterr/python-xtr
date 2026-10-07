---
name: xtr-recipes
description: How to add, configure and remove xtr packages in an application with the recipes:* commands instead of editing bundles.py, config files, .env and .gitignore by hand. Use when adding or removing an xtr dependency, when a package's use-in-an-application steps need applying, when bundles.py or a config/<name>.py is missing or drifted, when wiring the recipes:sync --check gate into CI, or when shipping a recipe beside a new bundle.
---

# xtr-recipes

Adding a package to an application is a short list of chores — list its bundle, write a config
file, set an environment variable, add an ignore line — that every package already describes in
its *Use in an application* section. A recipe is that description made declarative and shipped
beside the package, so `recipes:sync` does the chores and, read backwards, undoes them on removal.
It is a developer and CI tool, so install it as a dev dependency.

## Quick reference

- Install once: `uv add --dev xtr-recipes`.
- Add a package and apply its recipe: `uv run xtr-recipes recipes:add "xtr-messenger[di,console]"`.
- After a plain `uv add`, catch up with: `uv run xtr-recipes recipes:sync`.
- Remove a package and undo its recipe: `uv run xtr-recipes recipes:remove xtr-messenger`.
- See what is configured and what a sync would do: `uv run xtr-recipes recipes:show`.
- Read one recipe in full: `uv run xtr-recipes recipes:show xtr-messenger`.
- Restore a config file you deleted: `uv run xtr-recipes recipes:install xtr-messenger`.
- Guard it in CI: `uv run xtr-recipes recipes:sync --check` (exit 1 when anything drifted).
- A recipe only writes bundles, files, env and ignore lines, and prints notes. It runs no recipe
  step and no template; the only code it imports is the bundle class a recipe lists, and only from
  a module under that package's own import package, to read its requirements. It never edits your
  application code; the notes tell you the steps it cannot take.

## Add, sync and remove a package

```sh
# add the dependency and apply whatever recipe arrived with it, in one step
uv run xtr-recipes recipes:add "xtr-messenger[di,console]"

# or, if you already ran `uv add`, bring the project in line
uv run xtr-recipes recipes:sync

# undo everything the recipe wrote, then drop the dependency
uv run xtr-recipes recipes:remove xtr-messenger
```

`recipes:add` runs `uv add` then syncs as a fresh process; `recipes:remove` runs `uv remove` then
syncs. Both read only the project's direct dependencies (`[project].dependencies`), so a transitive
package is never configured on its own. A sync **configures** a new dependency, **updates** one
whose recipe changed, and **unconfigures** one no longer depended on, recording each in the
committed `xtr.lock`. Read the plan before trusting it:

```sh
uv run xtr-recipes recipes:sync --dry-run
```

## Read what is configured

```sh
uv run xtr-recipes recipes:show
```

```console
 Package        State
 xtr-clock      locked
 xtr-messenger  not configured
 xtr-orm        outdated
```

`locked` is applied and current, `not configured` would be configured by a sync, `outdated` has a
changed recipe, `removed` is locked but no longer depended on, and `skipped: install <package>[di]`
means the package is installed without the extra that ships its bundle class. Name a package to see
its bundles, files, env keys, ignore lines and notes as the recipe ships them.

## When a bundle is not listed

A recipe's bundle is left out of `bundles.py` when another listed bundle already requires it, so
depending on `xtr-clock` while `xtr-logging` is active lists no `ClockBundle` — the lock records it
`required`. This is recomputed every sync, so removing the requiring bundle lists it again. A
requirer limited to some environments does not count, so its peers are still listed. A bundle
whose class cannot be imported (installed without the `di` extra) is skipped with the extra
named, and the package is retried next sync; one already configured is left as the lock has it.

## Files you have edited

A sync never overwrites a config file you changed after the recipe wrote it: the new content goes
to `<file>.new` beside it and is reported. To take the recipe's version instead:

```sh
uv run xtr-recipes recipes:install xtr-messenger --force
```

`recipes:install` without `--force` re-applies one recipe and keeps your edits — the way to restore
a file that went missing, which a sync skips because the recipe is unchanged.

Removing a package moves an edited or adopted config file to `<file>.removed`: left in place it
would still import the removed package and stop the application loading. Delete it, or keep what
you need from it.

## Testing

Run the drift gate in CI; it writes nothing and fails when the lock, bundle list, config files,
`.env` or `.gitignore` no longer match the installed recipes:

```sh
uv run xtr-recipes recipes:sync --check
```

A clean project prints `recipes are in sync` and exits 0.

## Use in an application

1. **Install** — `uv add --dev xtr-recipes`.
2. **Configure the project** — the application package is `[project].name` normalised to an import
   name, or set `[tool.xtr-recipes] app = "<import name>"`; it must resolve to `src/<app>/` or
   `<app>/`.
3. **Add packages through it** — `uv run xtr-recipes recipes:add "<requirement>"`, then do the
   steps it prints under `steps`, and confirm with `debug:bundles`.
4. **Commit** `xtr.lock` alongside `bundles.py` and the generated config files.
5. **Guard** — add `uv run xtr-recipes recipes:sync --check` to CI.

There is no bundle to activate: `xtr-recipes` is a standalone console application, not wired into
the application's kernel, because the application may not build before or after a recipe runs.

## Errors

Every error derives from `RecipesError` and names the package and the key or file at fault:

- `ProjectNotFoundError` — no `pyproject.toml` at or above the directory, or the application
  package resolves to neither `src/<app>/` nor `<app>/`; it names the setting the app name came
  from.
- `InvalidManifestError` — a recipe's `manifest.toml` has an unknown table or key, a malformed
  `"<module>:<Class>"` target, a value of the wrong type, or a template with an unknown placeholder.
- `BundlesNotEditableError` — `bundles.py` was not written in the form the tool can read back; it
  prints the entries to add by hand.
- `RecipeNotInstalledError` — the named package is not one a command can work on. `recipes:install`
  raises it for a package that is not a direct dependency or ships no recipe; `recipes:show` only
  when the lock has no entry for it either, because a locked package is read from the lock.
- `UnsafePathError` — a path in `xtr.lock` is absolute, climbs out with `..` or is spelled with
  backslashes, or a file a recipe is about to write is a symbolic link; it is refused before
  anything is written or deleted. A `[files]` destination shaped the same way is an
  `InvalidManifestError` instead, because the manifest is where it was declared.
- `UnreadableFileError` — `pyproject.toml` is not valid TOML, or `xtr.lock` is not valid JSON;
  it names the file and what was wrong with it.

## Do not

- Do not hand-edit `bundles.py` into a shape the tool cannot read: keep `BUNDLES` a literal mapping
  of imported bundle classes to literal flag mappings.
- Do not hand-edit the `# >>> xtr-<name>` … `# <<< xtr-<name>` blocks in `.env` or `.gitignore`;
  lines outside them are yours and are left alone.
- Do not expect a recipe to edit application code — a `setup(app, kernel)` call, a middleware list,
  a firewall's authenticators are printed as `steps` for you to make.
- Do not add `xtr-recipes` as a runtime dependency or a bundle; it is a dev tool.
- Do not forget to commit `xtr.lock`; `recipes:sync --check` in CI depends on it.
