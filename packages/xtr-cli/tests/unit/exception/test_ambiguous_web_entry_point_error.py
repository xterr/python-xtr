from __future__ import annotations

from xtr_cli.exception import AmbiguousWebEntryPointError, CliError


def test_it_lists_the_candidates_and_the_option_choosing_one() -> None:
    error = AmbiguousWebEntryPointError(("a:app", "b:app"))

    assert isinstance(error, CliError)
    assert error.candidates == ("a:app", "b:app")
    assert str(error).endswith("pass --entrypoint to choose one")
