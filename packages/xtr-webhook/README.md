<div align="center">

# xtr-webhook

**Receive webhooks — verified, replay-bounded, turned into events — and send them signed, in the legacy or the Standard Webhooks format.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="asyncio" src="https://img.shields.io/badge/asyncio-native-1f6feb">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

A webhook is an HTTP request from someone who is not a user, so the usual answers do not
apply: there is no session to trust, the body is the only thing signed, and a request captured
once can be sent again tomorrow. Handling one well means checking it against the right
secret, refusing anything outside a window, and getting off the request as fast as possible.

Sending one is the same problem from the other side: sign the exact bytes, say when they were
signed, and retry what the receiver refused.

This package does both ends, and turns what arrives into an
[xtr-remote-event](../xtr-remote-event) event, so the code that handles it never sees HTTP.

## Install

```sh
uv add xtr-webhook              # signatures, parsers, the events a webhook becomes
uv add "xtr-webhook[client]"    # + sending signed webhooks
uv add "xtr-webhook[http]"      # + the endpoint that receives them
uv add "xtr-webhook[di]"        # + the bundle
```

## Quick start

## Use in an application

## Kernel / bundle

## Errors

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-webhook`; run the commands below from there. The `python-xtr-webhook`
repository is a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync --all-extras
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
