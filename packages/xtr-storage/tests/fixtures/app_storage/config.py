"""One storage per kind of adapter the bundle can build; nothing reaches a server."""

from __future__ import annotations

from xtr_dependency_injection import configure, env

from xtr_storage.bundle import (
    FsspecAdapterConfig,
    GcsAdapterConfig,
    LocalAdapterConfig,
    MemoryAdapterConfig,
    S3AdapterConfig,
    StorageConfig,
    StorageDefinition,
)

UNREACHABLE_ENDPOINT = "http://127.0.0.1:1"
"""An endpoint nothing answers on; the s3 and gcs storages point here and are never used."""


@configure
def storage() -> StorageConfig:
    return StorageConfig(
        storages={
            "default": StorageDefinition(),
            "memory": MemoryAdapterConfig(),
            "local": StorageDefinition(
                adapter=LocalAdapterConfig(directory=env("STORAGE_TEST_DIR")),
            ),
            "s3": S3AdapterConfig(
                bucket="unreachable",
                region="us-east-1",
                endpoint_url=UNREACHABLE_ENDPOINT,
                key="testing",
                secret="testing",  # noqa: S106 -- a throwaway credential for a store nothing reaches
            ),
            "fsspec": FsspecAdapterConfig(protocol="memory"),
            "gcs": GcsAdapterConfig(
                bucket="unreachable",
                token="anon",  # noqa: S106 -- a public marker, not a credential, for a store nothing reaches
                endpoint_url=UNREACHABLE_ENDPOINT,
            ),
            "read_only": StorageDefinition(adapter=MemoryAdapterConfig(), read_only=True),
            "prefixed": StorageDefinition(adapter=MemoryAdapterConfig(), prefix="some/prefix"),
            "public": StorageDefinition(
                adapter=MemoryAdapterConfig(),
                public_url=["https://cdn1.example/", "https://cdn2.example/"],
            ),
        },
    )
