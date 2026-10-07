---
name: xtr-storage
description: How to read, write, list, copy and move files with xtr-storage behind one async interface, on local disk, in memory, in Amazon S3, in Google Cloud Storage or on any fsspec backend. Use when code stores uploads, reports, exports or other files, must work against a disk in development and a bucket in production, needs public or signed urls, file visibility, checksums, streaming of large files, several named storages or a read-only or path-prefixed view; also when adding StorageBundle and named storages to an application on xtr-dependency-injection, or testing code that writes files.
---

# xtr-storage

Where the bytes live is a constructor argument. A `Storage` wraps one adapter and turns paths into
reads, writes, listings, copies and moves; swapping the adapter moves the files without touching
the code that stores them. Every call that reaches the backend is awaited.

## Quick reference

- Depend on `StorageOperatorInterface` (or `StorageReaderInterface` / `StorageWriterInterface`),
  never on an adapter or on `Storage` itself.
- Build one: `Storage(LocalAdapter("var/storage"))`, `Storage(InMemoryAdapter())`,
  `Storage(S3Adapter("bucket", prefix="avatars"))`.
- Write and read: `await storage.write("a/b.txt", b"...")`, `await storage.read("a/b.txt")`.
- Large files: `storage.read_stream(path)` and `await storage.write_stream(path, chunks)`.
- Per-call options lay over the storage's own: `await storage.write(path, data, {"visibility": "public"})`.
- Close what you build: `async with Storage(adapter) as storage:`, or `await storage.close()`.
- Several storages behind one: `MountManager({"uploads": ..., "reports": ...})`, paths `uploads://a.png`.
- In an application: activate `StorageBundle`, inject `StorageOperatorInterface`.

## Read and write

```python
from xtr_storage import InMemoryAdapter, Storage, Visibility


async def main() -> None:
    async with Storage(InMemoryAdapter()) as storage:
        await storage.write("notes/todo.txt", b"buy milk", {"visibility": Visibility.PUBLIC})
        data = await storage.read("notes/todo.txt")  # b"buy milk"
        await storage.file_exists("notes/todo.txt")  # True
        await storage.mime_type("notes/todo.txt")  # "text/plain"
        await storage.file_size("notes/todo.txt")  # 8
        await storage.copy("notes/todo.txt", "notes/copy.txt")
        await storage.move("notes/copy.txt", "archive/copy.txt")
        names = sorted([entry.path async for entry in storage.list_contents("notes", deep=True)])
        await storage.delete("notes/todo.txt")
```

| Call | Does |
| --- | --- |
| `read(path)`, `read_stream(path)` | The whole file, or its chunks as an async iterator |
| `write(path, data, config=None)`, `write_stream(path, stream, config=None)` | Creates or replaces; the stream may be async, a plain iterable, or a binary file object |
| `file_exists`, `directory_exists`, `has` | Existence; `has` is either |
| `list_contents(path="", deep=False)` | A lazy listing of `FileAttributes` / `DirectoryAttributes`; nothing is read until iterated |
| `file_size`, `last_modified`, `mime_type`, `visibility` | Metadata |
| `copy`, `move`, `delete`, `delete_directory`, `create_directory` | Changes |
| `set_visibility(path, visibility)` | `Visibility.PUBLIC` or `Visibility.PRIVATE`; each member is its string |
| `checksum(path, config=None)` | The backend's digest when it keeps one, else hashed here |
| `public_url(path)`, `temporary_url(path, expires_at)` | Lasting and expiring addresses |

Paths are normalized before an adapter sees them: backslashes become `/`, `.` and empty segments
drop, and a `..` pops the segment before it. A control or zero-width character raises
`CorruptedPathDetectedError`. A `..` that climbs above the root raises `PathTraversalDetectedError`;
with `allow_relative_path_traversal` set to `False`, any `..` does.

`copy(path, path)` and `move(path, path)` follow an `IdenticalPathPolicy`, set per call or as a
storage default under `Config.COPY_IDENTICAL_PATH` / `Config.MOVE_IDENTICAL_PATH`:

