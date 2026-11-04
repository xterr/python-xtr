"""A kernel of the mime bundle and an application bundle registering what a test needs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_dependency_injection import Bundle, Kernel, NoConfig, as_bundle

from xtr_mime.bundle import MimeBundle

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

    from xtr_mime.bundle import MimeConfig

__all__ = ["Registration", "mime_kernel"]


@dataclass(frozen=True, slots=True)
class Registration:
    """A service the application provides, under a tag when ``tag`` is given.

    A class is registered for the container to build, and any other object is provided as it
    is. ``priority`` is the definition's own, apart from any tag.
    """

    service: object
    qualifier: str | None = None
    tag: str | None = None
    attributes: Mapping[str, object] = field(default_factory=dict[str, object])
    priority: int | None = None


def mime_kernel(config: MimeConfig | None = None, *registrations: Registration) -> Kernel:
    """Return a kernel of the mime bundle configured with ``config``, and ``registrations``.

    The application is a bundle made for the call: it hands the mime bundle ``config`` in
    place of its default, and registers each object as a service.
    """

    @final
    @as_bundle("application")
    class ApplicationBundle(Bundle[NoConfig]):
        @override
        def prepend_extension(self, builder: ContainerBuilder) -> None:
            if config is not None:
                builder.prepend_extension_config("mime", lambda _default: config)

        @override
        def load_extension(
            self, config: NoConfig, services: ServiceConfigurator, builder: ContainerBuilder
        ) -> None:
            for registration in registrations:
                service, qualifier = registration.service, registration.qualifier
                definition = (
                    services.set(service, qualifier=qualifier)
                    if isinstance(service, type)
                    else services.instance(service, qualifier=qualifier)
                )
                definition.priority = registration.priority
                if registration.tag is not None:
                    _ = definition.add_tag(registration.tag, **registration.attributes)

    return Kernel(
        __name__,
        env="test",
        bundles={MimeBundle: {"all": True}, ApplicationBundle: {"all": True}},
        resources=(),
    )
