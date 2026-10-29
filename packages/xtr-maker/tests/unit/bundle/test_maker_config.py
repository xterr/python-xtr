"""Unit tests for :class:`xtr_maker.bundle.MakerConfig`."""

from __future__ import annotations

import pytest

from xtr_maker import InvalidArgumentError
from xtr_maker.bundle import MakerConfig


def test_the_defaults_write_final_classes_into_the_kernel_package() -> None:
    config = MakerConfig()

    assert config.root_package is None
    assert config.final_classes


def test_a_dotted_root_package_is_accepted() -> None:
    assert MakerConfig(root_package="acme.shop").root_package == "acme.shop"


@pytest.mark.parametrize("root_package", ["", "my-app", "acme..shop", "2app"])
def test_a_root_package_no_import_could_name_is_refused(root_package: str) -> None:
    with pytest.raises(InvalidArgumentError, match="root_package"):
        _ = MakerConfig(root_package=root_package)
