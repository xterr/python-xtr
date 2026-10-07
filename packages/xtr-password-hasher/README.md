<div align="center">

# xtr-password-hasher

**Password hashing behind one interface: argon2id by default, legacy hashes verified and upgraded.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

Storing a password is not "call a hash function". It is choosing an algorithm strong enough for
today, reading back hashes made by yesterday's choice, and moving each account to the current one
the next time its owner signs in — without the calling code knowing which era a hash came from.

This package puts all of that behind one small interface:

- 🔐 **argon2id by default** — memory-hard, so a stolen hash is expensive to attack; bcrypt and
  PBKDF2 are there to read hashes other stacks made.
- 🔁 **Verify then upgrade** — a hash made by an older algorithm still verifies, and
  `needs_rehash` tells you the moment to replace it (right after a successful check, the one time
  the plaintext is in hand).
- 🧩 **One hasher per user kind** — a factory picks the hasher by the user's class or a name it
  declares, so people and machine accounts can hash differently.
- 🪶 **One runtime dependency** — [pwdlib](https://frankie567.github.io/pwdlib/) with argon2.

> The `xtr-security` bundle configures this package — the factory, a user-facing hasher and the
> `security:hash-password` command — for an application on
> [xtr-dependency-injection](../xtr-dependency-injection). This package ships no bundle of its own.

```python
hasher = NativePasswordHasher()
stored = hasher.hash("correct horse battery staple")
hasher.verify(stored, "correct horse battery staple")  # True
```

## Install

```sh
uv add xtr-password-hasher                 # argon2id, PBKDF2 and plaintext
uv add "xtr-password-hasher[bcrypt]"       # + bcrypt, for hashes from other stacks
uv add "xtr-password-hasher[console]"      # + the security:hash-password command
```

Requires Python 3.11+.

## Quick start

```python
from xtr_password_hasher import NativePasswordHasher

hasher = NativePasswordHasher()  # argon2id

stored = hasher.hash(plain)  # keep this string; it describes its own algorithm
...
if hasher.verify(stored, attempt):
    if hasher.needs_rehash(stored):
        stored = hasher.hash(attempt)  # re-store under the current settings
```

Per-user hashing goes through a factory and the user hasher, which reads the stored hash off the
user itself:

```python
from xtr_password_hasher import NativePasswordHasher, PasswordHasherFactory, UserPasswordHasher


class Account:
    def __init__(self, password: str | None = None) -> None:
        self._password = password

    def get_password(self) -> str | None:
        return self._password


hasher = UserPasswordHasher(PasswordHasherFactory({Account: NativePasswordHasher()}))

account = Account(hasher.hash_password(Account(), "s3cret"))
hasher.is_password_valid(account, "s3cret")  # True
hasher.needs_rehash(account)  # False, until the settings change
```

A password that encodes to more than `MAX_PASSWORD_LENGTH` (4096) UTF-8 bytes is refused by `hash`
with `InvalidPasswordError` and can never match in `verify` — a guard against spending a hasher's
whole cost on one unbounded input, not a policy on how long a password may be. The bound is on
bytes, not characters, because that is the work a hasher reads: a multi-byte character costs its
bytes.

## Hashers

| Hasher | What it is |
|---|---|
| `NativePasswordHasher` | argon2id (default) or bcrypt, on pwdlib; verifies hashes of either when the backend is installed |
| `Pbkdf2PasswordHasher` | PBKDF2-HMAC from the standard library, salted from outside — for legacy hashes |
| `PlaintextPasswordHasher` | stores the password as it is, `{salt}` appended — **tests only** |
| `MigratingPasswordHasher` | hashes with a preferred hasher, verifies older ones behind it |

Every hasher answers the same three methods — `hash(plain_password) -> str`,
`verify(hashed_password, plain_password) -> bool`, `needs_rehash(hashed_password) -> bool` — so
they compose. `MigratingPasswordHasher(best, *extras)` hashes new passwords with `best`, verifies a
hash `best` recognises with `best` alone, and offers a hash it does not to each extra in turn.
Never put a `PlaintextPasswordHasher` among the extras: a leaked hash would then be a working
password.

### Hashers salted from outside

argon2id and bcrypt mint a salt and keep it inside the hash. Older schemes stored the salt in a
column of its own and only the digest in the hash; a hasher for those implements
`LegacyPasswordHasherInterface`, whose `hash` and `verify` take a `salt` (`None` for none):

```python
from xtr_password_hasher import Pbkdf2PasswordHasher

hasher = Pbkdf2PasswordHasher()  # sha512, base64, 1000 iterations, 40 bytes
hasher.verify(stored_digest, attempt, stored_salt)
```

`Pbkdf2PasswordHasher(algorithm="sha512", encode_hash_as_base64=True, iterations=1000,
length=40)` writes the derived key alone, base64 or hex; its defaults are the ones such hashes were
typically made with. The hash carries no parameters, so `needs_rehash` is always `False` — keep it
behind a self-salting hasher in a `MigratingPasswordHasher`, which passes the salt on to the
hashers that take one. `PlaintextPasswordHasher(ignore_password_case=False)` merges a salt as
`password{salt}` and refuses a salt holding `{` or `}`.

A user whose salt is stored beside its password implements
`LegacyPasswordAuthenticatedUserInterface` — `get_salt()` next to `get_password()` — and
`UserPasswordHasher` hands that salt to the hasher. Both interfaces share their method names with
the self-salting ones, so `isinstance` cannot tell them apart: ask
`is_legacy_password_hasher(hasher)`, which checks the declared interface.

## Migrating legacy hashes

argon2id is the default because it is memory-hard: an attacker needs both time and a lot of memory
per guess, which blunts the massively parallel hardware that makes bcrypt and PBKDF2 cheaper to
attack. New passwords should be argon2id.

But you rarely start clean. A `NativePasswordHasher` verifies a hash produced by another stack as
long as its backend is present — an `$argon2id$…` string, or a bcrypt `$2a$` / `$2b$` / `$2y$`
string with the `bcrypt` extra installed — and reports it through `needs_rehash` so it is upgraded
on the next successful sign-in. The `auto` configuration builds exactly this: argon2id in front,
bcrypt (when installed) and PBKDF2 behind it.

**bcrypt's 72-byte limit.** bcrypt reads at most 72 bytes and refuses a longer input outright. A
longer password is folded first — the base64 of its SHA-512 digest, cut to the 72 bytes bcrypt
would itself have kept — on both hashing and verifying, so a long password stays stable here. This
folding is this package's own convention, not a standard: a hash from another stack verifies only
when that stack folds long inputs the same way. A password of up to 72 bytes is passed through
untouched, so those interoperate regardless.

## Hashing off the event loop

A single argon2id hash costs tens of milliseconds of CPU by design. That is fine in a script or a
command, but in an async server it would block the event loop and stall every other request for
that whole time. The hashers are synchronous and CPU-bound on purpose; call them through a worker
thread in async code:

```python
import anyio

stored = await anyio.to_thread.run_sync(hasher.hash, plain)
ok = await anyio.to_thread.run_sync(hasher.verify, stored, attempt)
```

## In an application

This package ships no bundle. The [`xtr-security`](../xtr-security#use-in-an-application) bundle
configures it for an application on
[xtr-dependency-injection](../xtr-dependency-injection): it registers a
`PasswordHasherFactoryInterface`, a `UserPasswordHasherInterface`, and the `security:hash-password`
command, and maps user classes to hashers through the security configuration. A service then asks
for either interface by its type:

```python
from xtr_password_hasher import UserPasswordHasherInterface


class SignUp:
    def __init__(self, hasher: UserPasswordHasherInterface) -> None:
        self._hasher = hasher
```

`PasswordHasherFactory` takes a mapping of user class, `"module:Class"` string or declared name to
a **ready hasher instance** — the factory carries no configuration vocabulary, so it hashes the
same standalone as it does behind a container. Turning inert configuration (argon2 costs, migrating
chains, a hasher the container provides) into a live hasher is the security bundle's job: it reads
the `password_hashers` of the security configuration, builds each hasher, and hands the factory the
instances. `create_auto_password_hasher()` builds the one an application gets when it asks for no
particular hasher — argon2id, with bcrypt (when installed) and PBKDF2 verifying behind it — and is
what the bundle's `auto` configuration builds. A user chooses its hasher by class (walking its bases), or by a name it returns
from `PasswordHasherAwareInterface.get_password_hasher_name()`.

## Console command

With the `console` extra, once the `xtr-security` bundle registers it:

| Command | Does |
|---|---|
| `security:hash-password [PASSWORD] [USER-CLASS] [--empty-salt]` | Hashes `PASSWORD` with the hasher configured for `USER-CLASS` and prints the hasher, the hash and any generated salt |

The command takes the factory and the configured user classes from its constructor —
`UserPasswordHashCommand(factory, user_classes)`; the security bundle supplies both. With no
`USER-CLASS` it hashes for the first configured user class, asking which when several are
configured and the run is interactive; `USER-CLASS` is a `module:Class` or the name of a
configured hasher.

The password is asked for, hidden, when left out, and must not be blank. A password given as an
argument lands in the shell history and the process list, so an interactive run warns about it;
`-` reads it from standard input instead (`echo "$PASSWORD" | … security:hash-password -n -- -`).
A hasher salted from outside gets a generated salt — 30 random bytes, base64 — printed with the
hash for you to store beside it, after a confirmation when the run is interactive; `--empty-salt`
hashes without one.

## Errors

Every error derives from `PasswordHasherError` and carries what went wrong as typed attributes.

| Error | Raised when |
|---|---|
| `InvalidPasswordError` | A password encodes to more than `MAX_PASSWORD_LENGTH` UTF-8 bytes (also a `ValueError`) |
| `UnknownPasswordHasherError` | No hasher is configured for a user, class or name (also a `LookupError`) |
| `InvalidArgumentError` | A hasher or a config is given a value it cannot use (also a `ValueError`) |

## Layout

```
xtr_password_hasher/
├── password_hasher_interface.py            hash / verify / needs_rehash, and MAX_PASSWORD_LENGTH
├── legacy_password_hasher_interface.py     the same, salted from outside; is_legacy_password_hasher
├── password_authenticated_user_interface.py
├── legacy_password_authenticated_user_interface.py
├── hasher/                                 the hashers, the factory, the user hasher,
│                                           and create_auto_password_hasher
├── command/                                security:hash-password (UserPasswordHashCommand)
└── exception/                              one error per module, all a PasswordHasherError
```

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-password-hasher`; run the commands below from there. The
`python-xtr-password-hasher` repository is a read-only copy, so send issues and pull requests to
the monorepo.

```sh
uv sync --all-extras
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
