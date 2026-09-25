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

## `ResettableInterface`

```python
@runtime_checkable
class ResettableInterface(Protocol):
    def reset(self) -> None: ...
```

A long-running process — a worker consuming messages, a server answering requests — builds its
services once and uses them many times. Buffers, caches, accumulated state and generated ids
belong to one unit of work rather than to the service holding them. `reset()` ends that unit, so
the next starts clean while configuration survives:

```python
from xtr_service_contracts import ResettableInterface


class Buffer:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity  # configuration — survives
        self.items: list[str] = []  # this unit of work — does not

    def reset(self) -> None:
        self.items.clear()


assert isinstance(Buffer(10), ResettableInterface)
```

The protocol is structural and `@runtime_checkable`, so nothing has to inherit from it — a class
that already has a `reset()` satisfies it as it stands. A container is the usual caller: it knows
what it built, so it can reset whatever asks for it between units of work, and neither side has
to know anything else about the other.

```python
for service in container.services:
    if isinstance(service, ResettableInterface):
        service.reset()
```

## Who uses it

| Package | Uses it for |
| --- | --- |
| [xtr-logging](https://github.com/xterr/python-xtr-logging) | Buffered and fingers-crossed handlers, generated ids, and `LoggerFactory.reset()` between requests or messages |

## Development

```sh
uv sync
uv run ruff check . && uv run ruff format --check .
uv run basedpyright
uv run ty check
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
