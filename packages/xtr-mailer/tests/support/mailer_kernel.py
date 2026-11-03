"""A kernel of the mailer bundle, configured and given services by an application bundle."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_dependency_injection import Bundle, Kernel, NoConfig, as_bundle

from xtr_mailer.bundle import MailerBundle, MailerConfig

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

__all__ = ["Application", "Provided", "mailer_kernel"]


@final
@dataclass(frozen=True, slots=True)
class Provided:
    """A service the application provides as it is, under ``qualifier``, tagged ``tag``."""

    service: object
    qualifier: str | None = None
    tag: str | None = None


@final
@dataclass(frozen=True, slots=True)
class Application:
    """What the application configures and provides.

    Attributes:
        mailer: The mailer configuration; ``None`` keeps the bundle's default.
        peers: The configuration of a peer bundle by its name, in place of its default.
        provided: The services the application provides.
        environ: The environment the kernel reads ``env()`` placeholders from.
        debug: Whether the kernel is built in debug mode.
    """

    mailer: MailerConfig | None = None
    peers: Mapping[str, object] = field(default_factory=dict[str, object])
    provided: Sequence[Provided] = ()
    environ: Mapping[str, str] = field(default_factory=dict[str, str])
    debug: bool = True


def mailer_kernel(application: Application | None = None) -> Kernel:
    """Return a kernel of the mailer bundle and of a bundle standing for ``application``."""
    application = application if application is not None else Application()
    replaced: dict[str, object] = dict(application.peers)
    if application.mailer is not None:
        replaced["mailer"] = application.mailer

    @final
    @as_bundle("application")
    class ApplicationBundle(Bundle[NoConfig]):
        @override
        def prepend_extension(self, builder: ContainerBuilder) -> None:
            for name, config in replaced.items():
                builder.prepend_extension_config(name, _replacing(config))

        @override
        def load_extension(
            self, config: NoConfig, services: ServiceConfigurator, builder: ContainerBuilder
        ) -> None:
            for provided in application.provided:
                definition = services.instance(provided.service, qualifier=provided.qualifier)
                if provided.tag is not None:
                    _ = definition.add_tag(provided.tag)

    return Kernel(
        __name__,
        env="test",
        bundles={MailerBundle: {"all": True}, ApplicationBundle: {"all": True}},
        resources=(),
        environ=dict(application.environ),
        debug=application.debug,
    )


def _replacing(config: object) -> Callable[[object], object]:
    """Return the transform putting ``config`` in place of whatever a bundle had."""

    def replace(_default: object) -> object:
        return config

    return replace
