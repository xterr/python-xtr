from __future__ import annotations

from xtr_storage.adapter.portable_visibility_converter import PortableVisibilityConverter
from xtr_storage.adapter.visibility_converter_interface import VisibilityConverterInterface
from xtr_storage.visibility import Visibility


class FakeConverter:
    """A converter that grants everything, as a deployment behind a web server might."""

    def for_file(self, visibility: Visibility) -> int:
        del visibility

        return 0o666

    def for_directory(self, visibility: Visibility) -> int:
        del visibility

        return 0o777

    def inverse_for_file(self, mode: int) -> Visibility:
        del mode

        return Visibility.PUBLIC

    def inverse_for_directory(self, mode: int) -> Visibility:
        del mode

        return Visibility.PUBLIC

    def default_for_directories(self) -> int:
        return 0o777


def test_a_structural_match_satisfies_the_interface() -> None:
    assert isinstance(FakeConverter(), VisibilityConverterInterface)


def test_the_shipped_converter_satisfies_the_interface() -> None:
    assert isinstance(PortableVisibilityConverter(), VisibilityConverterInterface)


def test_a_partial_implementation_does_not_satisfy_the_interface() -> None:
    class OnlyFiles:
        def for_file(self, visibility: Visibility) -> int:
            del visibility

            return 0o600

    assert not isinstance(OnlyFiles(), VisibilityConverterInterface)


def test_a_fake_answers_through_the_interface() -> None:
    converter: VisibilityConverterInterface = FakeConverter()

    assert converter.for_file(Visibility.PRIVATE) == 0o666
    assert converter.for_directory(Visibility.PRIVATE) == 0o777
    assert converter.inverse_for_file(0o600) is Visibility.PUBLIC
    assert converter.inverse_for_directory(0o700) is Visibility.PUBLIC
    assert converter.default_for_directories() == 0o777
