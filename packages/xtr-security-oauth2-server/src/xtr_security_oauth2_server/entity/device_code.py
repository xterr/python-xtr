"""The device-code entity a device polls on while its owner approves it."""

from __future__ import annotations

from typing import final

from xtr_security_oauth2_server.entities.device_code_entity_interface import (
    DeviceCodeEntityInterface,
)
from xtr_security_oauth2_server.entities.traits.device_code_trait import DeviceCodeTrait
from xtr_security_oauth2_server.entities.traits.entity_trait import EntityTrait
from xtr_security_oauth2_server.entities.traits.token_entity_trait import TokenEntityTrait

__all__ = ["DeviceCode"]


@final
class DeviceCode(EntityTrait, TokenEntityTrait, DeviceCodeTrait, DeviceCodeEntityInterface):
    """A device code, its user code, and the polling state a poll reads.

    The one entity the device-code repository builds back out of storage as
    well as minting fresh, because the device flow is the one flow that reads
    a credential it already issued.

    The contract comes last of the bases, for the reason
    :class:`~xtr_security_oauth2_server.entity.access_token.AccessToken` gives.
    """
