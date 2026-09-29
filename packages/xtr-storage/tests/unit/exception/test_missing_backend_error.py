from __future__ import annotations

from xtr_storage.exception import MissingBackendError, StorageError


def test_it_carries_the_package_and_the_extra() -> None:
    error = MissingBackendError("s3fs", "s3")

    assert error.package == "s3fs"
    assert error.extra == "s3"


def test_its_message_names_the_package_and_how_to_install_it() -> None:
    error = MissingBackendError("s3fs", "s3")

    assert "s3fs" in str(error)
    assert "xtr-storage[s3]" in str(error)


def test_it_names_the_extra_of_the_backend_it_is_built_for() -> None:
    error = MissingBackendError("gcsfs", "gcs")

    assert str(error) == 'this storage needs the "gcsfs" package: install "xtr-storage[gcs]".'


def test_it_is_also_an_import_error() -> None:
    error = MissingBackendError("s3fs", "s3")

    assert isinstance(error, StorageError)
    assert isinstance(error, ImportError)
