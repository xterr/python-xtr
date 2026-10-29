from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from xtr_dependency_injection.bundle import (
    Bundle,
    BundleMetadata,
    NoConfig,
    as_bundle,
    required_bundle,
)
from xtr_dependency_injection.bundle.as_bundle import declare_bundle
from xtr_dependency_injection.bundle.bundle_resolver import resolve_bundles
from xtr_dependency_injection.exception import (
    BundleDefinitionError,
    CircularBundleDependencyError,
    DuplicateBundleError,
    MissingBundleError,
)
from xtr_dependency_injection.exception._naming import qualified_name

if TYPE_CHECKING:
    from xtr_dependency_injection.bundle.bundle_resolver import ListedBundles


@dataclass(frozen=True)
class SharedConfig:
    pass


@declare_bundle(BundleMetadata("kernel", NoConfig))
class CoreBundle(Bundle):
    pass


@as_bundle("beta")
class BetaBundle(Bundle):
    pass


@required_bundle(BetaBundle)
@as_bundle("alpha")
class AlphaBundle(Bundle):
    pass


@as_bundle("gamma")
class GammaBundle(Bundle):
    pass


@as_bundle("delta")
class DeltaBundle(Bundle):
    pass


@as_bundle("loop_a")
class LoopA(Bundle):
    pass


@as_bundle("loop_b")
class LoopB(Bundle):
    pass


# Set the loop via required_bundle after both classes exist.
_ = required_bundle(LoopB)(LoopA)
_ = required_bundle(LoopA)(LoopB)


@as_bundle("shared_one", config=SharedConfig)
class SharedOne(Bundle[SharedConfig]):
    pass


@as_bundle("shared_two", config=SharedConfig)
class SharedTwo(Bundle[SharedConfig]):
    pass


@required_bundle("no_such_module_xyz:MissingBundle", ignore_on_invalid=True)
@as_bundle("with_optional_missing")
class WithOptionalMissingBundle(Bundle):
    pass


@required_bundle("no_such_module_xyz:MissingBundle")
@as_bundle("with_required_missing")
class WithRequiredMissingBundle(Bundle):
    pass


class RaisesOnInit(Bundle):
    def __init__(self) -> None:
        raise RuntimeError("do not build me")


# Attach @as_bundle after the class body: as_bundle refuses classes needing arg-less constructor
# checks in the signature, which `RaisesOnInit` still passes — the ctor raises only at build time.
RaisesOnInit = as_bundle("raises_on_init")(RaisesOnInit)


class UndecoratedBundle(Bundle):
    """A Bundle subclass nobody declared with @as_bundle."""


# The module these tests live in, so a bundle above can be named by string.
_HERE = __name__
# A package no environment has, standing for a development dependency.
_NOT_INSTALLED = "xtr_not_installed_anywhere.bundle:DevToolsBundle"


def _resolve(
    listed: ListedBundles,
    *,
    env: str = "dev",
) -> list[str]:
    resolved = resolve_bundles(core=CoreBundle(), listed=listed, env=env)
    return [type(bundle).metadata().name for bundle in resolved.bundles]


def test_a_listed_bundle_active_via_all_is_activated() -> None:
    assert _resolve({BetaBundle: {"all": True}}) == ["kernel", "beta"]


def test_a_listed_bundle_active_only_in_specific_env_is_gated() -> None:
    assert _resolve({BetaBundle: {"dev": True}}, env="dev") == ["kernel", "beta"]
    assert _resolve({BetaBundle: {"dev": True}}, env="prod") == ["kernel"]


def test_a_listed_bundles_env_flag_overrides_the_all_default() -> None:
    assert _resolve({BetaBundle: {"all": True, "prod": False}}, env="prod") == ["kernel"]


def test_a_required_class_is_pulled_in() -> None:
    order = _resolve({AlphaBundle: {"all": True}})

    assert order == ["kernel", "beta", "alpha"]


def test_a_missing_required_string_is_refused() -> None:
    with pytest.raises(MissingBundleError) as caught:
        _ = _resolve({WithRequiredMissingBundle: {"all": True}})

    assert caught.value.name == "no_such_module_xyz:MissingBundle"
    assert caught.value.required_by == "with_required_missing"


