<div align="center">

# xtr-http-foundation

**One question each about a request that arrived, composed into one matcher — and the helpers that place an IP in a network.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="asyncio" src="https://img.shields.io/badge/asyncio-native-1f6feb">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

"Is this request one of mine?" is asked by a firewall, a webhook endpoint, a rate limiter and a
router, and each one answers it with its own tangle of `if`s over the method, the path and a
header or two. Written that way the answer is untestable on its own and subtly different
everywhere.

A matcher answers one such question, and a chain of them answers the whole of it. Alongside
them live the address helpers the questions about *who* sent a request are built on: whether an
IP falls in a network, and whether it is one only this network can reach.

## Install

```sh
uv add xtr-http-foundation
```

Requires Python 3.11+.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-http-foundation`; run the commands below from there. The
`python-xtr-http-foundation` repository is a read-only copy, so send issues and pull requests
to the monorepo.

```sh
uv sync --all-extras
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
