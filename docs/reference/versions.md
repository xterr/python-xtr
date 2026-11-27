# Versions

All the xtr packages have the same version number. A release publishes each
package, also a package that did not change. Thus, two xtr packages with the
same version always work together.

## Version numbers

The version number has three parts: `MAJOR.MINOR.PATCH`, for example `7.5.1`.

| Part | When it changes |
|---|---|
| `MAJOR` | A release changes an API in a way that can break your code. |
| `MINOR` | A release adds a feature. Your code continues to work. |
| `PATCH` | A release repairs a defect. Your code continues to work. |

## Dependencies between packages

A package requires each other xtr package from its own minor version, up to the
next major. For example, `xtr-messenger` 7.5.1 requires
`xtr-logging-contracts>=7.5,<8`. Thus, uv cannot install a package beside a
sibling that is older than it.

In your application, require the xtr packages by their major version. Thus, uv
can install any version 7 of the packages:

```toml
dependencies = [
    "xtr-cache>=7.0,<8",
    "xtr-messenger>=7.0,<8",
]
```

The `xtr-cli` templates and the `xtr-recipes` tool write the requirements in
this format.

## Upgrade the packages

uv upgrades only the packages that you name. Upgrade all the xtr packages of an
application together:

```sh
uv run xtr-recipes recipes:upgrade
```

The command upgrades each installed xtr package to its newest release, then
applies the recipes that changed.

## Python versions

Each package needs Python 3.14.4 or a later version. The tests of each package
run on Python 3.14.4 and on the latest release of Python 3.14.

The packages do not support Python 3.14.0, 3.14.1, 3.14.2 or 3.14.3. In those
releases, the folding of some email headers never stops.

## Where to find a release

Each package is on the package index with its own name, for example
`xtr-cache`. Each release has a git tag in the
[repository](https://github.com/xterr/python-xtr/tags).