def test_a_missing_required_with_ignore_on_invalid_is_skipped() -> None:
    resolved = resolve_bundles(
        core=CoreBundle(),
        listed={WithOptionalMissingBundle: {"all": True}},
        env="dev",
    )

    names = [type(bundle).metadata().name for bundle in resolved.bundles]
    assert names == ["kernel", "with_optional_missing"]
    skipped = [report for report in resolved.reports if report.state == "skipped"]
    assert len(skipped) == 1
    assert skipped[0].qualname == "no_such_module_xyz:MissingBundle"


def test_a_skipped_requirement_records_what_the_import_said() -> None:
    # Without the import's own words the report cannot tell a package that is
    # not installed from one whose module raises as it is imported.
    resolved = resolve_bundles(
        core=CoreBundle(),
        listed={WithOptionalMissingBundle: {"all": True}},
        env="dev",
    )

    (skipped,) = [report for report in resolved.reports if report.state == "skipped"]
    assert skipped.reason is not None
    assert "no_such_module_xyz" in skipped.reason


def test_a_required_bundle_inherits_the_requirers_activity() -> None:
    # Beta is listed but disabled in prod; alpha requires beta and is activated in prod.
    # Because the requirer (alpha) is active, beta becomes active too.
    order = _resolve(
        {AlphaBundle: {"all": True}, BetaBundle: {"prod": False, "all": True}},
        env="prod",
    )

    assert order == ["kernel", "beta", "alpha"]


def test_a_bundle_disabled_in_the_env_is_reported() -> None:
    resolved = resolve_bundles(
        core=CoreBundle(),
        listed={DeltaBundle: {"dev": True}},
        env="prod",
    )

    ((delta,),) = ([r for r in resolved.reports if r.name == "delta"],)
    assert delta.state == "env_disabled"


def test_two_active_bundles_sharing_a_config_type_are_refused() -> None:
    with pytest.raises(BundleDefinitionError, match="already belongs to bundle 'shared_one'"):
        _ = _resolve({SharedOne: {"all": True}, SharedTwo: {"all": True}})


def test_a_dependency_loop_is_refused() -> None:
    with pytest.raises(CircularBundleDependencyError) as caught:
        _ = _resolve({LoopA: {"all": True}, LoopB: {"all": True}})

    assert caught.value.cycle == ("loop_a", "loop_b", "loop_a")


def test_two_listed_bundles_with_the_same_name_are_refused() -> None:
    @as_bundle("clash")
    class ClashA(Bundle):
        pass

    # Give a different class the same name using declare_bundle's escape hatch.
    @declare_bundle(BundleMetadata("clash", NoConfig))
    class ClashB(Bundle):
        pass

    with pytest.raises(DuplicateBundleError):
        _ = _resolve({ClashA: {"all": True}, ClashB: {"all": True}})


def test_listing_the_kernel_bundle_is_refused() -> None:
    with pytest.raises(BundleDefinitionError, match="always active"):
        _ = _resolve({CoreBundle: {"all": True}})


def test_only_active_bundle_classes_are_instantiated() -> None:
    # RaisesOnInit raises in its constructor; when disabled it must not be built.
    resolved = resolve_bundles(
        core=CoreBundle(),
        listed={RaisesOnInit: {"prod": True}},
        env="dev",
    )

    assert [type(bundle).metadata().name for bundle in resolved.bundles] == ["kernel"]


def test_a_listed_bundle_raising_in_its_constructor_surfaces_that_error() -> None:
    # An error raised inside __init__ is the bundle's own, not an arity
    # failure: it must surface, not be masked as "cannot be built".
    with pytest.raises(RuntimeError, match="do not build me"):
        _ = _resolve({RaisesOnInit: {"all": True}})


def test_a_required_class_that_is_not_a_bundle_is_refused() -> None:
    class NotABundle:
        pass

    # The wrong type is the case under test.
    _ = required_bundle(NotABundle)(BetaBundle)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
    try:
        with pytest.raises(BundleDefinitionError, match="not a Bundle"):
            _ = _resolve({BetaBundle: {"all": True}})
    finally:
        # Restore beta's required tuple so other tests are unaffected.
        setattr(BetaBundle, "__xtr_required_bundles__", ())  # noqa: B010


def test_reports_include_required_names() -> None:
    resolved = resolve_bundles(
        core=CoreBundle(),
        listed={AlphaBundle: {"all": True}},
        env="dev",
    )

    ((alpha_report,),) = ([r for r in resolved.reports if r.name == "alpha"],)
    assert alpha_report.required == ("beta",)


