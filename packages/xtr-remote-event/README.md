<div align="center">

# xtr-remote-event

**Events received from another system, as one value type, handed to the consumer registered under their source's name — directly or through a message bus.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="asyncio" src="https://img.shields.io/badge/asyncio-native-1f6feb">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

An event from elsewhere — a delivery report, a payment notice, a message from a provider —
arrives in whatever shape its sender chose. Once it is read, though, what the application does
with it is always the same: hand it to the code that handles events from that sender.

This package is that last step, and nothing else: one value type for the event, a one-method
contract for the consumer, a decorator naming which sources a consumer answers for, and a
message so the work happens on a worker rather than in the request that received it.

## Install

```sh
uv add xtr-remote-event          # the event, the consumer contract, the decorator
uv add "xtr-remote-event[di]"    # + the bundle
```

## Quick start

## Use in an application

## Kernel / bundle

## Errors

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-remote-event`; run the commands below from there. The
`python-xtr-remote-event` repository is a read-only copy, so send issues and pull requests to
the monorepo.

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
