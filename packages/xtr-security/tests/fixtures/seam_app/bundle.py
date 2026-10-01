"""The fake third-party bundle that registers its factories through the seams."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_dependency_injection import Bundle, as_bundle, required_bundle

from tests.fixtures.seam_app.factories import FakeOAuth2Factory, FakeTokenHandlerFactory
from xtr_security.bundle import add_authenticator_factory, add_token_handler_factory
from xtr_security.bundle.security_bundle import SecurityBundle

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder

__all__ = ["FakeOAuth2Bundle"]


@final
@required_bundle(SecurityBundle)
@as_bundle("fake_oauth2")
class FakeOAuth2Bundle(Bundle):
    """Prepends the fake authenticator and token-handler factories onto security."""

    @override
    def prepend_extension(self, builder: ContainerBuilder) -> None:
        """Register the fake factories through the security config seams."""
        builder.prepend_extension_config("security", add_authenticator_factory(FakeOAuth2Factory()))
        builder.prepend_extension_config(
            "security", add_token_handler_factory(FakeTokenHandlerFactory())
        )
