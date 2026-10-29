# Add a console command

A command is a function or a class with the `@as_command` decorator. The
decorator gives the command a name, and the signature of the command is its
command line. The kernel finds a command when it scans the application package.
The commands of an application live in `src/shop/command/`.

This guide adds commands to the `shop` application.

## Before you start

- You have an application with the name `shop`. If not,
  [create an application](../setup/new-application.md).
- The console bundle is active. `uv run shop debug:bundles` shows `console` with
  the state `active`.
- The application has a console script. `pyproject.toml` holds the line
  `shop = "shop.__main__:main"` under `[project.scripts]`.

## Procedure

1. Open a terminal in the directory of the application.
2. Create the file `src/shop/command/import_orders_command.py` with this
   content:

   ```python
   """``order:import``: read the orders of a file."""

   from __future__ import annotations

   from pathlib import Path

   from xtr_console import ConsoleStyle, ExitCode, as_command, escape

   __all__ = ["import_orders"]


   @as_command("order:import")
   async def import_orders(io: ConsoleStyle, source: Path) -> int:
       """Import the orders of a file.

       Args:
           io: Where the command writes.
           source: The file to read.
       """
       io.success(f"Read {escape(str(source))}")
       return ExitCode.SUCCESS
   ```

3. Run the command with a file:

   ```sh
   uv run shop order:import orders.csv
   ```

   The command writes `[OK] Read orders.csv`.
4. Read the help of the command:

   ```sh
   uv run shop order:import --help
   ```

   The first line of the docstring is the description. The `Args:` section gives
   the description of each argument and each option.

> [!NOTE]
> The kernel imports every module under `src/shop/`, so the decorator registers
> the command. A module of a command never imports the application.

## Give the command a short name

The `@as_command` decorator takes a name and aliases. The part of the name
before the first colon is the namespace of the command.

1. Add one alias, or a tuple of aliases:

   ```python
   @as_command("order:import", aliases="oi")
   ```

2. Run the command under the alias:

   ```sh
   uv run shop oi orders.csv
   ```

> [!NOTE]
> A name without a colon has no namespace. A name that starts with `-`, or that
> holds a space, raises `InvalidCommandNameError`.

## Add arguments and options

The place of a parameter in the signature decides its kind. A parameter before
the bare `*` is an argument, and the command line gives it by position. A
parameter after the bare `*` is an option, and the command line gives it as
`--name`.

1. Add the parameters to the command:

   ```python
   @as_command("order:import", aliases="oi")
   async def import_orders(
       io: ConsoleStyle,
       source: Path,
       *,
       limit: int = 100,
       dry_run: bool = False,
   ) -> int: ...
   ```

2. Describe each parameter in the `Args:` section of the docstring.
3. Run the command with the options:

   ```sh
   uv run shop order:import orders.csv --limit 10 --dry-run
   ```

The annotation of a parameter converts the text of the command line:

| Declaration | Command line | The command receives |
|---|---|---|
| `source: Path` | `orders.csv` | `Path("orders.csv")` |
| `target: Path \| None = None` | nothing | `None` |
| `*files: Path` | `a.csv b.csv` | a tuple of two paths |
| `limit: int = 100` | `--limit 10` | `10` |
| `dry_run: bool = False` | `--dry-run` | `True` |
| `tags: list[str] \| None = None` | `--tags a --tags b` | `["a", "b"]` |
| `level: Literal["low", "high"] = "low"` | `--level high` | `"high"` |

A value that the annotation refuses ends the command with the exit code `2`.

### Give an option a short name

An `Option` marker holds what the annotation cannot say. Attach the marker with
`Annotated`.

1. Import `Option` and mark the parameter:

   ```python
   from typing import Annotated

   from xtr_console import Option


   @as_command("order:import")
   async def import_orders(
       io: ConsoleStyle,
       source: Path,
       *,
       dry_run: Annotated[bool, Option(alias="-d")] = False,
   ) -> int: ...
   ```

2. Run the command with the short name:

   ```sh
   uv run shop order:import orders.csv -d
   ```

The `Option` marker accepts these arguments:

| Argument | Effect |
|---|---|
| `alias="-d"` | a second name for the option |
| `name="--from"` | another name on the command line |
| `negative="--no-cache"` | a second flag that turns the option off |
| `count=True` | each repetition of the flag adds one to an integer |
| `env_var="SHOP_TOKEN"` | the value of a variable, when the command line omits the option |
| `validator=Range(gte=1, lte=5)` | refuse a value outside the limits |
| `help="..."` | the description, instead of the docstring |

An `Argument` marker accepts `name`, `help`, `env_var` and `validator`.

> [!CAUTION]
> Do not mark a parameter before the bare `*` with `Option`, and do not mark a
> parameter after it with `Argument`. Either mistake raises
> `CommandSignatureError`.

## Write the output of the command

A parameter with the annotation `ConsoleStyle` receives the style object of the
run. The style object writes every heading, table and message of the console.

