"""The device-code storage contract is runtime-checkable and fully async."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from tests.support.entities import DeviceCode
from xtr_security_oauth2_server_core.repositories.device_code_repository_interface import (
    DeviceCodeRepositoryInterface,
)

if TYPE_CHECKING:
    from xtr_security_oauth2_server_core.entities.device_code_entity_interface import (
        DeviceCodeEntityInterface,
    )


@final
class _DeviceCodeRepository:
    """Keeps the codes it was handed, found again by the code itself."""

    def __init__(self) -> None:
        self.stored: dict[str, DeviceCodeEntityInterface] = {}
        self.revoked: set[str] = set()

    async def get_new_device_code(self) -> DeviceCodeEntityInterface:
        return DeviceCode()

    async def persist_device_code(
        self,
        device_code_entity: DeviceCodeEntityInterface,
    ) -> None:
        self.stored[device_code_entity.get_identifier()] = device_code_entity

    async def get_device_code_entity_by_device_code(
        self,
        device_code: str,
    ) -> DeviceCodeEntityInterface | None:
        return self.stored.get(device_code)

    async def revoke_device_code(self, code_id: str) -> None:
        self.revoked.add(code_id)

    async def is_device_code_revoked(self, code_id: str) -> bool:
        return code_id in self.revoked


@final
class _WithoutLookup:
    """A repository that stores device codes but cannot find one again."""

    async def get_new_device_code(self) -> DeviceCodeEntityInterface:
        return DeviceCode()

    async def persist_device_code(
        self,
        device_code_entity: DeviceCodeEntityInterface,
    ) -> None:
        del device_code_entity

    async def revoke_device_code(self, code_id: str) -> None:
        del code_id

    async def is_device_code_revoked(self, code_id: str) -> bool:
        del code_id
        return False


def test_a_full_repository_satisfies_the_contract() -> None:
    repository: DeviceCodeRepositoryInterface = _DeviceCodeRepository()
    assert isinstance(repository, DeviceCodeRepositoryInterface)


def test_a_repository_missing_a_method_does_not_satisfy_it() -> None:
    assert not isinstance(_WithoutLookup(), DeviceCodeRepositoryInterface)
