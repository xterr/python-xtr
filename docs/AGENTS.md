# AGENTS.md — writing the documentation

Rules for agents that write or change a page under `docs/`. The root
[AGENTS.md](../AGENTS.md) also applies: its naming and vocabulary rules apply to
every page.

## The standard

Write every page in ASD-STE100 Simplified Technical English, Issue 9. The rules
below are the parts of the standard that apply to these pages, in our own words.
Do not copy text from the standard into this repository.

Vale checks the rules that a tool can check. Run it from the repository root:

```sh
vale docs
```

Vale cannot check all of the rules. Read your page again against this file
before you finish.

## Two types of text

Each page has one type. The type sets the limits.

| Type | Folders | The reader | Maximum words in a sentence |
|---|---|---|---|
| Procedure | `setup/`, `guides/` | does a task, step by step | 20 |
| Description | `index.md`, `components/`, `architecture/`, `reference/` | learns how a part works | 25 |

A guide can have a short description before its steps. That description obeys
the description rules.

## Rules for words

1. Use one word for one meaning. When a page uses "bundle" for a thing, do not
   call the same thing a "plugin" or a "module" later.
2. Use the simple word: "use", not "utilize"; "start", not "commence"; "show",
   not "indicate"; "help", not "facilitate"; "get", not "obtain".
3. Do not use contractions. Write "do not", not "don't".
4. Use an "-ing" word only when it is part of a technical name, for example
   `debug:bundles` output or a "routing table" that the code names.
5. Do not use phrasal verbs when a single verb exists: "start", not "set up";
   "find", not "look up"; "remove", not "take out".
6. Do not use "and/or", "etc.", "e.g." or "i.e.". Write the full words, or
   write the list.
7. Use "must" for a requirement. Do not use "shall", "should" or "may" for a
   requirement.
8. Technical names are permitted: package names, class names, functions,
   commands, options, configuration keys and file names. Put each one in code
   format, for example `xtr-cache`, `CacheBundle`, `recipes:add`.
9. A technical verb that is not a plain English verb must be in
   [the vocabulary](.vale/styles/config/vocabularies/xtr/accept.txt). Add it
   there with one meaning before you use it.

## Rules for sentences

1. Use the active voice. Write "The recipe writes the file", not "The file is
   written by the recipe".
2. Write one topic in each sentence.
3. Use "a", "an" or "the" before a noun when English permits it.
4. Do not stack more than three nouns. Write "the configuration of the cache
   pool", not "the cache pool configuration file entry".
5. Use the present tense for descriptions.

## Rules for procedures

1. Write each step in the imperative: "Run", "Open", "Add".
2. Write one instruction in each step. Two actions can share a step only when
   you do them at the same time.
3. Put a condition before the instruction: "If the build fails, read the
   error.", not "Read the error if the build fails."
4. Number the steps.
5. After a step that has a result the reader must see, write the result in the
   next sentence of the same step.

## Rules for descriptions

1. Start each paragraph with a topic sentence.
2. Write one topic in each paragraph.
3. Write a maximum of six sentences in each paragraph.
4. Give the information in a logical sequence: what the part is, what it does,
   how it connects to other parts.

## Notes, warnings and cautions

Use the callout syntax that GitHub, GitLab and the site all show:

```markdown
> [!NOTE]
> The kernel builds the container again each time it starts.
```

1. A `[!NOTE]` or a `[!TIP]` gives information. It never gives an instruction.
   If the reader must do something, write a numbered step.
2. A `[!WARNING]` tells the reader about a risk of data loss or a security
   problem. A `[!CAUTION]` tells the reader about a risk of damage to the
   project, for example a file that a command overwrites.
3. Start a warning or a caution with the instruction, then give the reason.
4. Always write the marker in capital letters: `[!NOTE]`, `[!WARNING]`.

## Markdown that shows on GitHub, GitLab and the site

Each page must read correctly in the repository browser of GitHub and GitLab, and
on the site. Use only this syntax:

- Headings, paragraphs, lists, tables, links and images.
- Fenced code blocks with a language: ` ```sh `, ` ```python `, ` ```toml `.
- Mermaid diagrams in a ` ```mermaid ` block.
- The callouts above.

Do not use syntax that only the site can show: `!!!` admonitions, `===` content
tabs, `--8<--` includes, or `:::` API directives. The API reference is made from
the docstrings when the site builds. Do not write it by hand.

## Links

1. Link to another page with a relative path to its `.md` file, for example
   `[Add a package](setup/add-a-package.md)` in `docs/index.md`.
2. Link to a package with the absolute URL of its folder in the repository, for
   example `https://github.com/xterr/python-xtr/tree/main/packages/xtr-cache`.
3. Link to the API reference of a package with the absolute URL of the site, for
   example `https://xterr.github.io/python-xtr/api/xtr_cache/`. The API pages
   are not in `docs/`, so a relative link does not work in the repository.
4. Write these two addresses only in the forms above. A copy of the repository
   on another host rewrites them to its own repository and site.
5. A link to a heading must use the anchor that GitHub makes from the heading.
   `tests/test_docs_links.py` checks every link.

## Code examples

1. Each example must run as it is shown. Use names that exist in the source.
2. Show the command, then show the output only when the reader must compare it.
3. Use `uv run` for each command that runs in a project.

## Before you finish

1. Run `vale docs` and correct each problem.
2. Run `uv run pytest tests/test_docs_links.py` from the repository root.
3. Run `uv run --only-group docs zensical build` and read the warnings.
