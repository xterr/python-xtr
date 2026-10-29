# Create an application

The `xtr-cli` tool makes a new application from a template. It writes the files,
installs the packages and applies the recipe of each package. The command asks
no questions.

There are two templates:

| Template | Command | What it contains |
|---|---|---|
| `cli` | `uvx xtr-cli new shop` | A console application: `xtr-dependency-injection`, `xtr-console` and `xtr-dotenv`. |
| `webapp` | `uvx xtr-cli new shop --webapp` | The console application, and a FastAPI application with logging, a database, a message bus, an HTTP client, notifications and security. |

## Before you start

- Do the steps in [Install the tools](install.md).
- Select a directory that does not exist, or an empty directory. The command
  does not write over a file.

## Procedure

1. Open a terminal in the parent directory of the new application.
2. Make the application. This example makes a web application with the name
   `shop`:

   ```sh
   uvx xtr-cli new shop --webapp
   ```

   The command shows each file that it writes and each command that it runs.
   At the end, it shows `[OK] shop is ready`.
3. Go into the new directory:

   ```sh
   cd shop
   ```

4. Run the tests of the application:

   ```sh
   uv run pytest
   ```

   The tests build the kernel. For a web application, a test also sends a
   request to the home page.
5. Run the example command:

   ```sh
   uv run shop app:hello Ada
   ```

   The command shows `[OK] Hello, Ada!`.
6. Show the bundles that the application uses:

   ```sh
   uv run shop debug:bundles
   ```

   The command shows a table. Each bundle has the state `active`.
7. For a web application, start the web server:

   ```sh
   uv run shop-web
   ```

   The server listens on `http://127.0.0.1:8000`. Open this address in a
   browser. The page shows `{"status": "ok"}`.
8. Push `Ctrl-C` to stop the server.

> [!NOTE]
> The web application connects to PostgreSQL and RabbitMQ only when it uses
> them. The tests and the home page work when neither service runs. The
> `compose.yaml` file of the application starts a PostgreSQL database.

## Options

| Option | What it does |
|---|---|
| `--webapp` | Makes a web application, not a console application. |
| `--name NAME` | Sets the name of the distribution and of the console command. The default is the name of the directory. |
| `--python 3.13` | Sets the Python version of the application. The version must be 3.11 or a later version. |
| `--no-git` | Does not start a git repository. |
| `--dry-run` | Shows each file and each command, and writes nothing. |

To make an application in the current directory, use `uvx xtr-cli init`.

> [!NOTE]
> The template writes the kernel as `Kernel(__package__, ...)` in
> `src/shop/kernel.py`. The kernel gets the name of the application package from
> Python. If you rename the package, the kernel uses the new name.

## Next step

[Add a package](add-a-package.md), or read
[the application layout](application-layout.md).
