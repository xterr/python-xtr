from __future__ import annotations

from xtr_cli.exception import InvalidProjectNameError


def test_it_points_to_the_name_option() -> None:
    error = InvalidProjectNameError("json", "it would shadow the standard library")

    assert (error.name, error.reason) == ("json", "it would shadow the standard library")
    assert "pass --name" in str(error)
