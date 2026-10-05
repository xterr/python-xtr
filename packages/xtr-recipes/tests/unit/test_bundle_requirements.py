from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_dependency_injection import Bundle, as_bundle, required_bundle

from xtr_recipes.bundle_requirements import BundleRequirements

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from xtr_dependency_injection.bundle.bundle import AnyBundle


@final
@as_bundle("fake_clock")
class ClockBundle(Bundle):
    pass


@final
@as_bundle("fake_cache")
class CacheBundle(Bundle):
    pass


@final
@required_bundle(ClockBundle)
@as_bundle("fake_logging")
class LoggingBundle(Bundle):
    pass


@final
@required_bundle(LoggingBundle)
@as_bundle("fake_messenger")
class MessengerBundle(Bundle):
    pass


@final
@required_bundle("absent_package.bundle:AbsentBundle", ignore_on_invalid=True)
@as_bundle("fake_orm")
class OrmBundle(Bundle):
    pass


@final
@required_bundle("fake_package.bundle:StringNamedBundle")
@as_bundle("fake_http_kernel")
class HttpKernelBundle(Bundle):
    pass


@final
@required_bundle(CacheBundle, ignore_on_invalid=True)
@as_bundle("fake_rate_limiter")
class RateLimiterBundle(Bundle):
    pass


@final
class NotABundle:
    pass


# How a bundle names itself: the module its class is defined in.
_CLOCK = f"{__name__}:ClockBundle"
# How a package re-exporting it names the same class in its own recipe.
_RE_EXPORTED_CLOCK = "xtr_clock.bundle:ClockBundle"
_LOGGING = "xtr_logging.bundle:LoggingBundle"
_MESSENGER = "xtr_messenger.bundle:MessengerBundle"
_CACHE = "xtr_cache.bundle:CacheBundle"
_ORM = "xtr_orm.bundle:OrmBundle"
_HTTP_KERNEL = "xtr_http_kernel.bundle:HttpKernelBundle"
_RATE_LIMITER = "xtr_rate_limiter.bundle:RateLimiterBundle"
_STRING_NAMED = "fake_package.bundle:StringNamedBundle"


def _loader(known: Mapping[str, type[AnyBundle]]) -> Callable[[str], type[AnyBundle] | None]:
    """Resolve only the targets a test spells out, so nothing is really imported."""

    def load(target: str) -> type[AnyBundle] | None:
        return known.get(target)

    return load


def test_it_finds_a_hard_requirement() -> None:
    requirements = BundleRequirements(_loader({_LOGGING: LoggingBundle, _CLOCK: ClockBundle}))

    assert requirements.required([_LOGGING, _CLOCK]) == frozenset({_CLOCK})


def test_it_finds_a_soft_requirement() -> None:
    requirements = BundleRequirements(
        _loader({_RATE_LIMITER: RateLimiterBundle, _CACHE: CacheBundle})
    )

    assert requirements.required([_RATE_LIMITER, _CACHE]) == frozenset({_CACHE})


def test_it_finds_a_requirement_of_a_requirement() -> None:
    requirements = BundleRequirements(
        _loader(
            {
                _MESSENGER: MessengerBundle,
                _LOGGING: LoggingBundle,
                _CLOCK: ClockBundle,
            }
        )
    )

    assert requirements.required([_MESSENGER, _LOGGING, _CLOCK]) == frozenset({_LOGGING, _CLOCK})


def test_it_reaches_through_a_peer_outside_the_set() -> None:
    requirements = BundleRequirements(
        _loader({_MESSENGER: MessengerBundle, _LOGGING: LoggingBundle, _CLOCK: ClockBundle})
    )

    assert requirements.required([_MESSENGER, _CLOCK]) == frozenset({_CLOCK})


def test_it_leaves_an_unrelated_bundle_alone() -> None:
    requirements = BundleRequirements(_loader({_LOGGING: LoggingBundle, _CACHE: CacheBundle}))

    assert requirements.required([_LOGGING, _CACHE]) == frozenset()


def test_a_bundle_requiring_nothing_in_the_set_is_listed_on_its_own() -> None:
    requirements = BundleRequirements(_loader({_CLOCK: ClockBundle}))

    assert requirements.required([_CLOCK]) == frozenset()


def test_it_matches_a_requirement_declared_as_a_string() -> None:
    requirements = BundleRequirements(_loader({_HTTP_KERNEL: HttpKernelBundle}))

    assert requirements.required([_HTTP_KERNEL, _STRING_NAMED]) == frozenset({_STRING_NAMED})


def test_it_matches_a_bundle_the_set_spells_under_another_module() -> None:
    requirements = BundleRequirements(
        _loader({_LOGGING: LoggingBundle, _RE_EXPORTED_CLOCK: ClockBundle}),
    )

    assert requirements.required([_LOGGING, _RE_EXPORTED_CLOCK]) == frozenset({_RE_EXPORTED_CLOCK})


def test_a_target_that_does_not_load_requires_nothing() -> None:
    requirements = BundleRequirements(_loader({_LOGGING: LoggingBundle}))

    assert requirements.required(["absent_package.bundle:AbsentBundle", _LOGGING]) == frozenset()


def test_a_soft_requirement_that_does_not_load_finds_nothing() -> None:
    requirements = BundleRequirements(_loader({_ORM: OrmBundle}))

    assert requirements.required([_ORM]) == frozenset()


def test_it_keeps_a_target_listed_only_once() -> None:
    requirements = BundleRequirements(_loader({_LOGGING: LoggingBundle, _CLOCK: ClockBundle}))

    assert requirements.required([_LOGGING, _LOGGING, _CLOCK]) == frozenset({_CLOCK})


def test_it_finds_nothing_in_an_empty_set() -> None:
    assert BundleRequirements(_loader({})).required([]) == frozenset()


def test_loadable_is_true_for_a_target_the_loader_resolves() -> None:
    assert BundleRequirements(_loader({_CLOCK: ClockBundle})).loadable(_CLOCK)


def test_loadable_is_false_for_a_target_the_loader_cannot_resolve() -> None:
    assert not BundleRequirements(_loader({})).loadable(_CLOCK)


def test_the_default_loader_finds_a_bundle_by_its_module_path() -> None:
    assert BundleRequirements().loadable(f"{__name__}:ClockBundle")


def test_the_default_loader_rejects_a_module_that_cannot_be_imported() -> None:
    assert not BundleRequirements().loadable("absent_package.bundle:AbsentBundle")


def test_the_default_loader_rejects_a_name_that_is_not_a_bundle() -> None:
    assert not BundleRequirements().loadable(f"{__name__}:NotABundle")


def test_the_default_loader_rejects_a_target_naming_no_class() -> None:
    assert not BundleRequirements().loadable("xtr_recipes")
