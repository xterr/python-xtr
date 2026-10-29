# Configure a bundle

Every bundle works with its default values. To change a value, the application
adds a configuration file for that bundle. The file holds a function with the
`@configure` decorator. The function returns the configuration object of the
bundle. The configuration of an application is Python code, so a type checker
reads it.

This guide configures the console bundle of the `shop` application.

## Before you start

- You have an application with the name `shop`. If not,
  [create an application](../setup/new-application.md).
- The bundle that you want to configure is active. `uv run shop debug:bundles`
  lists every active bundle.
- You know the configuration type of the bundle. The README of the package names
  the type under **Use in an application**.

## Procedure

1. Open a terminal in the directory of the application.
2. If the directory `src/shop/config/packages/` is absent, create it.
3. If the file `src/shop/config/packages/__init__.py` is absent, create it with
   this content:

   ```python
   """One configuration file for each bundle."""

   from __future__ import annotations

   __all__: list[str] = []
   ```

   The kernel scans an importable package only. Without this file the kernel
   finds no configuration file.
4. Read the configuration of the bundle as it is now:

   ```sh
   uv run shop debug:config console
   ```

   The output names each step of the resolution and the value after the last
   step:

   ```text
   console
   -------

   default
   ConsoleConfig(name=None, version=None, description=None, catch_exceptions=True)
   ```

5. Create the file `src/shop/config/packages/console.py` with a function that
   returns the configuration type of the bundle:

   ```python
   """The console: the name and the version that the help header shows."""

   from __future__ import annotations

   from xtr_console.bundle import ConsoleConfig
   from xtr_dependency_injection import configure

   __all__ = ["console"]


   @configure
   def console() -> ConsoleConfig:
       """The name and the version of the application."""
       return ConsoleConfig(name="shop", version="1.0.0")
   ```

6. Run a command of the application:

   ```sh
   uv run shop list
   ```

   The first line of the output is now `shop 1.0.0`.

> [!NOTE]
> A function without a parameter is a base provider. Its value replaces the
> default value of the bundle. One bundle permits one base provider in the
> application.

## Change one field and keep the others

A function with one parameter is a transform provider. The kernel gives it the
value of the step before, and the function returns a new value. Use
`dataclasses.replace` to change one field of a frozen dataclass.

1. Add a second function to `src/shop/config/packages/console.py`:

   ```python
   from dataclasses import replace


   @configure
   def console_description(config: ConsoleConfig) -> ConsoleConfig:
       """The line under the name in the help header."""
       return replace(config, description="The console of the shop")
   ```

2. Add the name of the function to `__all__`:

   ```python
   __all__ = ["console", "console_description"]
   ```

3. Run `uv run shop list`. The third line of the output is the description.

## Configure one environment only

The kernel builds for one environment. It reads the name of the environment from
the `APP_ENV` variable, and `dev` is the default. The `@when` and `@when_not`
decorators limit a provider to the environments that you name.

1. Add a provider with the `@when` decorator under `@configure`:

   ```python
   from xtr_dependency_injection import configure, when


   @configure
   @when("prod")
   def console_prod(config: ConsoleConfig) -> ConsoleConfig:
       """In `prod`, let an exception leave the command."""
       return replace(config, catch_exceptions=False)
   ```

2. Add `console_prod` to `__all__`.
3. Read the configuration of the `dev` environment:

   ```sh
   uv run shop debug:config console
   ```

   The steps of the output have no `console_prod`.
4. Read the configuration of the `prod` environment:

   ```sh
   APP_ENV=prod uv run shop debug:config console
   ```

   The last step of the output is now `transform ...:console_prod`.

> [!NOTE]
> The `allowed_envs` argument of the kernel lists the environments that the
> application permits. The kernel refuses every other name.

## Read a value from an environment variable

`env()` returns a placeholder, not a value. The container reads the variable
when it builds a service that needs the value. Therefore the container compiles
on a machine that has no value for the variable.

1. Use `env()` as the value of a field:

   ```python
   from xtr_dependency_injection import configure, env


   @configure
   def console_from_env(config: ConsoleConfig) -> ConsoleConfig:
       """The description comes from `SHOP_DESCRIPTION`."""
       return replace(
           config,
           description=env("SHOP_DESCRIPTION", default="The console of the shop"),
       )
   ```

2. Add the variable to the `.env` file of the application:

   ```sh
   SHOP_DESCRIPTION=The console of the shop, in development
   ```

3. Run `uv run shop debug:config console`. The value of the field is
   `env(SHOP_DESCRIPTION)`, not the text of the variable.

The second argument of `env()` converts the text of the variable:

| Written | The field receives |
|---|---|
| `env("SMTP_HOST")` | the text of the variable |
| `env("SMTP_PORT", int)` | an integer, or an error for other text |
| `env("MAIL_DEBUG", bool)` | true for `1`, `true`, `yes`, `on` or a number that is not zero |
| `env("SMTP_PORT", int, default=25)` | `25` when the variable has no value |
| `env("json:file:OPTIONS_FILE")` | the JSON content of the file that the variable names |

> [!WARNING]
> Keep a password, a key or another secret in `.env.local`, not in `.env`. Git
> tracks `.env`, and `.gitignore` excludes `.env.local`.

## Check the configuration

1. Read the configuration of every bundle:

   ```sh
   uv run shop debug:config
   ```

2. Read the configuration of one bundle:

   ```sh
   uv run shop debug:config console
   ```

   The line under the name of the bundle shows the steps of the resolution. The
   kernel resolves the value in this sequence:

   | Step | Source |
   |---|---|
   | 1 | the default value of the configuration type |
   | 2 | the base provider of the application |
   | 3 | a field that another bundle forwards with `AliasOf` |
   | 4 | the changes of other bundles, in the sequence of the bundles |
   | 5 | the transform providers of the application |

3. If `debug:config` reports no provider of yours, read step 3 of the procedure
   again. A directory without `__init__.py` holds no module that the kernel
   finds.

## Next step

- [Add a console command](console-commands.md) shows how to write a command.
- [The application layout](../setup/application-layout.md) describes the other
  files of an application.
- [Add a package](../setup/add-a-package.md) shows how a recipe writes a
  configuration file for you.
- The README of
  [xtr-dependency-injection](https://github.com/xterr/python-xtr/tree/main/packages/xtr-dependency-injection)
  describes parameters, placeholders and the resolution of a configuration.
- The [API reference](https://xterr.github.io/python-xtr/api/xtr_dependency_injection/)
  documents `configure`, `when` and `env`.
