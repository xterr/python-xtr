<div align="center">

# xtr-storage

**Files on local disk, in memory or in object stores, behind one async interface.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="asyncio" src="https://img.shields.io/badge/asyncio-native-1f6feb">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

Code that stores a file usually names the place in the same breath: an open at a
path, a client call to a bucket. Move the file somewhere else — a disk to a
bucket, a bucket to a dictionary in a test — and every one of those calls has to
be rewritten, because reading a local file and reading an object share no shape.

This package makes the place a constructor argument. A `Storage` wraps one
adapter and turns paths into reads, writes, listings, copies and moves; the
adapter decides where the bytes live. The code that stores files is written
once and moved between backends by swapping the adapter it is handed.

- 📁 **One async contract** — `read`, `write`, `delete`, `list_contents`, `copy`,
  `move`, metadata and urls, every call awaited.
- 🔌 **Seven adapters** — local disk, in-process memory, Amazon S3, Google Cloud
  Storage, any other backend by protocol, plus read-only and path-prefixed
  wrappers around any of them.
- 🧭 **A mount manager** — several storages behind one, each reached by the name
  a location starts with (`"uploads://avatars/1.png"`).
- 🚫 **Honest about limits** — a backend that cannot do a thing raises a clear
  `FeatureNotSupportedError`, never a silent wrong answer.
- 🧩 **A bundle** — named storages configured in Python and injected anywhere,
  with a zero-config default that touches no disk until first use.

```python
from xtr_storage import LocalAdapter, Storage

storage = Storage(LocalAdapter("var/storage"))

await storage.write("reports/2026.txt", b"hello")
report = await storage.read("reports/2026.txt")
```

## Install

```sh
uv add xtr-storage
uv add "xtr-storage[s3]"     # S3Adapter, on the s3fs backend
uv add "xtr-storage[gcs]"    # GcsAdapter, on the gcsfs backend
uv add "xtr-storage[di]"     # the bundle for xtr-dependency-injection
```

Requires Python 3.11+. Every adapter is built on `fsspec`, a required
dependency; the S3 and Google Cloud backends are the optional extras above. An
adapter whose extra is missing raises `MissingBackendError` naming the extra to
install, rather than failing on an obscure import.

## Quick start

A storage is an adapter and, optionally, standing defaults every call starts
from. The in-memory adapter keeps files in a dictionary — nothing to clean up —
and the local adapter keeps them under a directory, created on first write:

```python
import anyio

from xtr_storage import InMemoryAdapter, LocalAdapter, Storage, Visibility


async def main() -> None:
    memory = Storage(InMemoryAdapter())

    await memory.write("notes/todo.txt", b"buy milk", {"visibility": Visibility.PUBLIC})
    print((await memory.read("notes/todo.txt")).decode())  # buy milk
    print(await memory.file_exists("notes/todo.txt"))  # True
    print(await memory.mime_type("notes/todo.txt"))  # text/plain

    async for chunk in memory.read_stream("notes/todo.txt"):
        print(len(chunk))  # 8

    disk = Storage(LocalAdapter("var/storage"))
    await disk.write("greetings/hello.txt", b"hi there")
    await memory.copy("notes/todo.txt", "notes/copy.txt")

    listing = memory.list_contents("notes", deep=True)
    print(sorted([entry.path async for entry in listing]))  # ['notes/copy.txt', 'notes/todo.txt']

    await disk.delete("greetings/hello.txt")
    await memory.close()
    await disk.close()


anyio.run(main)
```

A call's own options are laid over the storage's standing defaults for that call
alone, so one upload can be public without changing the next. A `Storage` is an
async context manager too: `async with Storage(adapter) as storage:` closes the
adapter on the way out.

## Adapters

Every adapter satisfies the same `StorageAdapterInterface`. They differ only in
where the bytes live and which of four capabilities they can offer: setting and
reading **visibility**, handing back a **checksum**, composing a lasting
**public url**, and signing a **temporary url**. A capability a backend lacks is
either worked around by the storage (a checksum is computed by hashing the bytes
when the backend keeps none) or refused with a clear error.

### `LocalAdapter`

```python
from xtr_storage import LocalAdapter, LinkHandling

adapter = LocalAdapter("var/storage", link_handling=LinkHandling.SKIP)
```

