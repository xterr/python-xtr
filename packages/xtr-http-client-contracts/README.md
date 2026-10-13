<div align="center">

# xtr-http-client-contracts

**The async HTTP client contract, and nothing else — so a library that calls out installs no backend.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="asyncio" src="https://img.shields.io/badge/asyncio-native-1f6feb">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

A library that sends an HTTP request should not choose what sends it. It takes the client
interface, asks for a method and a URL, and leaves connection pooling, redirects and TLS to
whatever the application wired behind it.

That needs the *seam*, not a client. This package is that seam: the client interface, the
response and chunk interfaces, the typed request options, the errors they raise, and a
conformance suite any implementation runs against itself.

## Install

```sh
uv add xtr-http-client-contracts
```

Requires Python 3.11+.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-http-client-contracts`; run the commands below from there. The
`python-xtr-http-client-contracts` repository is a read-only copy, so send issues and pull
requests to the monorepo.

```sh
uv sync --all-extras
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