def test_a_bundle_both_listed_and_required_is_built_once_and_reported_as_listed() -> None:
    resolved = resolve_bundles(
        core=CoreBundle(),
        listed={AlphaBundle: {"all": True}, BetaBundle: {"all": True}},
        env="dev",
    )

    betas = [bundle for bundle in resolved.bundles if isinstance(bundle, BetaBundle)]
    (report,) = [report for report in resolved.reports if report.name == "beta"]
    assert len(betas) == 1
    assert report.source == "listed"


def test_a_bundle_listed_off_in_this_env_but_required_by_an_active_one_is_active() -> None:
    order = _resolve(
        {AlphaBundle: {"all": True}, BetaBundle: {"dev": True}},
        env="prod",
    )

    assert order == ["kernel", "beta", "alpha"]


def test_a_bundle_listed_by_name_is_imported_and_activated_where_its_flags_say() -> None:
    assert _resolve({f"{_HERE}:BetaBundle": {"dev": True}}, env="dev") == ["kernel", "beta"]


def test_a_bundle_listed_by_name_brings_the_bundles_it_requires() -> None:
    assert _resolve({f"{_HERE}:AlphaBundle": {"all": True}}) == ["kernel", "beta", "alpha"]


def test_a_bundle_listed_by_name_and_active_is_reported_as_its_class() -> None:
    resolved = resolve_bundles(
        core=CoreBundle(), listed={f"{_HERE}:BetaBundle": {"all": True}}, env="dev"
    )

    (beta,) = [report for report in resolved.reports if report.name == "beta"]
    assert (beta.source, beta.state, beta.qualname) == (
        "listed",
        "active",
        qualified_name(BetaBundle),
    )


def test_a_bundle_listed_by_name_is_never_imported_where_it_is_inactive() -> None:
    # Its module raises as it is imported, so importing it would fail the resolve.
    listed: ListedBundles = {"tests.fixtures.failing_on_import:DevToolsBundle": {"dev": True}}

    assert _resolve(listed, env="prod") == ["kernel"]


def test_a_bundle_listed_by_name_where_it_is_inactive_is_reported_under_that_name() -> None:
    listed: ListedBundles = {_NOT_INSTALLED: {"dev": True}}

    resolved = resolve_bundles(core=CoreBundle(), listed=listed, env="prod")

    (report,) = [report for report in resolved.reports if report.state != "active"]
    assert (report.name, report.qualname, report.source, report.state) == (
        _NOT_INSTALLED,
        _NOT_INSTALLED,
        "listed",
        "env_disabled",
    )


def test_a_bundle_listed_by_name_that_does_not_import_where_active_is_refused() -> None:
    with pytest.raises(MissingBundleError) as caught:
        _ = _resolve({_NOT_INSTALLED: {"dev": True}}, env="dev")

    assert (caught.value.name, caught.value.required_by) == (_NOT_INSTALLED, None)


def test_the_refusal_of_a_bundle_listed_by_name_names_the_environment() -> None:
    with pytest.raises(MissingBundleError) as caught:
        _ = _resolve({_NOT_INSTALLED: {"dev": True}}, env="dev")

    assert caught.value.reason is not None
    assert "'dev'" in caught.value.reason
    assert "xtr_not_installed_anywhere" in caught.value.reason


def test_a_name_that_is_not_module_and_class_is_refused_even_where_inactive() -> None:
    with pytest.raises(BundleDefinitionError, match="'module:Class'"):
        _ = _resolve({"xtr_dev_tools": {"dev": True}}, env="prod")


def test_a_name_naming_something_other_than_a_bundle_is_refused() -> None:
    with pytest.raises(BundleDefinitionError, match="is not a Bundle subclass"):
        _ = _resolve({f"{_HERE}:SharedConfig": {"all": True}})


def test_a_name_naming_a_bundle_never_declared_is_refused() -> None:
    with pytest.raises(BundleDefinitionError, match="not decorated with @as_bundle"):
        _ = _resolve({f"{_HERE}:UndecoratedBundle": {"all": True}})


def test_a_bundle_listed_as_its_class_and_by_name_is_refused() -> None:
    with pytest.raises(DuplicateBundleError) as caught:
        _ = _resolve({BetaBundle: {"prod": True}, f"{_HERE}:BetaBundle": {"dev": True}})

    assert (caught.value.name, caught.value.first, caught.value.second) == (
        "beta",
        qualified_name(BetaBundle),
        f"{_HERE}:BetaBundle",
    )