| Policy | Does |
| --- | --- |
| `IGNORE` (`"ignore"`) | Returns as though done, touching nothing; a path with no file there is still reported as a missing source — **the default** |
| `FAIL` (`"fail"`) | Raises `UnableToCopyFileError` / `UnableToMoveFileError` before the backend |
| `TRY` (`"try"`) | Hands it to the adapter: a rewrite, a refusal, or a lost file on a copy-then-delete move |

```python
from xtr_storage import Config, IdenticalPathPolicy

await storage.copy("a.txt", "a.txt", {Config.COPY_IDENTICAL_PATH: IdenticalPathPolicy.FAIL})
```

## Pick an adapter

| Adapter | Where | Extra | Visibility | Urls |
| --- | --- | --- | --- | --- |
| `LocalAdapter(root)` | A directory on this machine | — | permission bits | only through a configured generator |
| `InMemoryAdapter()` | A dictionary in this process | — | remembered per file | only through a configured generator |
| `S3Adapter(bucket, prefix=..., region=...)` | An S3 bucket | `s3` | access list | public and signed |
| `GcsAdapter(bucket, prefix=...)` | A Google Cloud Storage bucket | `gcs` | refused | public and signed |
| `GenericFsspecAdapter(filesystem, root=...)` | Any fsspec filesystem | — | refused | only through a configured generator |
| `ReadOnlyAdapter(adapter)` | Any of the above, writes refused | — | as wrapped | as wrapped |
| `PathPrefixedAdapter(adapter, prefix)` | Any of the above, under a prefix | — | as wrapped | as wrapped |

An adapter whose extra is missing raises `MissingBackendError` naming it. A capability a backend
lacks raises `FeatureNotSupportedError` instead of guessing. No adapter opens anything when built;
`LocalAdapter` creates its root on the first write.

`LocalAdapter(root, link_handling=...)` decides what a *listing* does with a symbolic link:
`LinkHandling.DISALLOW` (the default) raises `SymbolicLinkEncounteredError`, `LinkHandling.SKIP`
leaves it out. Neither follows a link out of the root — any operation naming a path a link carries
above the root is refused — so `SKIP` hides a link, it does not open a door through it.

## Several storages

```python
from xtr_storage import InMemoryAdapter, MountManager, Storage


async def main() -> None:
    async with MountManager(
        {"uploads": Storage(InMemoryAdapter()), "reports": Storage(InMemoryAdapter())}
    ) as files:
        await files.write("uploads://a.txt", b"hi")
        await files.copy("uploads://a.txt", "reports://a.txt")  # streamed across storages
```

There is no default mount: an unknown name, a missing `://` or an empty name raises
`UnableToResolveMountError`.

## Testing

The package ships no test helpers; `InMemoryAdapter` is the one a test needs.

- Hand the code under test `Storage(InMemoryAdapter())`. Two in-memory adapters share nothing, so
  a test that writes has nothing to undo.
- Assert what was stored by reading it back through the same storage.
- In an application test, replace the service:
  `boot_for_test(kernel, overrides={StorageOperatorInterface: Storage(InMemoryAdapter())})`.

```python
from xtr_storage import InMemoryAdapter, Storage


async def test_the_report_is_stored() -> None:
    storage = Storage(InMemoryAdapter())

    await write_report(storage)

    assert await storage.read("reports/2026.txt") == b"hello"
```

## Use in an application

`uv run xtr-recipes recipes:sync` applies the recipe shipped with this package: it lists
`StorageBundle` and ignores `/var/storage/`. That is the steps below a recipe can do; the others it
prints for you to make.

1. **Install** — `uv add "xtr-storage[di]"`; add `s3` or `gcs` for the object stores you reach.
2. **Activate** — `StorageBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`, imported from
   `xtr_storage.bundle`.
