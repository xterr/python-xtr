# Agent skills

An agent skill teaches a coding agent to use a package. Each xtr package that
is a direct dependency of the application ships a skill in its wheel. Its path
in the wheel is `src/xtr_<name>/.agents/skills/xtr-<name>/SKILL.md`, at the
version of the package. A skill holds a quick reference, task examples, test
help, the errors and the prohibitions of the package.

The `library-skills` tool discovers the skills of the installed packages. It
links each discovered skill into the `.agents/skills/` directory of the
project. A coding agent reads this directory on its own. A registered skill
loads when its description matches the task of the agent. The `AGENTS.md` file
of the project tells the agent to use the registered skills. The `xtr-cli`
templates write this file.

This guide registers the skills of the `shop` application.

## Before you start

- You have an application with the name `shop`. If not,
  [create an application](../setup/new-application.md).

## Register the skills

1. Open a terminal in the directory of the application.
2. Register every skill that the installed packages ship:

   ```sh
   uvx library-skills --all
   ```

   The command links each newly discovered skill into `.agents/skills/`.
3. If you add a package with `uv add` or `recipes:add`, run the command again.
   The command links the skill of the new package into `.agents/skills/`.
4. In the automated checks of the project, validate the registration:

   ```sh
   uvx library-skills --check
   ```

   The command ends with the exit code 1 when the registered skills and the
   installed packages differ.

## What a skill gives an agent

A skill tells the agent what the package is for. The quick reference names the
classes and the commands. The task sections show examples that run. The
testing section shows how to test the application. The errors section names
each error of the package. The prohibitions tell the agent what it must not
do.

The agent loads a skill only when the description of the skill matches the
task. Thus the knowledge of the package is in the context of the agent only
when it is necessary.

## Manage the skills

Each subcommand does one task:

| Command | What it does |
|---|---|
| `uvx library-skills scan` | Shows the skills that the installed packages ship. |
| `uvx library-skills list` | Lists the discovered or the registered skills. |
| `uvx library-skills install` | Registers the skills, one or many. |
| `uvx library-skills remove` | Removes the registered skills that are links. |

The options change what the command does:

| Option | What it does |
|---|---|
| `--all` | Registers every newly discovered and unmanaged skill. |
| `--skill NAME` or `-s NAME` | Registers one skill by the name. |
| `--check` | Validates the registration, with exit code 1 on a difference. |
| `--copy` | Copies the files instead of the links. |
| `--yes` or `-y` | Skips the confirmation. |
| `--claude` | Manages `.claude/skills/` together with `.agents/skills/`. |

> [!NOTE]
> A Claude agent reads `.claude/skills/` instead of `.agents/skills/`. The
> `--claude` option manages the two directories together.

## Next step

- [Add a package](../setup/add-a-package.md) installs a package and applies
  its recipe.
- [The application layout](../setup/application-layout.md) lists `AGENTS.md`
  with the other files of the application.
