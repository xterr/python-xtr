"""A backend does not hand out checksums of the algorithm that was asked for."""

from __future__ import annotations

from .unable_to_provide_checksum_error import UnableToProvideChecksumError

__all__ = ["ChecksumAlgorithmNotSupportedError"]


class ChecksumAlgorithmNotSupportedError(UnableToProvideChecksumError):
    """The backend keeps checksums, but not in the algorithm that was asked for.

    An object store hands out the digests it happens to hold — an entity tag,
    an MD5 it recorded on upload — and nothing else. A storage treats this as
    "ask me differently", not as a failure: it reads the file and computes the
    digest itself. It surfaces only when a caller went to the backend directly.

    Attributes:
        location: The path a checksum was wanted for, as the caller gave it.
        algorithm: The algorithm that was asked for.
        reason: Why there is none.
    """

    algorithm: str

    def __init__(self, location: str, algorithm: str) -> None:
        """Record the path and the algorithm the backend does not keep."""
        self.algorithm = algorithm
        super().__init__(location, f"this backend has no {algorithm!r} checksum")
