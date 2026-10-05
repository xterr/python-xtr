"""Files kept as objects in an S3 bucket, reached through the async s3 backend."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, final
from urllib.parse import quote

from typing_extensions import override

from xtr_storage.adapter._object_store import (
    directory_exists,
    is_directory_marker,
    select_allowed,
)
from xtr_storage.adapter.fsspec_adapter import FsspecAdapter
from xtr_storage.config import Config
from xtr_storage.exception import (
    ChecksumAlgorithmNotSupportedError,
    MissingBackendError,
    UnableToCreateDirectoryError,
    UnableToGenerateTemporaryUrlError,
    UnableToProvideChecksumError,
    UnableToRetrieveMetadataError,
    UnableToSetVisibilityError,
)
from xtr_storage.file_attributes import FileAttributes
from xtr_storage.path.path_prefixer import PathPrefixer
from xtr_storage.visibility import Visibility

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Awaitable, Callable

    from fsspec import (  # pyright: ignore[reportMissingTypeStubs] -- fsspec ships no type information; imported only to name what this adapter builds
        AbstractFileSystem,
    )

    from xtr_storage.mime_type.mime_type_detector_interface import MimeTypeDetectorInterface

__all__ = ["S3Adapter"]

_DEFAULT_REGION: Final = "us-east-1"
"""The region a public url falls back to when the bucket names none."""

_ALL_USERS_URI: Final = "http://acs.amazonaws.com/groups/global/AllUsers"
"""The grantee an object-level access list names when anyone may read a file."""

_PUBLIC_PERMISSIONS: Final = frozenset({"READ", "FULL_CONTROL"})
"""The permissions that, granted to everyone, make a file publicly readable."""

_WRITE_KEYS: Final = frozenset(
    {
        "ACL",
        "CacheControl",
        "ContentDisposition",
        "ContentEncoding",
        "ContentLanguage",
        "ContentType",
        "Expires",
        "Metadata",
        "StorageClass",
        "ServerSideEncryption",
        "SSEKMSKeyId",
        "Tagging",
    }
)
"""The write settings this backend understands; anything else a write drops."""

_CONTENT_TYPE_HINT: Final = "__xtr_storage_s3_content_type__"
"""A private option the write methods stash a detected media type under.

