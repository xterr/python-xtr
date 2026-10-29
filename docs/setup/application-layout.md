# The application layout

This page describes the files of an application that `uvx xtr-cli new shop
--webapp` makes. A console application has the same files, but it has no `web/`
directory.

```text
shop/
├── .env                      # environment variables, written by the recipes
├── compose.yaml              # services for development, written by the recipes
├── pyproject.toml            # dependencies, console scripts and tool settings
├── xtr.lock                  # the recipes that the application applied
├── src/shop/
│   ├── __main__.py           # the console entry point: uv run shop
│   ├── kernel.py             # the kernel that each entry point builds
│   ├── command/              # the console commands of the application
│   ├── config/
│   │   ├── bundles.py        # the bundles and their environments
│   │   └── packages/         # one configuration file for each bundle
│   └── web/
│       ├── __main__.py       # the web entry point: uv run shop-web
│       ├── app.py            # the FastAPI application
│       └── routes.py         # the routes of the application
└── tests/
```

## The kernel

`src/shop/kernel.py` contains the kernel. The kernel reads the bundles from
`config/bundles.py`, and it reads the environment from the `APP_ENV` variable.
Then it builds the container.

Each entry point builds and starts its own kernel. The console entry point runs
a command. The web entry point serves the FastAPI application.

```python
kernel: Final = Kernel(
    "shop",
    allowed_envs=("dev", "test", "prod"),
    exclude=(*DEFAULT_EXCLUDES, "shop.web.app"),
    concurrent_scoped_access=True,
)
```

The kernel scans the `shop` package for services. The `exclude` argument keeps
`shop.web.app` out of the scan, because that module builds the web application
when Python imports it.

## The bundles

`src/shop/config/bundles.py` lists the bundles of the application. Each bundle
has a map of the environments where it is active:

```python
BUNDLES = {
    DotenvBundle: {"all": True},
    OrmBundle: {"all": True},
    SecurityBundle: {"all": True},
}
```

The list has only the bundles that the application selects. A bundle can
require other bundles. The kernel adds these bundles. The `debug:bundles`
command shows each bundle with its source: `listed`, `required` or `kernel`.

## The configuration files

Each file in `src/shop/config/packages/` configures one bundle. The file has a
function with the `@configure` decorator. The function returns the
configuration object of the bundle:

```python
@configure
def logging() -> LoggingConfig:
    """One console handler, on every channel, following the command's verbosity."""
    return LoggingConfig(handlers={"console": ConsoleHandlerConfig()})
```

A bundle works with no configuration file. A configuration file is necessary
only to change the default values. The
[configuration guide](../guides/configuration.md) shows how to change a value.

## The environment files

The `.env` file contains the environment variables of the application. Each
recipe writes its variables between two marker lines:

```sh
###> xtr-orm ###
DATABASE_URL=postgresql+asyncpg://app:!ChangeMe!@127.0.0.1:5432/app
###< xtr-orm ###
```

> [!WARNING]
> Do not put a real password or a real secret in `.env`. Git tracks `.env`. Put
> local values in `.env.local`, which `.gitignore` excludes.

## The lock file

`xtr.lock` records the recipe of each package that the application applied.
Git must track this file. `recipes:sync --check` compares the application with
the lock file.

## The folders of your code

Each class goes in the folder named after what the class is, under
`src/shop/`. One module holds one public class.

| Folder | What it holds |
|---|---|
| `entity/` | the table definitions of the database |
| `repository/` | the queries of each entity |
| `message/` | the messages of the message bus |
| `message_handler/` | the handler of each message |
| `scheduler/` | the provider of each schedule |
| `command/` | the console commands |
| `event/` | the events of the application |
| `event_listener/` | a class that reacts to one event |
| `event_subscriber/` | a class that reacts to more than one event |
| `remote_event/` | the consumer of the events of each other system |
| `webhook/` | the request parser of each webhook |
| `middleware/` | the middleware of the message bus |
| `stamp/` | the stamps of an envelope |
| `transport/` | the transports of the message bus |
| `security/voter/` | the voters of the access decisions |
| `service/` | the other services of the application |
| `exception/` | the errors of the application |

The template makes only the folders that its own files need. Create a folder
when you write the first class for it. A folder must have an `__init__.py`
file, because the kernel imports each module by its dotted name.

The `make:*` commands of `xtr-maker` write into these folders, and they create
the folder and the `__init__.py` file when neither is there. The
[Generate code](../guides/generate-code.md) guide shows one flow.

## The console commands

The commands of the application are in `src/shop/command/`. The
[console commands guide](../guides/console-commands.md) shows how to add a
command.
