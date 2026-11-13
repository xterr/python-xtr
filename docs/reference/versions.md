# Versions

All the xtr packages have the same version number. A release publishes each
package, also a package that did not change. Thus, two xtr packages with the
same version always work together.

## Version numbers

The version number has three parts: `MAJOR.MINOR.PATCH`, for example `6.8.0`.

| Part | When it changes |
|---|---|
| `MAJOR` | A release changes an API in a way that can break your code. |
| `MINOR` | A release adds a feature. Your code continues to work. |
| `PATCH` | A release repairs a defect. Your code continues to work. |

## Dependencies between packages

A package requires each other xtr package by its major version. For example,
`xtr-messenger` 6.8.0 requires `xtr-logging-contracts>=6.0,<7`. Thus, uv can
install any version 6 of the packages together.

Require the xtr packages in your application in the same way:

```toml
dependencies = [
    "xtr-cache>=6.0,<7",
    "xtr-messenger>=6.0,<7",
]
```

The `xtr-cli` templates and the `xtr-recipes` tool write the requirements in
this format.

## Python versions

Each package supports Python 3.11 and later versions. The tests of each package
run on Python 3.11 and on Python 3.14.

## Where to find a release

Each package is on the package index with its own name, for example
`xtr-cache`. Each release has a git tag in the
[repository](https://github.com/xterr/python-xtr/tags).
