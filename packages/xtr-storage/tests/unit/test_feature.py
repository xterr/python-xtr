from __future__ import annotations

from xtr_storage.feature import Feature


def test_it_names_every_capability_a_backend_may_lack() -> None:
    assert {feature.name for feature in Feature} == {"VISIBILITY"}


def test_every_value_is_the_lower_case_name() -> None:
    assert [feature.value for feature in Feature] == [feature.name.lower() for feature in Feature]


def test_a_feature_reads_as_its_value_in_a_message() -> None:
    assert f"no {Feature.VISIBILITY} here" == "no visibility here"


def test_a_feature_compares_equal_to_its_value() -> None:
    assert Feature.VISIBILITY == "visibility"
