"""Every error this library raises.

All of them derive from :class:`StorageError`, so one ``except`` catches
anything storing a file can go wrong with, and a narrower one handles a single
cause. The failures of an operation a backend refused share
:class:`StorageOperationFailedError` and name that operation, which is the
clause a retry belongs in; everything else — a path that is not a path, a
capability a backend does not have, a package that is not installed — is a
mistake to fix rather than to retry.

Each carries the data a caller needs as typed attributes rather than forcing a
message to be parsed, and no message ever repeats a credential.
"""

from __future__ import annotations

from .checksum_algorithm_not_supported_error import ChecksumAlgorithmNotSupportedError
from .corrupted_path_detected_error import CorruptedPathDetectedError
from .feature_not_supported_error import FeatureNotSupportedError
from .invalid_argument_error import InvalidArgumentError
from .invalid_stream_error import InvalidStreamError
from .invalid_visibility_error import InvalidVisibilityError
from .missing_backend_error import MissingBackendError
from .path_traversal_detected_error import PathTraversalDetectedError
from .storage_error import StorageError
from .storage_operation_failed_error import StorageOperationFailedError
from .symbolic_link_encountered_error import SymbolicLinkEncounteredError
from .unable_to_check_directory_existence_error import UnableToCheckDirectoryExistenceError
from .unable_to_check_existence_error import UnableToCheckExistenceError
from .unable_to_check_file_existence_error import UnableToCheckFileExistenceError
from .unable_to_copy_file_error import UnableToCopyFileError
from .unable_to_create_directory_error import UnableToCreateDirectoryError
from .unable_to_delete_directory_error import UnableToDeleteDirectoryError
from .unable_to_delete_file_error import UnableToDeleteFileError
from .unable_to_generate_public_url_error import UnableToGeneratePublicUrlError
from .unable_to_generate_temporary_url_error import UnableToGenerateTemporaryUrlError
from .unable_to_list_contents_error import UnableToListContentsError
from .unable_to_move_file_error import UnableToMoveFileError
from .unable_to_provide_checksum_error import UnableToProvideChecksumError
from .unable_to_read_file_error import UnableToReadFileError
from .unable_to_resolve_mount_error import UnableToResolveMountError
from .unable_to_retrieve_metadata_error import UnableToRetrieveMetadataError
from .unable_to_set_visibility_error import UnableToSetVisibilityError
from .unable_to_write_file_error import UnableToWriteFileError

__all__ = [
    "ChecksumAlgorithmNotSupportedError",
    "CorruptedPathDetectedError",
    "FeatureNotSupportedError",
    "InvalidArgumentError",
    "InvalidStreamError",
    "InvalidVisibilityError",
    "MissingBackendError",
    "PathTraversalDetectedError",
    "StorageError",
    "StorageOperationFailedError",
    "SymbolicLinkEncounteredError",
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
]