1. Call the methods of the style object:

   ```python
   @as_command("order:report")
   async def report(io: ConsoleStyle) -> int:
       """Print the report of the orders."""
       io.title("Orders")
       io.table(["State", "Count"], [["open", "10"], ["sent", "4"]])
       io.listing(["10 open", "4 sent"])
       io.note("The figures come from the last import")
       io.success("Report ready")
       return ExitCode.SUCCESS
   ```

2. Run the command:

   ```sh
   uv run shop order:report
   ```

| Method | Writes |
|---|---|
| `title(message)` | a heading with `=` under it |
| `section(message)` | a smaller heading with `-` under it |
| `text(message, verbosity=Verbosity.NORMAL)` | one line, at the verbosity that you give |
| `listing(items)` | a list with a bullet for each item |
| `table(headers, rows)` | columns under a header |
| `progress(items, description="Working")` | each item, with a progress bar over them |
| `success(message)` | `[OK]` on a green band |
| `error(message)` | `[ERROR]` on a red band |
| `warning(message)` | `[WARNING]` on a yellow band |
| `note(message)` | `[NOTE]` |

A message is markup, so `"[bold]done[/bold]"` writes **done**. Call `escape` on
text that comes from outside the program:

```python
from xtr_console import escape

io.success(f"Read {escape(str(source))}")
```

## Return an exit code

Every command returns an integer, and the annotation of the return value says
so. The `ExitCode` enumeration names the three codes of the console.

1. Return a code for each outcome:

   ```python
   @as_command("order:import")
   async def import_orders(io: ConsoleStyle, source: Path) -> int:
       """Import the orders of a file."""
       if not source.is_file():
           io.error(f"No file {escape(str(source))}")
           return ExitCode.FAILURE
       io.success("Imported")
       return ExitCode.SUCCESS
   ```

2. Read the code of the last command in the shell:

   ```sh
   uv run shop order:import nope.csv
   echo $?
   ```

   The shell reports `1`.

| The command | Exit code |
|---|---|
| returns `ExitCode.SUCCESS` or `0` | `0` |
| returns `ExitCode.FAILURE`, or raises an exception | `1` |
| returns `ExitCode.INVALID` | `2` |
| receives a command line that the parser refuses | `2` |
| returns another integer | that integer, between `0` and `255` |
| stops under Ctrl-C | `130` |

> [!NOTE]
> A command without a return annotation, or with an annotation that is not an
> integer, raises `CommandSignatureError`.

## Write a command as a class

A class command holds the services of the command in its constructor. The
container builds the class when the command runs, and only then.

1. Create the file `src/shop/command/count_orders_command.py`:

   ```python
   """``order:count``: print the number of orders."""

   from __future__ import annotations

   from xtr_console import ConsoleStyle, ExitCode, as_command

   from shop.catalog import OrderRepository

   __all__ = ["CountOrders"]


   @as_command("order:count")
   class CountOrders:
       """Print the number of orders."""

       def __init__(self, orders: OrderRepository) -> None:
           self._orders = orders

       async def __call__(self, io: ConsoleStyle) -> int:
           """Print the number of orders.

           Args:
               io: Where the command writes.
           """
           io.success(f"{self._orders.count()} orders")
           return ExitCode.SUCCESS
   ```

2. Run the command:

   ```sh
   uv run shop order:count
   ```

The `__call__` method takes the arguments and the options. Its docstring gives
the help of the command.

### Ask a function command for a service

A function command asks the container for a service with the `Injected` marker.
The command line never sees such a parameter.

```python
from xtr_dependency_injection import Injected


@as_command("order:stock")
async def stock(io: ConsoleStyle, orders: Injected[OrderRepository]) -> int:
    """Print the number of orders.

    Args:
        io: Where the command writes.
        orders: The repository of the orders.
    """
    io.success(f"{orders.count()} orders")
    return ExitCode.SUCCESS
```

## Find the command in the list

1. List every command of the application:

   ```sh
   uv run shop list
   ```

   The output groups the commands under their namespace. It also holds the
   commands of every active bundle.
2. List one namespace only:

   ```sh
   uv run shop list order
   ```

   The output holds the three commands of this guide, and the alias of one:

   ```text
   Available commands for the "order" namespace:
     order:count        Print the number of orders.
     order:import (oi)  Import the orders of a file.
     order:report       Print the report of the orders.
   ```

3. If the list has no command of yours, read the name of the module again. The
   kernel skips a module under `tests`, and a module with the name `conftest`,
   `__main__` or `test_*`.

> [!NOTE]
> `@as_command("cache:warm", hidden=True)` keeps a command out of the list. The
> command still runs under its name.

## Next step

- [Configure a bundle](configuration.md) shows how to name the application and
  give it a version.
- [Console commands](../reference/console-commands.md) lists the commands of the
  xtr packages.
- The README of
  [xtr-console](https://github.com/xterr/python-xtr/tree/main/packages/xtr-console)
  describes questions, verbosity and the testers of a command.
- The [API reference](https://xterr.github.io/python-xtr/api/xtr_console/)
  documents `as_command`, `ConsoleStyle`, `Option` and `ExitCode`.