Files under one directory on this machine, everything below it and nothing
above. Visibility becomes permission bits through a converter the deployment may
replace; directories a write needs are created with the mode that converter
names, not the process umask. Symbolic links in a listing are either skipped or
refused. Nothing is touched until the first operation — the root is created by
the first write.

| Visibility | Checksum | Public url | Temporary url |
|---|---|---|---|
| ✓ permission bits | ✓ by hashing the bytes | only with a configured generator, else `UnableToGeneratePublicUrlError` | `UnableToGenerateTemporaryUrlError` unless a generator is injected |

### `InMemoryAdapter`

```python
from xtr_storage import InMemoryAdapter, Visibility

adapter = InMemoryAdapter(default_visibility=Visibility.PRIVATE)
```

Files in a dictionary that vanish with the process, each with a visibility
remembered beside it. Two in-memory adapters in one process share no store, so a
test that writes has nothing to undo. What a test reaches for, and what an
application uses to hand bytes between two steps of one request.

| Visibility | Checksum | Public url | Temporary url |
|---|---|---|---|
| ✓ remembered per file | ✓ by hashing the bytes | only with a configured generator, else `UnableToGeneratePublicUrlError` | `UnableToGenerateTemporaryUrlError` unless a generator is injected |

### `S3Adapter`

```python
from xtr_storage import S3Adapter, Storage

storage = Storage(S3Adapter("uploads", prefix="avatars", region="eu-west-1"))
```

An S3 bucket, and an optional key prefix within it, as one storage — through the
`s3` extra. A directory is a zero-byte marker object, hidden from listings.
Visibility is a canned access list, public-read or private. A checksum is the
entity tag the store already holds, handed out for `"etag"`; any other algorithm
falls back to hashing. A file has a lasting public url composed from the bucket
and region (or the endpoint) and a temporary signed one the backend produces.
Credentials handed in are kept for the first client build and never reach a
message. Nothing is opened by construction.

| Visibility | Checksum | Public url | Temporary url |
|---|---|---|---|
| ✓ access list | ✓ `"etag"` from the store, else by hashing | ✓ composed from bucket and region or endpoint | ✓ signed by the backend |

### `GcsAdapter`

```python
from xtr_storage import GcsAdapter, Storage

storage = Storage(GcsAdapter("uploads", prefix="avatars"))
```

A Google Cloud Storage bucket — through the `gcs` extra. Directories are the same
zero-byte fiction. Checksums, public urls and signed urls are real; the native
`"md5"` and `"crc32c"` checksums are read from the object, other algorithms fall
back to hashing. Visibility is refused this version, because the store offers no
single answer to map onto. Nothing is opened by construction.

| Visibility | Checksum | Public url | Temporary url |
|---|---|---|---|
| ✗ raises `FeatureNotSupportedError` | ✓ `"md5"`/`"crc32c"` from the object, else by hashing | ✓ composed from bucket or endpoint | ✓ signed by the backend |

### `GenericFsspecAdapter`

```python
from fsspec.implementations.memory import MemoryFileSystem
from xtr_storage import GenericFsspecAdapter, Storage

storage = Storage(GenericFsspecAdapter(MemoryFileSystem(), root="data"))
```

Any backend this library has no named adapter for. Hand it a filesystem instance
and a root, and it wraps that instance behind the same contract.

| Visibility | Checksum | Public url | Temporary url |
|---|---|---|---|
| ✗ raises `FeatureNotSupportedError` | ✓ by hashing the bytes | only with a configured generator, else `UnableToGeneratePublicUrlError` | `UnableToGenerateTemporaryUrlError` unless a generator is injected |

### `ReadOnlyAdapter` and `PathPrefixedAdapter`

```python
from xtr_storage import PathPrefixedAdapter, ReadOnlyAdapter, S3Adapter, Storage

published = Storage(ReadOnlyAdapter(S3Adapter("assets")))
tenant = Storage(PathPrefixedAdapter(S3Adapter("uploads"), "tenant-42"))
```

Two wrappers around any adapter. `ReadOnlyAdapter` delegates every read and
capability and refuses every write with its own operation error. `PathPrefixedAdapter`
roots an adapter under a prefix — every path is prefixed going in, stripped out
of listings coming back, and errors carry the caller-facing path. An empty
prefix is refused.

## Paths

