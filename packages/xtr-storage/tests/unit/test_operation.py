from __future__ import annotations

from xtr_storage.operation import Operation


def test_it_names_every_operation_a_storage_performs() -> None:
    assert {operation.name for operation in Operation} == {
        "WRITE",
        "READ",
        "DELETE",
        "DELETE_DIRECTORY",
        "CREATE_DIRECTORY",
        "MOVE",
        "COPY",
        "RETRIEVE_METADATA",
        "SET_VISIBILITY",
        "LIST_CONTENTS",
        "FILE_EXISTS",
        "DIRECTORY_EXISTS",
        "EXISTENCE_CHECK",
    }


def test_every_value_is_the_lower_case_name() -> None:
    assert [operation.value for operation in Operation] == [
        operation.name.lower() for operation in Operation
    ]


def test_an_operation_reads_as_its_value_in_a_message() -> None:
    assert f"the {Operation.DELETE_DIRECTORY} failed" == "the delete_directory failed"


def test_an_operation_compares_equal_to_its_value() -> None:
    assert Operation.READ == "read"
