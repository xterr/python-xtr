from __future__ import annotations

from sqlalchemy import MetaData

from xtr_orm_messenger.transport import messages_table


def test_the_table_has_the_columns_a_transport_reads_and_writes() -> None:
    table = messages_table(MetaData(), "messenger_messages")

    assert [column.name for column in table.columns] == [
        "id",
        "body",
        "headers",
        "queue_name",
        "created_at",
        "available_at",
        "delivered_at",
    ]
    assert [column.name for column in table.primary_key] == ["id"]
    assert table.c.delivered_at.nullable
    assert not table.c.available_at.nullable


def test_the_index_follows_the_query_a_worker_asks() -> None:
    table = messages_table(MetaData(), "jobs")

    (index,) = table.indexes
    assert index.name == "jobs_queue_name_idx"
    assert [column.name for column in index.columns] == [
        "queue_name",
        "available_at",
        "delivered_at",
        "id",
    ]


def test_a_table_already_defined_is_returned_rather_than_defined_again() -> None:
    metadata = MetaData()
    first = messages_table(metadata, "jobs")

    assert messages_table(metadata, "jobs") is first
