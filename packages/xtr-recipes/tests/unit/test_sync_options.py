from __future__ import annotations

from xtr_recipes.sync_options import SyncOptions


def test_the_default_syncs_everything_and_overwrites_nothing() -> None:
    options = SyncOptions()

    assert options.only is None
    assert options.force is False


def test_it_carries_the_package_to_re_apply() -> None:
    assert SyncOptions(only="xtr-messenger").only == "xtr-messenger"


def test_it_carries_the_choice_to_overwrite() -> None:
    assert SyncOptions(force=True).force is True
