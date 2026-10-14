<div align="center">

# xtr-http-client

**An async HTTP client behind one interface: typed options in, a response read on demand out.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="asyncio" src="https://img.shields.io/badge/asyncio-native-1f6feb">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

Sending a request is the easy half. The rest — one set of defaults per host, a timeout that
means what it says, a redirect that drops the credentials it must not carry on, an address an
untrusted URL must never reach, and a way to answer from a script instead of the network in a
test — is what every application writes again.

This package implements [xtr-http-client-contracts](../xtr-http-client-contracts) and puts that
rest behind the same interface: every feature is a client wrapping a client, so the code that
calls out sees one type however much is layered under it.

## Install

```sh
uv add xtr-http-client
uv add "xtr-http-client[di]"            # + the bundle
uv add "xtr-http-client[throttling]"    # + the limiter the throttling client paces by
```

Requires Python 3.11+.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what
removing it undoes.

- **Install** — `uv add "xtr-http-client[di]"`; add `throttling` to pace a client with an
  [xtr-rate-limiter](../xtr-rate-limiter) limiter, `http2` to ask for HTTP/2.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate* step below: it lists
  `HttpClientBundle`. There is no config file, environment or ignore line to write; it prints the
  step to name the services the application calls in `config/http_client.py`, which a recipe
  cannot make for you (see [xtr-recipes](../xtr-recipes)).
- **Activate** — `HttpClientBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`,
  imported from `xtr_http_client.bundle`.
- **Brings along** — the rate limiter bundle when xtr-rate-limiter is installed.
- **Configure** — optional: with no configuration there is one client, an
  `HttpClientInterface` sending requests as they are given. Default options, a client per
  service, retries, a pace and a mock for tests go in `<app>/config/http_client.py`, a
  `@configure` function returning `HttpClientConfig` — see [Kernel / bundle](#kernel--bundle).
- **Environment** — nothing. A credential given as `env(...)` is read when the client needing
  it is built.
- **Ignore** — nothing.
- **Remove** — drop the `BUNDLES` entry, delete `<app>/config/http_client.py`, then
  `uv remove xtr-http-client`.
- **Check** — `debug:bundles` shows `http_client` as `listed` and `active`.

## Kernel / bundle

```python
# app/bundles.py
from xtr_http_client.bundle import HttpClientBundle

BUNDLES = {HttpClientBundle: {"all": True}}
```

```python
# app/config/http_client.py
from xtr_dependency_injection import configure, env

from xtr_http_client.bundle import (
    ClientOptionsConfig,
    HttpClientConfig,
    RetryFailedConfig,
    ScopedClientConfig,
)


@configure
def http_client() -> HttpClientConfig:
    return HttpClientConfig(
        default_options=ClientOptionsConfig(
            timeout=10, retry_failed=RetryFailedConfig(enabled=True)
        ),
        scoped_clients={
            "github": ScopedClientConfig(
                base_uri="https://api.github.com/",
                headers={"Accept": "application/vnd.github+json"},
                auth_bearer=env("GITHUB_TOKEN"),
            ),
        },
    )
```

The default client is the unqualified `HttpClientInterface`; each scoped client is the
`HttpClientInterface` qualified by its name:

```python
from typing import Annotated

from xtr_dependency_injection import Target, as_service
from xtr_http_client_contracts import HttpClientInterface


@as_service
class GithubRepositories:
    def __init__(self, github: Annotated[HttpClientInterface, Target("github")]) -> None:
        self._github = github
```

`HttpClientConfig`:

| Field | Default | What it sets |
|---|---|---|
| `max_host_connections` | `6` | how many connections one pool may hold |
| `default_options` | `ClientOptionsConfig()` | what every request starts from, and the default client's layers |
| `scoped_clients` | `{}` | a client per service, by name |
| `mock_response_factory` | `False` | answer every request from `MockHttpClient` instead of the network |
| `tracing` | `False` | wrap every client in a `TraceableHttpClient` |

`ClientOptionsConfig` carries the request options of the same name — `headers`, `timeout`,
`max_redirects`, `proxy`, `verify_peer` and the rest, `None` leaving each to the client — and
two layers: `retry_failed`, a `RetryFailedConfig` (`enabled`, `max_retries`, `delay`,
`multiplier`, `max_delay`, `jitter`, `http_codes`, `base_uris`, or a `retry_strategy` service
instead of the numbers), and `rate_limiter`, the name of the xtr-rate-limiter limiter requests
wait their turn from. `ScopedClientConfig` adds `scope` or `base_uri` (one is required),
`auth_basic`, `auth_bearer`, `query` and its own `mock_response_factory`; the
`retry_failed` and `rate_limiter` it leaves unset are the default options' own.

Each client is built, from the inside out, as the transport, the pace of its limiter, its
scope, its retries — outside the scope when they move along `base_uris` — and the trace.
Every client shares one transport, and so its connections; nothing is opened until a request
is made, and the connections are closed with the container. With `mock_response_factory`, the
`MockHttpClient` service is the transport: a test scripts it with `set_response_factory`.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-http-client`; run the commands below from there. The `python-xtr-http-client`
repository is a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync --all-extras
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