Every path a caller gives is normalized before an adapter ever sees it, to the
one form the backend is shown: backslashes become forward slashes, `.` segments
and empty segments drop, and `..` pops the segment before it. A path with a
control or zero-width character is refused with `CorruptedPathDetectedError`. A
`..` that would climb past the root is refused with `PathTraversalDetectedError`
when traversal is disallowed — allowed by default, set
`allow_relative_path_traversal=False` in the config to forbid it.

## Visibility

`Visibility` has two members, `PUBLIC` and `PRIVATE`, and each *is* its string
(`"public"`, `"private"`), so an option mapping or an environment variable
carries the word and is understood without a conversion step. An adapter
translates the two into whatever its backend uses — permission bits, an access
list — and one that cannot say so raises rather than guess. Pass a visibility as
a write option, or set it after the fact:

```python
await storage.write("logo.svg", data, {"visibility": "public"})
await storage.set_visibility("logo.svg", Visibility.PRIVATE)
print(await storage.visibility("logo.svg"))  # Visibility.PRIVATE
```

## Streams

Large files never have to land in memory whole. `read_stream` yields the bytes
in chunks; `write_stream` accepts an async iterable of bytes, a plain iterable,
or a binary file object, spooling it to the backend a chunk at a time. A
seekable file object is rewound first; anything else raises `InvalidStreamError`.

```python
async def chunks() -> AsyncIterator[bytes]:
    yield b"part one"
    yield b"part two"


await storage.write_stream("big.bin", chunks())
async for chunk in storage.read_stream("big.bin"):
    ...
```

## Mount manager

A `MountManager` puts several storages behind one, each reached by the name it
was mounted at. Every location reads `<name>://<path>`; there is no default
mount, so a location that went nowhere is an error rather than a silent guess.
A copy or move within one storage is delegated; across two, the manager streams
the bytes from one to the other and carries the visibility when both support it.

```python
from xtr_storage import InMemoryAdapter, MountManager, Storage

files = MountManager(
    {
        "uploads": Storage(InMemoryAdapter()),
        "reports": Storage(InMemoryAdapter()),
    }
)

await files.write("uploads://a.txt", b"hi")
await files.copy("uploads://a.txt", "reports://a.txt")
async for entry in files.list_contents("reports://", deep=True):
    print(entry.path)  # reports://a.txt

await files.close()  # closes every mounted storage
```

An unknown mount, a missing `://`, or an empty name raises
`UnableToResolveMountError`.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read
backwards, what removing it undoes.

- **Install** — `uv add "xtr-storage[di]"`; add `s3` or `gcs` for the object
  stores you reach.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate* and *Ignore*
  steps below: it lists `StorageBundle` and ignores `/var/storage/`. There is no
  config file or environment to write.
- **Activate** — `StorageBundle: {"all": True}` in `BUNDLES` in
  `<app>/bundles.py`, imported from `xtr_storage.bundle`.
