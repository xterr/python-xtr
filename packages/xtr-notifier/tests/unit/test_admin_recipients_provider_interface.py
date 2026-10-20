from __future__ import annotations

from xtr_notifier import AdminRecipientsProviderInterface
from xtr_notifier.recipient import Recipient, RecipientInterface


class _Structural:
    @property
    def admin_recipients(self) -> tuple[RecipientInterface, ...]:
        return (Recipient("admin@example.test"),)


def test_anything_naming_admin_recipients_provides_them() -> None:
    assert isinstance(_Structural(), AdminRecipientsProviderInterface)
    assert not isinstance(object(), AdminRecipientsProviderInterface)