The base builds write settings from a :class:`~xtr_storage.config.Config` that
carries no path, so a media type guessed from the name is threaded through the
configuration under this key — never forwarded to the backend, since it is not
in :data:`_WRITE_KEYS` — and read back by :meth:`S3Adapter._write_options`.
"""


@final
class S3Adapter(FsspecAdapter):
    """An S3 bucket, and an optional key prefix within it, as one storage.

    What an object store adds to the shared base is all here. A directory is a
    zero-byte marker object, since the store keeps none of its own, and those
    markers are hidden from listings and answered for by an existence check that
    knows to look for them. Visibility is a canned access list — public-read or
    private — set on write and copy and read back from the object's grants.
    A checksum is the entity tag the store already holds, handed out only when
    ``"etag"`` is asked for so the storage falls back to hashing the bytes for
    anything else. And a file has two addresses: a lasting public one composed
    from the bucket and region, and a temporary signed one the backend produces.

    Nothing is opened by construction: the backend package is imported and the
    client built on the first operation, so an application may declare a bucket
    it never touches and pay nothing for it. Credentials handed in are kept for
    that first build and never reach a message or a representation.
    """

    _bucket: str
    _key_prefixer: PathPrefixer
    _region: str | None
    _endpoint_url: str | None
    _key: str | None
    _secret: str | None
    _token: str | None
    _anon: bool
    _client_kwargs: dict[str, object]
    _config_kwargs: dict[str, object]
    _configured_write_options: dict[str, object]

    def __init__(  # noqa: PLR0913 -- an object store's connection surface is wide: bucket, prefix, region, endpoint, three credentials and three option maps, each a distinct concern
        self,
        bucket: str,
        prefix: str = "",
        *,
        region: str | None = None,
        endpoint_url: str | None = None,
        key: str | None = None,
        secret: str | None = None,
        token: str | None = None,
        anon: bool = False,
        client_kwargs: Mapping[str, object] | None = None,
        config_kwargs: Mapping[str, object] | None = None,
        write_options: Mapping[str, object] | None = None,
        mime_type_detector: MimeTypeDetectorInterface | None = None,
    ) -> None:
        """Remember the bucket, the prefix and the credentials, and open nothing.

        Args:
            bucket: The bucket every object is stored in.
            prefix: A key prefix under which this storage's objects live, so one
                bucket may hold several storages. Empty for the whole bucket.
            region: The bucket's region, used to compose a public url; defaults
                to ``us-east-1`` there when left out.
            endpoint_url: An alternate endpoint — a compatible store, a local
                test server — used for both requests and composed public urls.
            key: The access key id, or ``None`` to let the backend find one.
            secret: The secret access key, paired with ``key``.
            token: A session token, for temporary credentials.
            anon: Whether to reach the store without credentials.
            client_kwargs: Extra keyword settings for the underlying client,
                merged after the region.
            config_kwargs: Extra client configuration for the underlying client.
            write_options: Default write settings; only the keys this backend
                understands are forwarded, the rest dropped.
            mime_type_detector: How a media type is guessed from a name when a
                write names none; a name-only detector by default.
        """
        stripped_bucket = bucket.strip("/")
        stripped_prefix = prefix.strip("/")
        root = f"{stripped_bucket}/{stripped_prefix}" if stripped_prefix else stripped_bucket
        super().__init__(root, mime_type_detector=mime_type_detector)
        self._bucket = stripped_bucket
        self._key_prefixer = PathPrefixer(stripped_prefix)
        self._region = region
        self._endpoint_url = endpoint_url
        self._key = key
        self._secret = secret
        self._token = token
        self._anon = anon
        self._client_kwargs = dict(client_kwargs) if client_kwargs is not None else {}
        self._config_kwargs = dict(config_kwargs) if config_kwargs is not None else {}
        self._configured_write_options = dict(write_options) if write_options is not None else {}

    @override
    def _create_filesystem(self) -> AbstractFileSystem:
        """Import the backend and build an asynchronous client for the bucket.

        The import happens here rather than at module load so an application
        without the extra installed pays nothing until it uses this adapter, and
        gets a clear error naming the extra when it does.

        Raises:
            MissingBackendError: When the backend package is not installed.
        """
        try:
            import s3fs  # noqa: PLC0415  # pyright: ignore[reportMissingTypeStubs] -- imported lazily so an application without the extra pays nothing; s3fs ships no type information
        except ImportError as error:
            raise MissingBackendError("s3fs", "s3") from error
        client_kwargs = dict(self._client_kwargs)
        if self._region is not None:
            _ = client_kwargs.setdefault("region_name", self._region)
        return s3fs.S3FileSystem(
            asynchronous=True,
            skip_instance_cache=True,
            use_listings_cache=False,
            key=self._key,
            secret=self._secret,
            token=self._token,
            anon=self._anon,
            endpoint_url=self._endpoint_url,
            client_kwargs=client_kwargs,
            config_kwargs=self._config_kwargs or None,
        )

    @override
    def _session_closer(self) -> Callable[[AbstractFileSystem], Awaitable[None]] | None:
        """Return the coroutine that shuts the backend client down on close.

        The asynchronous client the backend opens has no finalizer registered,
        so an owner must close it explicitly or leak the session. The creator
        context the backend keeps is closed here, which shuts every client it
        made, and it only exists once a session was opened — hence the guard.
        """

        async def close(filesystem: AbstractFileSystem) -> None:
            creator = getattr(filesystem, "_s3creator", None)
            if creator is not None:
                _ = await creator.__aexit__(None, None, None)  # pyright: ignore[reportAny] -- s3fs ships no type information; _s3creator is its async client-creator context

        return close

    @override
    def _is_hidden_entry(self, path: str) -> bool:
        """Hide the marker objects that stand in for directories from listings."""
        return is_directory_marker(path)

    @override
    def _write_options(self, config: Config) -> Mapping[str, object]:
        """Build the write settings a put forwards: allowed keys, acl, media type.

        The configured defaults are filtered to the keys the backend accepts, a
        visibility named in the call becomes a canned access list, and a media
        type guessed from the name fills in when neither the call nor the
        defaults set one.
        """
        options = select_allowed(self._configured_write_options, _WRITE_KEYS)
        visibility = config.visibility_option(Config.VISIBILITY)
        if visibility is not None:
            options["ACL"] = _acl_for(visibility)
        hint = config.get(_CONTENT_TYPE_HINT)
        if "ContentType" not in options and isinstance(hint, str):
            options["ContentType"] = hint
        return options

    @override
    async def write(self, path: str, contents: bytes, config: Config) -> None:
        """Write ``contents`` at ``path``, its media type guessed from the name."""
        await super().write(path, contents, self._with_detected_type(path, config))

    @override
    async def write_stream(self, path: str, contents: AsyncIterable[bytes], config: Config) -> None:
        """Stream ``contents`` to ``path``, its media type guessed from the name."""
        await super().write_stream(path, contents, self._with_detected_type(path, config))

    def _with_detected_type(self, path: str, config: Config) -> Config:
        """Return ``config`` carrying a media type guessed from ``path``, if any.

        The guess is laid under the configured options — an explicit content
        type keeps precedence — and stored under a private key the backend never
        sees, since the base has no path to guess from itself.
        """
        detected = self._mime_detector.detect_from_path(path)
        if detected is None:
            return config
        return config.with_defaults({_CONTENT_TYPE_HINT: detected})

    @override
    async def create_directory(self, path: str, config: Config) -> None:
        """Write the zero-byte marker object that stands in for the directory."""
        del config
        location = self._prefixer.prefix_directory_path(path)
        try:
            await self._get_bridge().pipe_file(location, b"")
        except OSError as error:
            raise UnableToCreateDirectoryError(path) from error

    @override
    async def directory_exists(self, path: str) -> bool:
        """Return whether a marker or any object lives under the directory ``path``."""
        location = self._prefixer.prefix_directory_path(path)
        return await directory_exists(self._get_bridge(), location)

    @staticmethod
    @override
    def _content_type(info: Mapping[str, object]) -> str | None:
        """Ignore the type the store stamps on every object; trust the name instead.

        A store gives every object a media type, inventing a generic one for a
        write that named none, so reading it back would report that invention
        for a file whose name says nothing. The name-based detector the base
        falls back to is the very source a write records the type from, so what
        is read and what is written agree, and an unrecognised name has no type
        at all rather than the store's stand-in.
        """
        del info
        return None

    @override
    async def visibility(self, path: str) -> FileAttributes:
        """Return who may read ``path``, read from the object's access list.

        Raises:
            UnableToRetrieveMetadataError: When the object is missing or its
                access list could not be read.
        """
        try:
            grants = await self._get_bridge().call(
                "call_s3",
                "get_object_acl",
                Bucket=self._bucket,
                Key=self._key_prefixer.prefix_path(path),
            )
        except FileNotFoundError as error:
            raise UnableToRetrieveMetadataError.visibility(
                path, "the file does not exist"
            ) from error
        except OSError as error:
            raise UnableToRetrieveMetadataError.visibility(path) from error
        return FileAttributes(path=path, visibility=_visibility_from_grants(grants))

    @override
    async def set_visibility(self, path: str, visibility: Visibility) -> None:
        """Set ``path``'s canned access list to the one ``visibility`` means.

        Raises:
            UnableToSetVisibilityError: When the object is missing or the change
                was refused.
        """
        location = self._prefixer.prefix_path(path)
        try:
            _ = await self._get_bridge().call("chmod", location, _acl_for(visibility))
        except FileNotFoundError as error:
            raise UnableToSetVisibilityError(path, "the file does not exist") from error
        except OSError as error:
            raise UnableToSetVisibilityError(path) from error

    async def checksum(self, path: str, config: Config) -> str:
        """Return the entity tag the store holds for ``path``, quotes stripped.

        Args:
            path: The file to digest, already normalized.
            config: The options in force; only ``"etag"`` is answered from here.

        Returns:
            The entity tag, without the quotes the store wraps it in.

        Raises:
            ChecksumAlgorithmNotSupportedError: When any algorithm but ``"etag"``
                is asked for — the storage's cue to hash the bytes instead.
            UnableToProvideChecksumError: When the store kept no entity tag.
            UnableToRetrieveMetadataError: When the object is missing.
        """
        algorithm = config.str_option(Config.CHECKSUM_ALGORITHM, "md5")
        if algorithm != "etag":
            raise ChecksumAlgorithmNotSupportedError(path, algorithm)
        info = await self._info(path, "checksum")
        etag = info.get("ETag")
        if not isinstance(etag, str) or etag == "":
            raise UnableToProvideChecksumError(path, "the backend kept no entity tag")
        return etag.strip('"')

    async def public_url(self, path: str, config: Config) -> str:
        """Return a lasting address for ``path``, composed from bucket and region.

        Args:
            path: The file to address, already normalized.
            config: The options in force; unread here.

        Returns:
            An absolute url. When an endpoint was configured the address is
            path-style under it; otherwise it is the virtual-hosted address in
            the bucket's region, ``us-east-1`` when none was named.
        """
        del config
        quoted_key = quote(self._key_prefixer.prefix_path(path))
        if self._endpoint_url is not None:
            return f"{self._endpoint_url.rstrip('/')}/{self._bucket}/{quoted_key}"
        region = self._region or _DEFAULT_REGION
        return f"https://{self._bucket}.s3.{region}.amazonaws.com/{quoted_key}"

    async def temporary_url(self, path: str, expires_at: datetime, config: Config) -> str:
        """Return a signed address for ``path``, good until ``expires_at``.

        Args:
            path: The file to address, already normalized.
            expires_at: When the address stops working; a timezone-aware moment
                the storage has already vouched for.
            config: The options in force; unread here.

        Returns:
            An absolute, signed url.

        Raises:
            UnableToGenerateTemporaryUrlError: When the address could not be
                signed.
        """
        del config
        seconds = max(1, int((expires_at - datetime.now(UTC)).total_seconds()))
        location = self._prefixer.prefix_path(path)
        try:
            return await self._get_bridge().sign(location, seconds)
        except (OSError, ValueError) as error:
            raise UnableToGenerateTemporaryUrlError(path) from error


def _acl_for(visibility: Visibility) -> str:
    """Return the canned access list a visibility maps to."""
    match visibility:
        case Visibility.PUBLIC:
            return "public-read"
        case Visibility.PRIVATE:
            return "private"


def _visibility_from_grants(acl: object) -> Visibility:
    """Read a visibility off an object's access list.

    Public when the everyone group is granted read — or full control — and
    private otherwise. The untyped surface the backend returns is crossed once,
    in :func:`_grant_mappings`, so this walk reads only typed mappings.
    """
    for grant in _grant_mappings(acl):
        grantee = _child_mapping(grant, "Grantee")
        if grantee.get("URI") == _ALL_USERS_URI and grant.get("Permission") in _PUBLIC_PERMISSIONS:
            return Visibility.PUBLIC
    return Visibility.PRIVATE


def _grant_mappings(acl: object) -> list[Mapping[str, object]]:
    """Return the grant mappings of an untyped access list, malformed ones dropped.

    The one place the untyped access list the backend returns is reached into;
    every grant that comes back is a mapping the rest of the module can read
    without the checker's blindness spreading past here.
    """
    if not isinstance(acl, Mapping):
        return []
    raw = acl.get("Grants")  # pyright: ignore[reportUnknownMemberType] -- the access list is an untyped backend object
    if not isinstance(raw, list):
        return []
    return [grant for grant in raw if isinstance(grant, Mapping)]  # pyright: ignore[reportUnknownVariableType] -- the access list is an untyped backend object


def _child_mapping(mapping: Mapping[str, object], key: str) -> Mapping[str, object]:
    """Return the nested mapping under ``key``, or an empty one when there is none."""
    value = mapping.get(key)
    if isinstance(value, Mapping):
        return value  # pyright: ignore[reportUnknownVariableType] -- narrowed from an untyped backend value
    return {}
