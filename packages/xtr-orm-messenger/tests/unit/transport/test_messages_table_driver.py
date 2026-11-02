from __future__ import annotations

from sqlalchemy import MetaData
from xtr_orm import MappingDriverInterface

from xtr_orm_messenger.transport import MessagesTableDriver


def test_it_adds_the_messages_table_once() -> None:
    metadata = MetaData()
    driver = MessagesTableDriver("jobs")

    assert isinstance(driver, MappingDriverInterface)
    assert driver.load_metadata(metadata) == ("jobs",)
    assert driver.load_metadata(metadata) == ()
    assert list(metadata.tables) == ["jobs"]
