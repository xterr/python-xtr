# Reference

The reference pages give facts that you find when you need them. They do not
teach a task.

| Page | What it contains |
|---|---|
| [Console commands](console-commands.md) | Each console command of each package. |
| [Versions](versions.md) | The version numbers of the packages, and how the packages work together. |
| [API reference](https://xterr.github.io/python-xtr/api/xtr_dependency_injection/) | The classes and functions of each package. The site makes these pages from the docstrings. |

## Configuration options

The configuration of a bundle is a frozen dataclass. The API reference shows
each field of each configuration class, with its type and its default value.
For example, `CacheConfig` is in the API page of `xtr_cache.bundle`.

To see the configuration that your application uses, run this command:

```sh
uv run shop debug:config
```

To see the configuration of one bundle, add the name of the bundle:

```sh
uv run shop debug:config cache
```