- **Brings along** — nothing; the bundle requires no other.
- **Configure** — optional: with no configuration there is one `default` storage
  on local files under `var/storage`. Named storages go in
  `<app>/config/storage.py`, a `@configure` function returning `StorageConfig`
  — see [Kernel / bundle](#kernel--bundle).
- **Environment** — nothing required. Credentials and directories given as
  `env(...)` must be set when the application boots: booting checks every
  storage.
- **Ignore** — `var/storage/`: where the default storage keeps files, under the
  project.
- **Remove** — drop the `BUNDLES` entry, delete `<app>/config/storage.py`, then
  `uv remove xtr-storage`.
- **Check** — `debug:bundles` shows `storage` as `listed` and `active`.

## Kernel / bundle

With [xtr-dependency-injection](../xtr-dependency-injection), list the bundle and
name the storages:

```python
# app/bundles.py
from xtr_storage.bundle import StorageBundle

BUNDLES = {StorageBundle: {"all": True}}
```

```python
# app/config/storage.py
from xtr_dependency_injection import configure, env
from xtr_storage.bundle import LocalAdapterConfig, S3AdapterConfig, StorageConfig, StorageDefinition


@configure
def storage() -> StorageConfig:
    return StorageConfig(
        storages={
            "default": LocalAdapterConfig(),
            "uploads": StorageDefinition(
                adapter=S3AdapterConfig(
                    bucket=env("UPLOADS_BUCKET"),
                    region=env("AWS_REGION"),
                    key=env("AWS_ACCESS_KEY_ID"),
                    secret=env("AWS_SECRET_ACCESS_KEY"),
                ),
                prefix="avatars",
                visibility="public",
            ),
        },
    )
```

Every storage is registered under `StorageOperatorInterface`,
`StorageReaderInterface` and `StorageWriterInterface`, qualified by its name; the
one named `"default"` is provided without a qualifier too. A `MountManager` over
all of them is provided as well.

```python
from typing import Annotated

from xtr_dependency_injection import Target, as_service
from xtr_storage import StorageOperatorInterface


@as_service
class Avatars:
    def __init__(
        self,
        storage: StorageOperatorInterface,  # the default storage
        uploads: Annotated[StorageOperatorInterface, Target("uploads")],
    ) -> None: ...
```

| `StorageConfig` field | Meaning |
|---|---|
| `storages` | Each storage by name: a full `StorageDefinition`, or a bare adapter configuration read as a definition with everything else at its default. An empty mapping means the `default` local storage |

A `StorageDefinition` names an adapter configuration — `LocalAdapterConfig`,
`MemoryAdapterConfig`, `S3AdapterConfig`, `GcsAdapterConfig`,
`FsspecAdapterConfig`, or a `Reference` to an adapter the container provides —
and layers the standing options over it: `visibility`, `directory_visibility`,
`retain_visibility`, `public_url`, `read_only` and `prefix`.

- **Zero config**: one `default` storage on local files under
  `%kernel.project_dir%/var/storage`. Nothing is opened, and no directory is
  created, until a storage is first used.
- **Checked at boot**: booting reads the configuration, `env()` values included,
  and refuses a `Reference` the container does not provide, an adapter whose
  backend extra is not installed, or a visibility set on a backend that has none
  — naming the storage, never a credential.
- **Lifecycle**: when the container closes, every storage closes the connections
  it opened.

## Errors

Every error derives from `StorageError`, so one `except` catches anything
storing a file can go wrong with. The failures of an operation a backend refused
share `StorageOperationFailedError` and name that operation; everything else is a
mistake to fix rather than to retry. No message ever repeats a credential.

| Error | Raised when |
|---|---|
| `UnableToReadFileError` | A read fails or the file is missing |
| `UnableToWriteFileError` | A write fails |
| `UnableToDeleteFileError` / `UnableToDeleteDirectoryError` | A delete fails |
| `UnableToCreateDirectoryError` | A directory cannot be created |
| `UnableToSetVisibilityError` | A visibility cannot be set |
| `UnableToRetrieveMetadataError` | A size, modification time, mime type or visibility cannot be read |
| `UnableToCopyFileError` / `UnableToMoveFileError` | A copy or move fails, or source and destination are the same under a `fail` policy |
| `UnableToCheckExistenceError` (`…File…`, `…Directory…`) | An existence check fails |
| `UnableToListContentsError` | A listing fails while iterating |
| `UnableToProvideChecksumError` | A checksum cannot be produced |
| `ChecksumAlgorithmNotSupportedError` | The backend has no native checksum for the algorithm asked |
| `UnableToGeneratePublicUrlError` / `UnableToGenerateTemporaryUrlError` | No generator is configured, or the backend cannot produce the url |
| `UnableToResolveMountError` | A mount location names no storage, or is malformed |
| `PathTraversalDetectedError` / `CorruptedPathDetectedError` | A path climbs past the root, or carries a control character |
| `SymbolicLinkEncounteredError` | A listing meets a symbolic link a local storage was told to refuse |
| `FeatureNotSupportedError` | A backend is asked for a capability it does not have (also a `NotImplementedError`) |
| `MissingBackendError` | An adapter's extra package is not installed (also an `ImportError`) |
| `InvalidVisibilityError` | A string names no visibility (also a `ValueError`) |
| `InvalidStreamError` | A write stream is of a type the storage cannot read (also a `TypeError`) |
| `InvalidArgumentError` | An argument or option is invalid (also a `ValueError`) |

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo,
under `packages/xtr-storage`; run the commands below from there. The
`python-xtr-storage` repository is a read-only copy, so send issues and pull
requests to the monorepo.

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

The suite reaches no cloud: the S3 adapter runs against a local server kept in
the test process, the Google Cloud adapter against an in-test fake, and every
adapter that stores bytes passes the same conformance tests.

## License

MIT — see [LICENSE](LICENSE).
