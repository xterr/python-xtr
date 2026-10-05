from __future__ import annotations

from xtr_storage import exception
from xtr_storage.exception import StorageError

_EXPORTED: tuple[type[StorageError], ...] = (
    exception.ChecksumAlgorithmNotSupportedError,
    exception.CorruptedPathDetectedError,
    exception.FeatureNotSupportedError,
    exception.InvalidArgumentError,
    exception.InvalidStreamError,
    exception.InvalidVisibilityError,
    exception.MissingBackendError,
    exception.PathTraversalDetectedError,
    exception.StorageError,
    exception.StorageOperationFailedError,
    exception.SymbolicLinkEncounteredError,
    exception.UnableToCheckDirectoryExistenceError,
    exception.UnableToCheckExistenceError,
    exception.UnableToCheckFileExistenceError,
    exception.UnableToCopyFileError,
    exception.UnableToCreateDirectoryError,
    exception.UnableToDeleteDirectoryError,
    exception.UnableToDeleteFileError,
    exception.UnableToGeneratePublicUrlError,
    exception.UnableToGenerateTemporaryUrlError,
    exception.UnableToListContentsError,
    exception.UnableToMoveFileError,
    exception.UnableToProvideChecksumError,
    exception.UnableToReadFileError,
    exception.UnableToResolveMountError,
    exception.UnableToRetrieveMetadataError,
    exception.UnableToSetVisibilityError,
    exception.UnableToWriteFileError,
)


def test_every_exported_name_resolves() -> None:
    assert [name for name in exception.__all__ if not hasattr(exception, name)] == []


def test_it_exports_every_error_this_library_raises() -> None:
    assert sorted(exception.__all__) == sorted(error.__name__ for error in _EXPORTED)


def test_every_error_it_exports_derives_from_the_base() -> None:
    assert [error for error in _EXPORTED if not issubclass(error, StorageError)] == []
