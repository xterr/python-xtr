# Generate code

The `make:*` commands write the first files of a class. Each command puts a
file in the folder named after what the class is. A command never overwrites a
file that exists.

The commands are in the `xtr-maker` package. The package is a development
dependency, so a deployment has none of these commands.

This guide generates an entity, the revision of its table, and a message.

## Before you start

- You have an application with the name `shop`. If not,
  [create an application](../setup/new-application.md).
- The application has `xtr-maker` in its `dev` dependencies.
  [Add a package](../setup/add-a-package.md#add-a-package-for-development-only)
  shows the command.
- `uv run shop debug:bundles` shows `maker` with the state `active`.
- The `orm` bundle and the `messenger` bundle are active.
- The database of the application runs, and it has each revision.

## Procedure

1. Open a terminal in the directory of the application.
2. List the commands that the application has:

   ```sh
   uv run shop list make
   ```

   The list holds one command for each library whose bundle is active.
3. Write an entity with one field:

   ```sh
   uv run shop make:entity Book --field title:string:120 -n
   ```

   The command writes `src/shop/entity/book.py` and
   `src/shop/repository/book_repository.py`.
4. Open `src/shop/entity/book.py` and add the other properties of the entity.
5. Write the revision of the new table:

   ```sh
   uv run shop make:migration --message books -n
   ```

   The command writes a file under `migrations/`, and it names the revision.
6. Read the new revision.
7. Apply the revision to the database:

   ```sh
   uv run shop orm:migrations:migrate -n
   ```

8. Write a message and its handler:

   ```sh
   uv run shop make:message PlaceOrder -n
   ```

   The command writes `src/shop/message/place_order.py` and
   `src/shop/message_handler/place_order_handler.py`.
9. Open the message and add its fields.
10. Open the handler and write what it does with the message.

> [!CAUTION]
> Apply every revision before you run `make:migration`. The command compares
> the database with the table definitions. A database that is behind reports
> how many revisions wait, and it writes no revision.

## The other commands

| Command | What it writes | It needs this bundle |
|---|---|---|
| `make:schedule` | the provider of a schedule, in `scheduler/` | `scheduler` |
| `make:webhook` | the request parser, the consumer of the events, and a route module in `config/packages/` | `webhook` |
| `make:command` | a console command class, in `command/` | the console bundle alone |
| `make:listener` | a class in `event_listener/`, or a class in `event_subscriber/` | `event_dispatcher` |

A command that has no `-n` option on its command line asks for each value. The
README of `xtr-maker` lists each argument, each option and each question.

> [!NOTE]
> A run writes every file together. A target that exists ends the run, and no
> file reaches the disk.

## Next step

- [The application layout](../setup/application-layout.md) lists the folder of
  each type of class.
- [Console commands](../reference/console-commands.md) lists the commands of the
  xtr packages.
- The README of
  [xtr-maker](https://github.com/xterr/python-xtr/tree/main/packages/xtr-maker)
  describes each command in full.
- The [API reference](https://xterr.github.io/python-xtr/api/xtr_maker/)
  documents `Generator`, `FileManager` and `TemplateRenderer`.
