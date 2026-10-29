from __future__ import annotations

from xtr_recipes.bundle_entry import BundleEntry


def test_it_splits_the_module_from_the_target() -> None:
    entry = BundleEntry("xtr_messenger.bundle:MessengerBundle", {"all": True})

    assert entry.module == "xtr_messenger.bundle"


def test_it_reads_the_class_name_from_the_target() -> None:
    entry = BundleEntry("xtr_messenger.bundle:MessengerBundle", {"all": True})

    assert entry.class_name == "MessengerBundle"


def test_it_keeps_the_flags_it_was_given() -> None:
    entry = BundleEntry("a.b:C", {"dev": True, "prod": False})

    assert entry.flags == {"dev": True, "prod": False}


def test_it_imports_its_class_unless_told_to_list_it_by_name() -> None:
    entry = BundleEntry("a.b:C", {"all": True})

    assert not entry.by_name
