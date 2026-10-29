# Console commands

This page lists the console commands of the xtr packages. A bundle adds its
commands to the console of the application when the bundle is active. Run a
command with the console script of the application:

```sh
uv run shop debug:bundles
```

To see the commands of your application, run `uv run shop list`. To see the
arguments and the options of one command, add `--help`:

```sh
uv run shop orm:migrations:migrate --help
```

The `xtr-cli` and `xtr-recipes` commands are different. They have their own
console scripts, because they change the project and do not need its kernel.

## Project tools

| Command | Package | What it does |
|---|---|---|
| `xtr new` (`project:new`) | `xtr-cli` | Makes an application in a new directory. |
| `xtr init` (`project:init`) | `xtr-cli` | Makes an application in the current directory. |
| `xtr serve` (`server:start`) | `xtr-cli` | Serves the web application of the current project. |
| `recipes:add` | `xtr-recipes` | Adds a requirement to the project, then applies the recipes that it brings. The `--dev` option puts the requirement in the `dev` group. |
| `recipes:remove` | `xtr-recipes` | Removes a dependency, then undoes its recipe. |
| `recipes:sync` | `xtr-recipes` | Applies new recipes, applies changed recipes again and undoes the recipes of removed packages. |
| `recipes:install` | `xtr-recipes` | Applies the recipe of one package again. |
| `recipes:show` | `xtr-recipes` | Lists the recipes of the project, or shows one recipe. |

Run the `xtr-cli` commands with `uvx xtr-cli <command>`, or with `xtr <command>`
after `uv tool install xtr-cli`. Run the `xtr-recipes` commands with
`uv run xtr-recipes <command>` in the project.

## Diagnostics

| Command | Package | What it does |
|---|---|---|
| `debug:bundles` | `xtr-console` | Lists each bundle that the kernel found, and the installed bundles that are not active. |
| `debug:config` | `xtr-console` | Shows the configuration of each bundle, or of one bundle. |
| `debug:container` | `xtr-console` | Lists the services of the container. The `--tag` option selects the services with a tag. |
| `debug:dotenv` | `xtr-dotenv` | Lists each environment file, and the value of each variable in each file. |
| `debug:event-dispatcher` | `xtr-event-dispatcher` | Lists the listeners of each event in the sequence that they run. |
| `debug:router` | `xtr-http-kernel` | Lists the routes of the web application in the sequence that the router tries them. |
| `debug:firewall` | `xtr-security` | Lists the firewalls, or shows the parts of one firewall. |
| `debug:scheduler` | `xtr-scheduler` | Lists the schedules and their recurring messages, with the time of the next run. |

## Application tasks

| Command | Package | What it does |
|---|---|---|
| `dotenv:dump` | `xtr-dotenv` | Compiles the environment files of one environment into one JSON file. |
| `router:match` | `xtr-http-kernel` | Shows the route that a path and a method find. It does not serve a request. |
| `messenger:consume` | `xtr-messenger` | Receives messages from the transports that you name, until you stop it. |
| `workflow:dump` | `xtr-workflow` | Writes a workflow as the source of a diagram. |

## Code generators

All these commands are in the `xtr-maker` package. The package is a development
dependency, so a deployment without the development dependencies has none of
these commands. Each command is in the console only when the bundle of its
library is active.

| Command | What it writes |
|---|---|
| `make:message` | A message, and the handler of that message. |
| `make:schedule` | The provider of a schedule. |
| `make:webhook` | The parser of a webhook, the consumer of its events, and its route. |
| `make:entity` | An entity and its repository, or new properties on an entity that exists. |
| `make:command` | A console command class. |
| `make:listener` | A listener of one event, or a subscriber of one event. |
| `make:migration` | A revision of the differences between the database and the table definitions. |

`make:command` needs only the console bundle. The six other commands need the
bundle of the library that they write code for. The
[Generate code](../guides/generate-code.md) guide shows one flow, and the
[xtr-maker README](https://github.com/xterr/python-xtr/tree/main/packages/xtr-maker)
describes each argument and each option.

## Cache

| Command | Package | What it does |
|---|---|---|
| `cache:pool:list` | `xtr-cache` | Lists the cache pools. |
| `cache:pool:clear` | `xtr-cache` | Clears cache pools. |
| `cache:pool:delete` | `xtr-cache` | Deletes one item from a cache pool. |
| `cache:pool:invalidate-tags` | `xtr-cache` | Invalidates cache tags in each pool that has tags, or in the pools that you name. |
| `cache:pool:prune` | `xtr-cache` | Removes the expired values from cache pools. |

## Database

All these commands are in the `xtr-orm` package.

| Command | What it does |
|---|---|
| `orm:database:create` | Creates the database of a connection on its server. |
| `orm:database:drop` | Drops the database of a connection from its server. |
| `orm:run-sql` | Runs a statement and shows the result. |
| `orm:migrations:status` | Shows the state of the database against its revisions. |
| `orm:migrations:list` | Lists each revision, and shows if the database has it. |
| `orm:migrations:current` | Shows the revisions that the database has now. |
| `orm:migrations:latest` | Shows the revisions that no other revision follows. |
| `orm:migrations:up-to-date` | Tells if the database has each revision. |
| `orm:migrations:migrate` | Moves the database up or down to a revision. |
| `orm:migrations:execute` | Runs only the revisions that you select, up or down. |
| `orm:migrations:diff` | Writes a revision of the differences between the database and the table definitions. |
| `orm:migrations:generate` | Writes an empty revision that you complete. |
| `orm:migrations:dump-schema` | Writes a first revision that creates each table of a database. |
| `orm:migrations:version` | Records revisions as applied or not applied. It runs no revision. |
| `orm:migrations:rollup` | Records the one remaining revision as the only applied revision. |

> [!WARNING]
> `orm:database:drop` deletes the database and all its data. Make a backup
> before you use it on a database that has data you need.

## Security

| Command | Package | What it does |
|---|---|---|
| `security:hash-password` | `xtr-password-hasher` | Hashes a password with the hasher that the configuration selects. |
| `security:oidc:generate-token` | `xtr-security-http` | Makes the access token that a firewall signs, and shows it. |
| `jwt:generate-keypair` | `xtr-security-jwt` | Makes a signing key. It shows the private key and the public key set. |
| `jwt:check-config` | `xtr-security-jwt` | Signs a test token and reads it again, to prove that the keys work. |
| `jwt:generate-token` | `xtr-security-jwt` | Loads a user and shows a token signed for that user. |
| `oauth2-server:create-client` | `xtr-security-oauth2-server` | Adds a client, and shows its secret one time. |
| `oauth2-server:list-clients` | `xtr-security-oauth2-server` | Lists the clients. It hides their secrets. |
| `oauth2-server:update-client` | `xtr-security-oauth2-server` | Changes the registration of a client, or turns it on or off. |
| `oauth2-server:delete-client` | `xtr-security-oauth2-server` | Deletes the registration of a client. |
| `oauth2-server:generate-keypair` | `xtr-security-oauth2-server` | Makes a signing key pair and writes it to the configured location. |
| `oauth2-server:clear-expired-tokens` | `xtr-security-oauth2-server` | Deletes each issued credential that has expired. |

> [!CAUTION]
> `oauth2-server:create-client` shows the secret of the client only one time.
> Copy the secret to a safe location before you close the terminal.
