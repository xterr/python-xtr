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
