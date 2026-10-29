"""The xtr-maker bundle: the generator the ``make:*`` commands share, and the commands.

Each maker writes code for one library, so its command is registered only when
that library's bundle is active: an application never sees a maker for a
library it does not use. Those bundles are not required from here: making code
for a library is no reason to switch its bundle on, so the maker only reads
which bundles the application activated.

Nothing touches the disk until a maker runs: the application package is
looked for the first time a maker needs it.
"""

from __future__ import annotations

from typing import Final, final

from typing_extensions import override
from xtr_console.bundle import ConsoleBundle
from xtr_dependency_injection import (
    Bundle,
    ContainerBuilder,
    # Imported at runtime: the container reads the factory annotations below.
    KernelInterface,
    ServiceConfigurator,
    as_bundle,
    bundle_active,
    required_bundle,
)

from xtr_maker.file_manager import FileManager
from xtr_maker.generator import Generator
from xtr_maker.template_renderer import TemplateRenderer

from .maker_config import MakerConfig

__all__ = ["MakerBundle"]

_MAKERS: Final[tuple[tuple[str, str | None], ...]] = (
    ("xtr_maker.command.make_message_command", "messenger"),
    ("xtr_maker.command.make_schedule_command", "scheduler"),
    ("xtr_maker.command.make_webhook_command", "webhook"),
    ("xtr_maker.command.make_entity_command", "orm"),
    ("xtr_maker.command.make_command_command", None),
    ("xtr_maker.command.make_listener_command", "event_dispatcher"),
)
"""Each maker's command module, and the bundle that must be active for it (``None``: none)."""


@final
@required_bundle(ConsoleBundle)
@as_bundle("maker", config=MakerConfig)
class MakerBundle(Bundle[MakerConfig]):
    """Registers the generator, and the makers whose library's bundle is active."""

    @override
    def load_extension(
        self,
        config: MakerConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the generator's services, then the command module of each maker in reach.

        The generator is scoped: a maker run is one unit of work, which queues
        its own files, and a run that fails leaves nothing queued for the next.
        """
        del config
        _ = services.set(_template_renderer)
        _ = services.set(_file_manager)
        _ = services.set(_generator, lifetime="scoped")
        if bundle_active(builder, "webhook"):
            _set_routed_webhook_types(builder)
        for module, peer in _MAKERS:
            if peer is None or bundle_active(builder, peer):
                services.load(module)


def _set_routed_webhook_types(builder: ContainerBuilder) -> None:
    """Give ``make:webhook`` the types the webhook configuration routes, read as it is built.

    Read here rather than injected: the configuration a service is given has
    every secret resolved, so an application whose secrets are not set yet
    could not make its next webhook.
    """
    # Imported only now: xtr-webhook is optional, and only an active webhook bundle
    # gets the maker's module loaded.
    from xtr_webhook.bundle import WebhookConfig  # noqa: PLC0415 — optional, see above.

    from xtr_maker.command.make_webhook_command import (  # noqa: PLC0415 — see above.
        ROUTED_TYPES_PARAMETER,
    )

    config = builder.get_extension_config(WebhookConfig)
    builder.set_parameter(ROUTED_TYPES_PARAMETER, sorted(config.routing))


def _template_renderer() -> TemplateRenderer:
    """Render the templates this package ships."""
    return TemplateRenderer()


def _file_manager(kernel: KernelInterface, config: MakerConfig) -> FileManager:
    """Write into the configured package, else the one the kernel is named after."""
    return FileManager(kernel.project_dir, config.root_package or kernel.name)


def _generator(
    file_manager: FileManager, template_renderer: TemplateRenderer, config: MakerConfig
) -> Generator:
    """Build a generator with an empty queue, marking classes ``@final`` as configured."""
    return Generator(file_manager, template_renderer, final_classes=config.final_classes)
