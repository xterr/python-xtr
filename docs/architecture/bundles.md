# Bundles

A bundle connects one package to the container. It reads a configuration
object, and then it tells the container how to make the services of the
package. This page describes the parts of a bundle.

## A bundle and its configuration

A bundle is a subclass of `Bundle`. The `@as_bundle` decorator gives the bundle
a name and a configuration class:

```python
@final
@as_bundle("cache", config=CacheConfig)
class CacheBundle(Bundle[CacheConfig]): ...
```

The configuration class is a frozen dataclass. Each field has a default value.
Thus, the bundle works when the application gives no configuration. The
`__post_init__` method of the class makes sure that the values agree with each
other.

## How an application changes the configuration

An application changes the configuration with a function that has the
`@configure` decorator. The function returns a configuration object. If the
function has a parameter of the configuration type, it receives the current
configuration:

```python
from dataclasses import replace

from xtr_dependency_injection import configure, env
from xtr_messenger import MessageBusConfig, TransportConfig


@configure
def messenger(config: MessageBusConfig) -> MessageBusConfig:
    return replace(config, transports={"async": TransportConfig(env("MESSENGER_DSN"))})
```

The [configuration guide](../guides/configuration.md) shows the procedure.

## The hooks of a bundle

A bundle can override six hooks. Each hook is optional, and each hook has one
job.

| Hook | When it runs | Its job |
|---|---|---|
| `build` | First, before the configuration. | Adds compiler passes, autoconfiguration rules and kernel parameters. |
| `prepend_extension` | When the kernel merges the configuration. | Changes the configuration of another bundle. |
| `load_extension` | When the kernel merges the configuration. | Registers the services of the package. |
| `process` | After all the bundles registered their services. | Reads and changes the service definitions. |
| `boot` | After the container compiles. It is async. | Starts the resources of the package. |
| `shutdown` | When the kernel shuts down, in the opposite sequence. It is async. | Closes the resources of the package. |

The hooks of the bundles run in the sequence of their dependencies.

## Bundles that require other bundles

A bundle can require another bundle with the `@required_bundle` decorator. The
kernel then adds the other bundle, also when the application does not list it.
The `Required` column of `debug:bundles` shows the bundles that each bundle
requires.

A bundle can also use another bundle only when it is available. The
`ignore_on_invalid=True` argument makes the requirement optional. Thus,
`xtr-cache` adds its console commands only when the application installs
`xtr-console`.

## The zero-configuration rule

Each bundle must build and boot with no configuration from the application.
With no configuration, a bundle does no input or output until the application
asks for a service.

Some settings come only from the application, for example a signing key. The
bundle does not check such a setting when the kernel builds. The service that
needs the setting checks it when the application first uses that service. The
error then gives the name of the setting.

> [!NOTE]
> Each bundle has a test that calls `assert_zero_config`. This test builds and
> boots the bundle with no configuration.

## How the application finds a bundle

The application lists its bundles in `config/bundles.py`. When you install a
package, its bundle does not become active.

Each package with a bundle declares the bundle in an entry point of its
`pyproject.toml`. The `debug:bundles` command reads these entry points. It shows
each installed bundle that the application does not list, under the title
**Installed, not active**.

## A bundle for development only

A bundle can be active in some environments only. The flags `{"dev": True}`
make a bundle active in development and nowhere else. `config/bundles.py`
imports such a bundle like every other one. The bundle of `xtr-maker`, which
adds the `make:*` commands, is one example.

A deployment that installs no development dependencies still loads the list.
When the list cannot import a package, the kernel reads the list again and
substitutes that package. Where the flags leave the bundle
inactive, nothing needs it, and `debug:bundles` reports it as `env_disabled`.
Where the flags make it active, the build stops with `MissingBundleError`, and
the error names the bundle.

> [!NOTE]
> The kernel substitutes only the imports of `config/bundles.py`. An
> application module that needs the missing package still fails to import.

## More information

The
[xtr-dependency-injection README](https://github.com/xterr/python-xtr/tree/main/packages/xtr-dependency-injection)
describes each part of the bundle API.
