"""A kernel of the serializer bundle and an application bundle registering what a test needs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_dependency_injection import Bundle, Kernel, NoConfig, as_bundle

from xtr_serializer.bundle import SerializerBundle

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

    from xtr_serializer.bundle import SerializerConfig

__all__ = ["Registration", "serializer_kernel"]


@dataclass(frozen=True, slots=True)
class Registration:
    """A service the application provides, under a tag when ``tag`` is given.

    A class is registered for the container to build — one instance per key — and any other
    object is provided as it is. ``priority`` is the definition's own, apart from any tag.
    ``decorates`` names the service it decorates, when it is a decorator.
    """

    service: object
    qualifier: str | None = None
    tag: str | None = None
    attributes: Mapping[str, object] = field(default_factory=dict[str, object])
    priority: int | None = None
    decorates: type | None = None


def serializer_kernel(
    config: SerializerConfig | None = None, *registrations: Registration
) -> Kernel:
    """Return a kernel of the serializer bundle configured with ``config``, and ``registrations``.

    The application is a bundle made for the call: it hands the serializer bundle ``config``
    in place of its default, and registers each object as a service.
    """

    @final
    @as_bundle("application")
    class ApplicationBundle(Bundle[NoConfig]):
        @override
        def prepend_extension(self, builder: ContainerBuilder) -> None:
            if config is not None:
                builder.prepend_extension_config("serializer", lambda _default: config)

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
                if registration.decorates is not None:
                    _ = definition.set_decorated_service(registration.decorates)

    return Kernel(
        __name__,
        env="test",
        bundles={SerializerBundle: {"all": True}, ApplicationBundle: {"all": True}},
        resources=(),
    )
