# Add a package

The `xtr-recipes` tool adds a package to an application. It installs the
package, and then it applies the recipe of the package. A recipe can do these
tasks:

- Add the bundle of the package to `config/bundles.py`.
- Write a configuration file in `config/packages/`.
- Add environment variables to `.env`.
- Add lines to `.gitignore`.
- Add services to `compose.yaml`.

The recipe also shows the steps that it cannot do. You must do these steps.

## Before you start

- You have an application. If not, [create an application](new-application.md).
- The application has `xtr-recipes` in its `dev` dependencies. The `xtr-cli`
  templates add it.

## Procedure

1. Open a terminal in the directory of the application.
2. Add the package. This example adds `xtr-storage`:

   ```sh
   uv run xtr-recipes recipes:add xtr-storage
   ```

   The command installs the package and applies its recipe. It shows each file
   that it writes:

   ```text
   configure xtr-storage
     write src/shop/config/packages/storage.py
     write .gitignore
     bundle StorageBundle listed
     check:
       - shop debug:bundles — storage is listed and active
   ```

3. Read the output of the command. If the output has a `steps` list, do each
   step in the list.
4. Run the check that the output shows:

   ```sh
   uv run shop debug:bundles
   ```

   The table shows the bundle of the package with the state `active`.
5. Read the **Use in an application** section of the README of the package.
   This section tells you what the package needs, for example an environment
   variable or an extra.

## Add a package with an extra

Some packages have extras for third-party backends. Put the extra in the
requirement:

```sh
uv run xtr-recipes recipes:add "xtr-cache[redis]"
```

## Remove a package

1. Remove the package and undo its recipe:

   ```sh
   uv run xtr-recipes recipes:remove xtr-storage
   ```

2. If the output has a `steps` list, do each step in the list.
3. Run `uv run shop debug:bundles`. The bundle of the package is not in the
   table.

## If you added a package with uv add

`uv add` installs a package, but it does not apply the recipe. To apply the
recipes of all the direct dependencies, run this command:

```sh
uv run xtr-recipes recipes:sync
```

## Next step

Read [the application layout](application-layout.md), or select a
[guide](../guides/index.md).
