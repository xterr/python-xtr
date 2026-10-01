# Password hashing

argon2id by default, older hashes verified and upgraded, one hasher per kind of user. The bundle
builds the hashers from `password_hashers` and registers `PasswordHasherFactoryInterface` and
`UserPasswordHasherInterface`; an application injects the latter.

## Configure

`password_hashers` maps a user class, a `"module:Class"` string or a name the user declares to one
hasher configuration.

| Configuration | What it builds |
| --- | --- |
| `AutoHasherConfig()` | the secure default: argon2id, with bcrypt (when installed) and PBKDF2 verifying behind it |
| `NativeHasherConfig(algorithm="argon2id", time_cost=3, memory_cost=65536, parallelism=4)` | argon2id with those costs |
| `NativeHasherConfig(algorithm="bcrypt", cost=12)` | bcrypt at that cost — 4 to 31 |
| `Pbkdf2HasherConfig(hash_algorithm="sha512", encode_as_base64=True, iterations=1000, key_length=40)` | PBKDF2-HMAC salted from outside — to verify legacy hashes, never asks for a rehash |
| `PlaintextHasherConfig(ignore_case=False)` | the password as it is — **tests only** |
| `ServiceHasherConfig(service=MyHasher, qualifier=None)` | a hasher the container provides |

`NativeHasherConfig` and `Pbkdf2HasherConfig` take `migrate_from=(…)`: hashers whose hashes this
one should still verify, best first. Every value is checked where it is written, so a bad bcrypt
cost or an unavailable digest raises `InvalidArgumentError` as the configuration is built, not on
the first hash.

```python
from xtr_security.bundle import AutoHasherConfig, NativeHasherConfig, Pbkdf2HasherConfig

password_hashers = {
    Account: AutoHasherConfig(),
    MachineAccount: NativeHasherConfig(time_cost=2, memory_cost=32768),
    LegacyAccount: NativeHasherConfig(migrate_from=(Pbkdf2HasherConfig(),)),
}
```

A user may also choose its hasher by name, by implementing
`PasswordHasherAwareInterface.get_password_hasher_name()`.

## Use it

`UserPasswordHasherInterface` reads the stored hash off the user, through
`PasswordAuthenticatedUserInterface` — a `get_password()` returning the stored string. A user
whose salt is stored beside its hash implements `LegacyPasswordAuthenticatedUserInterface`, adding
`get_salt()`, and the salt reaches the hashers that take one.

| Call | Does |
| --- | --- |
| `hash_password(user, plain_password)` | returns the string to store on the user |
| `is_password_valid(user, plain_password)` | verifies the password against the user's stored hash |
| `needs_rehash(user)` | tells whether the stored hash is behind the current settings |

```python
import anyio
from xtr_password_hasher import UserPasswordHasherInterface


class ChangePassword:
    def __init__(self, hasher: UserPasswordHasherInterface) -> None:
        self._hasher = hasher

    async def __call__(self, user: Account, current: str, new: str) -> None:
        if not await anyio.to_thread.run_sync(self._hasher.is_password_valid, user, current):
            raise BadCredentialsError("The current password is wrong.")
        user.password = await anyio.to_thread.run_sync(self._hasher.hash_password, user, new)
```

**Always through a worker thread in async code.** One argon2id hash costs tens of milliseconds of
CPU by design; called on the event loop it stalls every other request for that long.

The single-hasher interface, under the factory, is `hash(plain_password) -> str`,
`verify(hashed_password, plain_password) -> bool`, `needs_rehash(hashed_password) -> bool`; a
`LegacyPasswordHasherInterface` adds a `salt` to `hash` and `verify`. Reach for it only outside a
user:
`NativePasswordHasher()`, `Pbkdf2PasswordHasher()`, `MigratingPasswordHasher(best, *extras)`, or
`create_auto_password_hasher()` for what `AutoHasherConfig()` builds.

## Verify, then upgrade

The moment to replace a hash is right after a successful check, the one time the plaintext is in
hand:

```python
if await anyio.to_thread.run_sync(hasher.is_password_valid, user, attempt):
    if hasher.needs_rehash(user):
        user.password = await anyio.to_thread.run_sync(hasher.hash_password, user, attempt)
```

Behind a firewall you do not write this: the password migrating listener does it for you, provided
the user provider implements `PasswordUpgraderInterface` so the new hash can be stored.

A hash from another stack verifies as long as its backend is present — an `$argon2id$…` string, or
a bcrypt `$2a$` / `$2b$` / `$2y$` string with the `bcrypt` extra of `xtr-password-hasher`
installed — and reports through `needs_rehash` that it should move to argon2id.

## Bounds and errors

A password over `MAX_PASSWORD_LENGTH` (4096) UTF-8 **bytes** is refused by `hash` with
`InvalidPasswordError` and can never verify: a guard against spending a hasher's whole cost on one
unbounded input, not a policy on password length. bcrypt's own 72-byte limit is handled for you —
a longer password is folded through SHA-512 first, on hashing and on verifying alike.

| Error | Raised when |
| --- | --- |
| `InvalidPasswordError` | A password encodes to more than `MAX_PASSWORD_LENGTH` bytes. Also a `ValueError` |
| `UnknownPasswordHasherError` | No hasher is configured for a user, class or name. Also a `LookupError` |
| `InvalidArgumentError` | A hasher or a configuration was given a value it cannot use. Also a `ValueError` |

All three derive from `PasswordHasherError`.

## The command

With a console bundle active and the `console` extra installed:

```sh
security:hash-password [PASSWORD] [USER-CLASS] [--empty-salt]
```

It asks for the password hidden when it is left out (`-` reads it from standard input), and prints
the hasher and the hash — the string to paste into an `InMemoryUserProviderConfig` or a fixture.
With no `USER-CLASS` it hashes for the first class in `password_hashers`, asking which when there
are several and the run is interactive; `USER-CLASS` is a `module:Class` or a configured name. A
hasher salted from outside gets a generated salt, printed with the hash, unless `--empty-salt`.
