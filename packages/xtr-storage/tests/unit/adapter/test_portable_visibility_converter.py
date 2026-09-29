from __future__ import annotations

import pytest

from xtr_storage.adapter.portable_visibility_converter import PortableVisibilityConverter
from xtr_storage.visibility import Visibility


def test_the_default_file_modes_are_the_portable_ones() -> None:
    converter = PortableVisibilityConverter()

    assert converter.for_file(Visibility.PUBLIC) == 0o644
    assert converter.for_file(Visibility.PRIVATE) == 0o600


def test_the_default_directory_modes_carry_the_execute_bit() -> None:
    converter = PortableVisibilityConverter()

    assert converter.for_directory(Visibility.PUBLIC) == 0o755
    assert converter.for_directory(Visibility.PRIVATE) == 0o700


def test_directories_default_to_private() -> None:
    assert PortableVisibilityConverter().default_for_directories() == 0o700


def test_the_default_for_directories_follows_the_visibility_it_was_given() -> None:
    converter = PortableVisibilityConverter(default_for_directories=Visibility.PUBLIC)

    assert converter.default_for_directories() == 0o755


def test_every_mode_is_adjustable() -> None:
    converter = PortableVisibilityConverter(
        file_public=0o664,
        file_private=0o640,
        directory_public=0o775,
        directory_private=0o750,
    )

    assert converter.for_file(Visibility.PUBLIC) == 0o664
    assert converter.for_file(Visibility.PRIVATE) == 0o640
    assert converter.for_directory(Visibility.PUBLIC) == 0o775
    assert converter.for_directory(Visibility.PRIVATE) == 0o750


@pytest.mark.parametrize("visibility", list(Visibility))
def test_a_file_mode_reads_back_as_the_visibility_that_wrote_it(visibility: Visibility) -> None:
    converter = PortableVisibilityConverter()

    assert converter.inverse_for_file(converter.for_file(visibility)) is visibility


@pytest.mark.parametrize("visibility", list(Visibility))
def test_a_directory_mode_reads_back_as_the_visibility_that_wrote_it(
    visibility: Visibility,
) -> None:
    converter = PortableVisibilityConverter()

    assert converter.inverse_for_directory(converter.for_directory(visibility)) is visibility


def test_only_the_exact_private_file_mode_reads_as_private() -> None:
    converter = PortableVisibilityConverter()

    assert converter.inverse_for_file(0o600) is Visibility.PRIVATE
    assert converter.inverse_for_file(0o400) is Visibility.PUBLIC
    assert converter.inverse_for_file(0o640) is Visibility.PUBLIC
    assert converter.inverse_for_file(0o000) is Visibility.PUBLIC


def test_only_the_exact_private_directory_mode_reads_as_private() -> None:
    converter = PortableVisibilityConverter()

    assert converter.inverse_for_directory(0o700) is Visibility.PRIVATE
    assert converter.inverse_for_directory(0o750) is Visibility.PUBLIC
    assert converter.inverse_for_directory(0o500) is Visibility.PUBLIC


def test_the_private_mode_read_back_is_the_configured_one() -> None:
    converter = PortableVisibilityConverter(file_private=0o640, directory_private=0o750)

    assert converter.inverse_for_file(0o640) is Visibility.PRIVATE
    assert converter.inverse_for_file(0o600) is Visibility.PUBLIC
    assert converter.inverse_for_directory(0o750) is Visibility.PRIVATE
    assert converter.inverse_for_directory(0o700) is Visibility.PUBLIC


def test_files_and_directories_are_read_by_their_own_rule() -> None:
    converter = PortableVisibilityConverter()

    assert converter.inverse_for_file(0o700) is Visibility.PUBLIC
    assert converter.inverse_for_directory(0o600) is Visibility.PUBLIC
