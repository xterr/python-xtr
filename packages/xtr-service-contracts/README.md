<div align="center">

# xtr-service-contracts

**What a container drives, not what a service does.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="core dependencies: 0" src="https://img.shields.io/badge/core%20deps-0-3FB950">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

A service's own contract says what it is *for* — a logger logs, a lock locks, a bus dispatches.
This package holds the other kind: what something built by a container must answer to so the
container can **manage** it, whatever it is for.

Keeping the two apart matters. `reset()` is not a logging idea, so a logging contract that ships
it makes every consumer of that contract inherit a concern belonging to the container. Here it is
declared once, and any contract or library that needs it depends on a package with **no
dependencies at all**.

That last part is the whole design: this is a leaf, and it should stay one. Every other contract
package in the ecosystem is free to depend on it, which only remains true while nothing here can
drag anything in.

## Install

```sh
uv add xtr-service-contracts
```

Requires Python 3.11+.

## `ResetInterface`

```python
@runtime_checkable
class ResetInterface(Protocol):
    def reset(self) -> None: ...
```

A long-running process — a worker consuming messages, a server answering requests — builds its
services once and uses them many times. Buffers, caches, accumulated state and generated ids
belong to one unit of work rather than to the service holding them. `reset()` ends that unit, so
the next starts clean while configuration survives:

```python
from xtr_service_contracts import ResetInterface


class Buffer:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity  # configuration — survives
        self.items: list[str] = []  # this unit of work — does not

    def reset(self) -> None:
        self.items.clear()


assert isinstance(Buffer(10), ResetInterface)
```

The protocol is structural and `@runtime_checkable`, so nothing has to inherit from it — a class
that already has a `reset()` satisfies it as it stands. A container is the usual caller: it knows
what it built, so it can reset whatever asks for it between units of work, and neither side has
to know anything else about the other.

```python
for service in container.services:
    if isinstance(service, ResetInterface):
        service.reset()
```

## `ContainerInterface`

```python
@runtime_checkable
class ContainerInterface(Protocol):
    async def get(self, service: type[T], /, qualifier: Hashable | None = None) -> T: ...
    def has(self, service: type[object], /, qualifier: Hashable | None = None) -> bool: ...
    def get_parameter(self, name: str, /) -> object: ...
    def has_parameter(self, name: str, /) -> bool: ...
```

What a dependency-injection container answers to.

A service is identified by its **type** plus an optional `qualifier` that chooses between several
services registered for that same type. `get` builds asynchronously and raises a `LookupError`
when `has()` is false; a registered service that cannot be built raises its own error.
`get_parameter` takes a dotted name and raises a `LookupError` when `has_parameter()` is false.

## `ServiceProviderInterface`

```python
@runtime_checkable
class ServiceProviderInterface(Protocol[T_co]):
    async def get(self, name: Hashable, /) -> T_co: ...
    def has(self, name: Hashable, /) -> bool: ...
    def provided_services(self) -> Mapping[Hashable, type[object]]: ...
```

A source of services keyed by **name**. It knows every name it can answer to and the type each
yields, without building any of them; a service is built lazily, on first request.

## `ServiceCollectionInterface`

```python
@runtime_checkable
class ServiceCollectionInterface(ServiceProviderInterface[T_co], Protocol[T_co]):
    def __len__(self) -> int: ...
    def __aiter__(self) -> AsyncIterator[tuple[Hashable, T_co]]: ...
```

A provider that is also countable and iterable. Iterating yields `(name, service)` pairs, each
built as it is reached, in `provided_services()` order:

```python
count = len(collection)
async for name, service in collection:
    ...
```

All three are `@runtime_checkable`, which checks method presence only — an implementation inherits
the protocol explicitly so a type checker verifies its signatures against the contract.

## Why providers are not containers

A **container** is keyed by **type** (plus an optional qualifier) and carries **parameters**: it
is what an application resolves services from. A **provider** is keyed by **name** and carries
nothing else: a small, fixed, named collection, the shape a `ServiceLocator` or a tagged-iterator
locator takes. Splitting them keeps each contract about one thing, and lets `ContainerInterface`
speak in types rather than being pinned to string ids.

## Who uses it

| Package | Uses it for |
| --- | --- |
| [xtr-dependency-injection](https://github.com/xterr/python-xtr-dependency-injection) | `ContainerInterface`, `ServiceProviderInterface` and `ServiceCollectionInterface` as its container, locator and tagged-collection contracts, and `ResetInterface` for `kernel.reset` |
| [xtr-logging](https://github.com/xterr/python-xtr-logging) | Buffered and fingers-crossed handlers, generated ids, and `LoggerFactory.reset()` between requests or messages |

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-service-contracts`; run the commands below from there. The `python-xtr-service-contracts` repository is a
read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync
uv run ruff check . && uv run ruff format --check .
uv run basedpyright
uv run ty check
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