3. **Brings along** — nothing; the bundle requires no other.
4. **Configure** — optional; with no configuration there is one `default` storage on local files
   under `var/storage`, and nothing is opened until it is first used:

   ```python
   # <app>/config/storage.py
   from xtr_dependency_injection import configure, env
   from xtr_storage.bundle import LocalAdapterConfig, S3AdapterConfig, StorageConfig, StorageDefinition


   @configure
   def storage() -> StorageConfig:
       return StorageConfig(
           storages={
               "default": LocalAdapterConfig(),
               "uploads": StorageDefinition(
                   adapter=S3AdapterConfig(bucket=env("UPLOADS_BUCKET"), region=env("AWS_REGION")),
                   prefix="avatars",
                   visibility="public",
               ),
           },
       )
   ```

   An adapter entry is `LocalAdapterConfig`, `MemoryAdapterConfig`, `S3AdapterConfig`,
   `GcsAdapterConfig`, `FsspecAdapterConfig`, or a `Reference` to an adapter the container
   provides. A `StorageDefinition` adds `visibility`, `directory_visibility`,
   `retain_visibility`, `public_url`, `read_only` and `prefix`.
5. **Environment** — nothing required; credentials and directories given as `env(...)` must be set
   when the application boots, because booting checks every storage.
6. **Ignore** — `/var/storage/` in `.gitignore`.
7. **Use** — inject `StorageOperatorInterface` for the `default` storage, or qualify by name. A
   `MountManager` over every storage is provided too.

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

8. **Check** — `debug:bundles` shows `storage` as `listed` and `active`.
9. **Remove** — drop the `BUNDLES` entry, delete `<app>/config/storage.py`, then
   `uv remove xtr-storage`.

## Errors

Everything derives from `StorageError`; a failure of an operation the backend refused derives from
`StorageOperationFailedError` and names the operation. No message repeats a credential.

| Error | Raised when |
| --- | --- |
| `UnableToReadFileError`, `UnableToWriteFileError` | A read or write fails, or the file is missing |
| `UnableToDeleteFileError`, `UnableToDeleteDirectoryError`, `UnableToCreateDirectoryError` | A delete or a directory creation fails |
| `UnableToCopyFileError`, `UnableToMoveFileError` | A copy or move fails, or the paths are the same under a `fail` policy |
| `UnableToRetrieveMetadataError`, `UnableToSetVisibilityError` | Metadata cannot be read, or a visibility set |
| `UnableToListContentsError` | A listing fails while it is iterated |
| `UnableToProvideChecksumError`, `ChecksumAlgorithmNotSupportedError` | No checksum can be produced |
| `UnableToGeneratePublicUrlError`, `UnableToGenerateTemporaryUrlError` | No url can be produced |
| `UnableToResolveMountError` | A mount location names no storage, or is malformed |
| `PathTraversalDetectedError`, `CorruptedPathDetectedError` | A path climbs past the root, or carries a control character |
| `SymbolicLinkEncounteredError` | A path a symbolic link carries outside a `LocalAdapter`'s root, or a link met in a listing that refuses them |
| `FeatureNotSupportedError` | The backend lacks the capability (also a `NotImplementedError`) |
| `MissingBackendError` | The adapter's extra is not installed (also an `ImportError`) |
| `InvalidVisibilityError`, `InvalidArgumentError` | A bad visibility string or option (also a `ValueError`) |
| `InvalidStreamError` | A write stream of a type the storage cannot read (also a `TypeError`) |

## Do not

- Do not depend on an adapter or on `Storage` in application code; depend on
  `StorageOperatorInterface` and let the container pick the backend.
- Do not build paths with `os.path` or `pathlib`; pass `/`-separated strings, as every backend
  sees them.
- Do not read a large file whole with `read`; stream it with `read_stream` and `write_stream`.
- Do not read `LinkHandling.SKIP` as "links are followed": no link leads out of a `LocalAdapter`'s
  root under either setting.
- Do not expect a backend to fake a capability: GCS and generic fsspec backends refuse visibility,
  and a local or in-memory storage gives urls only through a configured generator.
- Do not leave a storage you built open; use `async with` or `close()`. The container closes the
  ones it built.
- Do not put credentials in code; read them with `env(...)` in `config/storage.py`.
