<div align="center">

# xtr-security-csrf

**Cross-site request forgery protection: a manager that mints and checks tokens by id, and the session storage that keeps them.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

A browser submits a form because a page told it to — and a page on someone else's site can
tell it to submit yours, carrying the user's cookies as though the request were the user's.
A **cross-site request forgery token** breaks that: the page that renders a form mints a
value into it, and the request that submits the form carries the value back, where it is
checked against what was minted. Another site's page cannot read the value — it is on your
origin's page, not theirs — so its forged submit does not check out.

This package is that mechanism, in three small pieces:

- 🎫 **A token** — `CsrfToken(token_id, value)`: the id names what the token guards, the
  value answers for it.
- 🖋️ **A manager** — `CsrfTokenManager(storage, generator=None, namespace=None)` mints a
  value per id, stores it, and masks what it hands out: every value a caller sees is
  masked with a fresh key, so two renders of one form carry different strings — and both
  check out, because what is *stored* never changes until `refresh_token` replaces it.
  `is_token_valid` compares in constant time and never raises on what it is handed.
- 🗄️ **A storage** — `TokenStorageInterface` keeps values by id; `SessionTokenStorage`
  keeps them in the [xtr-http-foundation](../xtr-http-foundation) session, under
  `_csrf/<token_id>`, and `ClearableTokenStorageInterface.clear()` drops every token it
  minted — the session strategy's call when a re-authentication rotates the session, so
  a value stolen before the rotation cannot answer after it.

It ships no bundle of its own: it is a library member of the security family —
[xtr-security](../xtr-security) is the bundle that wires the family into an application on
[xtr-dependency-injection](../xtr-dependency-injection).

## Install

```sh
uv add xtr-security-csrf
```

Requires Python 3.11+. One sibling comes with it:
[xtr-http-foundation](../xtr-http-foundation), whose session the storage keeps tokens in.

## Quick start

Everything below runs without a container: a session on the memory storage, the storage
over it, the manager over that. Mint a token where a form renders, check it where the form
submits:

```python
from __future__ import annotations

import asyncio

from xtr_http_foundation import MemorySessionStorage, Session
from xtr_security_csrf import CsrfToken, CsrfTokenManager, SessionTokenStorage


async def main() -> None:
    session = Session(MemorySessionStorage())
    manager = CsrfTokenManager(SessionTokenStorage(session))

    # The page that renders the form mints the token into it.
    token = await manager.get_token("newsletter")
    print("render:", token.get_value())

    # The request that submits the form carries the value back.
    print("carried:", await manager.is_token_valid(token))

    # A value nobody minted does not check out.
    print("forged:", await manager.is_token_valid(CsrfToken("newsletter", "nope")))


asyncio.run(main())
```

```console
render: 3.kV3xtkP…  (masked anew on every run)
carried: True
forged: False
```

The manager's four calls:

| Call | What it does |
|---|---|
| `await get_token(token_id)` | Returns the token for the id, minting one where none is stored |
| `await refresh_token(token_id)` | Mints a fresh value for the id, stored or not — for once-only tokens |
| `await remove_token(token_id)` | Drops the value, returning what it held, or `None` |
| `await is_token_valid(token)` | Tells whether the token carries the value stored under its id |

### The masked value

What a caller receives is never the stored value: `get_token` masks it with a fresh random
key every call — three dot-separated parts, a key-derived prefix, the key, the masked
value. The manager unmasks what comes back before comparing, so any string a request
carries can be handed to `is_token_valid` without a guard: one that does not read as a
masked value is compared as it came, and does not check out.

### The namespace

Stored ids carry a prefix: `CsrfTokenManager(storage, namespace="https-")` stores under
`https-<token_id>`, so tokens minted for one origin do not answer for another. A string is
used as it is; a callable is asked each time — the scheme a request arrived under can
change between calls. `None`, the default, prefixes nothing.

### The storage

`SessionTokenStorage(session, namespace="_csrf")` keeps each value under
`<namespace>/<token_id>` in the session's attributes, and keeps the list of its ids under
the namespace key itself — the session offers no way to walk its attributes, so the list
is what `clear()` drops them from: every token this storage minted, and nothing the rest of
the session holds. A token written under the namespace by something else than this storage
is not in the list, and survives a clear.

`clear()` is the session strategy's call, on the re-authentication that rotates the
session: the tokens minted under the old one must not answer for the new. `remove_token`
is the logout listener's — it drops the ids a listener knows by name.

## Errors

Everything this library raises derives from `CsrfError`, and carries what went wrong as
typed attributes rather than only a message.

| Error | Base (besides `CsrfError`) | Raised when |
|---|---|---|
| `InvalidArgumentError` | `ValueError` | a declaration, configuration or call was malformed — a generator asked for less entropy than a byte holds |
| `TokenNotFoundError` | — | a value was asked for under an id that holds nothing; carries `get_token_id()` |

## Layout

```
xtr_security_csrf/
├── csrf_token.py                    CsrfToken, the id and the value a caller holds
├── csrf_token_manager_interface.py CsrfTokenManagerInterface, the four calls
├── csrf_token_manager.py           CsrfTokenManager, minting, masking, checking
├── token_generator/
│   ├── token_generator_interface.py  TokenGeneratorInterface, the minting seam
│   └── uri_safe_token_generator.py   UriSafeTokenGenerator, URI-safe values
├── token_storage/
│   ├── token_storage_interface.py          TokenStorageInterface, values by id
│   ├── clearable_token_storage_interface.py ClearableTokenStorageInterface, + clear()
│   └── session_token_storage.py            SessionTokenStorage, in the session
└── exception/                       CsrfError, the root of everything raised
```

## Testing

The suite runs on `pytest` with `anyio`; the storages are exercised over a real
[xtr-http-foundation](../xtr-http-foundation) `Session` on `MemorySessionStorage`, so the
persist-and-reattach path a request actually takes is what the tests prove — not a mock
of it.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-security-csrf`; run the commands below from there. The `python-xtr-security-csrf`
repository is a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
