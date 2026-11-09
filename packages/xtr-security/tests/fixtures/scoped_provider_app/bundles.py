"""The bundles the scoped-provider fixture activates: security, and its loaderless login."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_dependency_injection import Bundle, as_bundle, required_bundle

from tests.fixtures.scoped_provider_app.authenticator import LoaderlessLoginFactory
from xtr_security.bundle import SecurityBundle, add_authenticator_factory

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder
    from xtr_dependency_injection.bundle.bundle import AnyBundle

__all__ = ["BUNDLES", "LoaderlessLoginBundle"]


@final
@required_bundle(SecurityBundle)
@as_bundle("loaderless_login")
class LoaderlessLoginBundle(Bundle):
    """Prepends the loaderless login's factory onto the security configuration."""

    @override
    def prepend_extension(self, builder: ContainerBuilder) -> None:
        """Register the factory through the authenticator seam."""
        builder.prepend_extension_config(
            "security", add_authenticator_factory(LoaderlessLoginFactory())
        )


BUNDLES: Mapping[type[AnyBundle], Mapping[str, bool]] = {
    SecurityBundle: {"all": True},
    LoaderlessLoginBundle: {"all": True},
}
