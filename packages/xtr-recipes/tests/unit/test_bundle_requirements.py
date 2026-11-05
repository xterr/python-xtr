from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_dependency_injection import Bundle, as_bundle

from xtr_recipes.bundle_requirements import BundleRequirements

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from xtr_dependency_injection.bundle.bundle import AnyBundle


@final
@as_bundle("fake_clock")
class ClockBundle(Bundle):
    pass


@final
class NotABundle:
    pass


# How a bundle names itself: the module its class is defined in.
_CLOCK = f"{__name__}:ClockBundle"
# A distribution whose own name is dotted ships a dotted namespace package.
_DOTTED = "zope.interface.bundle:ZopeBundle"
# The distribution this test module's own targets belong to: its import
# package is the first segment of ``__name__``.
_OWN = __name__.split(".")[0]


def _loader(known: Mapping[str, type[AnyBundle]]) -> Callable[[str], type[AnyBundle] | None]:
    """Resolve only the targets a test spells out, so nothing is really imported."""

    def load(target: str) -> type[AnyBundle] | None:
        return known.get(target)

    return load


def test_loadable_is_true_for_a_target_the_loader_resolves() -> None:
    assert BundleRequirements(_loader({_CLOCK: ClockBundle})).loadable(_CLOCK, _OWN)


def test_loadable_is_false_for_a_target_the_loader_cannot_resolve() -> None:
    assert not BundleRequirements(_loader({})).loadable(_CLOCK, _OWN)


def test_loadable_refuses_a_target_outside_the_declaring_distribution() -> None:
    requirements = BundleRequirements(_loader({_CLOCK: ClockBundle}))

    assert not requirements.loadable(_CLOCK, "xtr-messenger")


def test_loadable_refuses_a_target_naming_an_arbitrary_module() -> None:
    assert not BundleRequirements().loadable("os:getcwd", "xtr-messenger")


def test_loadable_accepts_a_target_under_a_dotted_distribution_name() -> None:
    requirements = BundleRequirements(_loader({_DOTTED: ClockBundle}))

    assert requirements.loadable(_DOTTED, "zope-interface")


def test_loadable_refuses_a_target_outside_a_dotted_distributions_package() -> None:
    requirements = BundleRequirements(_loader({_DOTTED: ClockBundle}))

    assert not requirements.loadable(_DOTTED, "zope-sqlalchemy")


def test_loadable_accepts_a_target_however_the_distribution_is_spelled() -> None:
    requirements = BundleRequirements(_loader({_CLOCK: ClockBundle}))

    assert requirements.loadable(_CLOCK, _OWN.replace("_", "-").upper())


def test_the_default_loader_finds_a_bundle_by_its_module_path() -> None:
    assert BundleRequirements().loadable(f"{__name__}:ClockBundle", _OWN)


def test_the_default_loader_rejects_a_module_that_cannot_be_imported() -> None:
    assert not BundleRequirements().loadable("absent_package.bundle:AbsentBundle", "absent-package")


def test_the_default_loader_rejects_a_name_that_is_not_a_bundle() -> None:
    assert not BundleRequirements().loadable(f"{__name__}:NotABundle", _OWN)


def test_the_default_loader_rejects_a_target_naming_no_class() -> None:
    assert not BundleRequirements().loadable("xtr_recipes", "xtr-recipes")
