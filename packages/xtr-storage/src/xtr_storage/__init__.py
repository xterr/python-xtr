"""Files on local disk, in memory or in object stores, behind one async interface.

A ``Storage`` wraps one adapter and turns paths into reads, writes, listings,
copies and moves. The adapter decides where the bytes live — a directory on this
machine, a dictionary in this process, a bucket on an object store — so code that
stores files is written once and moved between them by its constructor.

Every call that touches a backend is awaited.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from xtr_storage.adapter import (
    FsspecAdapter,
    GcsAdapter,
    GenericFsspecAdapter,
    InMemoryAdapter,
    LocalAdapter,
    PathPrefixedAdapter,
    PortableVisibilityConverter,
    ReadOnlyAdapter,
    S3Adapter,
    StorageAdapterInterface,
    VisibilityConverterInterface,
)
from xtr_storage.checksum_provider_interface import ChecksumProviderInterface
from xtr_storage.config import Config
from xtr_storage.directory_attributes import DirectoryAttributes
from xtr_storage.directory_listing import DirectoryListing
from xtr_storage.exception import (
    ChecksumAlgorithmNotSupportedError,
    CorruptedPathDetectedError,
    FeatureNotSupportedError,
    InvalidArgumentError,
    InvalidStreamError,
    InvalidVisibilityError,
    MissingBackendError,
    PathTraversalDetectedError,
    StorageError,
    StorageOperationFailedError,
    SymbolicLinkEncounteredError,
    UnableToCheckDirectoryExistenceError,
    UnableToCheckExistenceError,
    UnableToCheckFileExistenceError,
    UnableToCopyFileError,
    UnableToCreateDirectoryError,
    UnableToDeleteDirectoryError,
    UnableToDeleteFileError,
    UnableToGeneratePublicUrlError,
    UnableToGenerateTemporaryUrlError,
    UnableToListContentsError,
    UnableToMoveFileError,
    UnableToProvideChecksumError,
    UnableToReadFileError,
    UnableToResolveMountError,
    UnableToRetrieveMetadataError,
    UnableToSetVisibilityError,
    UnableToWriteFileError,
)
from xtr_storage.feature import Feature
from xtr_storage.file_attributes import FileAttributes
from xtr_storage.identical_path_policy import IdenticalPathPolicy
from xtr_storage.link_handling import LinkHandling
from xtr_storage.mime_type import ExtensionMimeTypeDetector, MimeTypeDetectorInterface
from xtr_storage.mount_manager import MountManager
from xtr_storage.operation import Operation
from xtr_storage.path import PathNormalizerInterface, PathPrefixer, WhitespacePathNormalizer
from xtr_storage.storage import Storage
from xtr_storage.storage_attributes import StorageAttributes
from xtr_storage.storage_operator_interface import StorageOperatorInterface
from xtr_storage.storage_reader_interface import StorageReaderInterface
from xtr_storage.storage_writer_interface import StorageWriterInterface
from xtr_storage.url_generation import (
    ChainedPublicUrlGenerator,
    PrefixPublicUrlGenerator,
    PublicUrlGeneratorInterface,
    ShardedPrefixPublicUrlGenerator,
    TemporaryUrlGeneratorInterface,
)
from xtr_storage.visibility import Visibility

try:
    __version__ = version("xtr-storage")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree or a vendored copy, with no installed
    # metadata to read. Having no version is better than refusing to import.
    __version__ = "0+unknown"

__all__ = [
    "ChainedPublicUrlGenerator",
    "ChecksumAlgorithmNotSupportedError",
    "ChecksumProviderInterface",
    "Config",
    "CorruptedPathDetectedError",
    "DirectoryAttributes",
    "DirectoryListing",
    "ExtensionMimeTypeDetector",
    "Feature",
    "FeatureNotSupportedError",
    "FileAttributes",
    "FsspecAdapter",
    "GcsAdapter",
    "GenericFsspecAdapter",
    "IdenticalPathPolicy",
    "InMemoryAdapter",
    "InvalidArgumentError",
    "InvalidStreamError",
    "InvalidVisibilityError",
    "LinkHandling",
    "LocalAdapter",
    "MimeTypeDetectorInterface",
    "MissingBackendError",
    "MountManager",
    "Operation",
    "PathNormalizerInterface",
    "PathPrefixedAdapter",
    "PathPrefixer",
    "PathTraversalDetectedError",
    "PortableVisibilityConverter",
    "PrefixPublicUrlGenerator",
    "PublicUrlGeneratorInterface",
    "ReadOnlyAdapter",
    "S3Adapter",
    "ShardedPrefixPublicUrlGenerator",
    "Storage",
    "StorageAdapterInterface",
    "StorageAttributes",
    "StorageError",
    "StorageOperationFailedError",
    "StorageOperatorInterface",
    "StorageReaderInterface",
    "StorageWriterInterface",
    "SymbolicLinkEncounteredError",
    "TemporaryUrlGeneratorInterface",
    "UnableToCheckDirectoryExistenceError",
    "UnableToCheckExistenceError",
    "UnableToCheckFileExistenceError",
    "UnableToCopyFileError",
    "UnableToCreateDirectoryError",
    "UnableToDeleteDirectoryError",
    "UnableToDeleteFileError",
    "UnableToGeneratePublicUrlError",
    "UnableToGenerateTemporaryUrlError",
    "UnableToListContentsError",
    "UnableToMoveFileError",
    "UnableToProvideChecksumError",
    "UnableToReadFileError",
    "UnableToResolveMountError",
    "UnableToRetrieveMetadataError",
    "UnableToSetVisibilityError",
    "UnableToWriteFileError",
    "Visibility",
    "VisibilityConverterInterface",
    "WhitespacePathNormalizer",
    "__version__",
]
