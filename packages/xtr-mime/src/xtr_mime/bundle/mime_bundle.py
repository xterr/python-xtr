"""The xtr-mime bundle: the MIME types table, holding every guesser tagged, and the HTML converter.

An application listing :class:`MimeBundle` gets a :class:`~xtr_mime.MimeTypes` under
``MimeTypesInterface`` and ``MimeTypeGuesserInterface``, asking every service the application or
another bundle tags :data:`~xtr_mime.bundle.MIME_TYPE_GUESSER_TAG` before it answers from a
file's extension; a class subclassing ``MimeTypeGuesserInterface`` is tagged without being told.
It also gets a :class:`~xtr_mime.DefaultHtmlToTextConverter` under
``HtmlToTextConverterInterface``.

The table is the container's own: building it leaves
:meth:`MimeTypes.get_default() <xtr_mime.MimeTypes.get_default>`, which a part naming a file's
type reads, as it was — a container never changes what the whole process shares.

Nothing is built at boot: the table reads the standard library's type table when it is first
asked for.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import final

from typing_extensions import override
from xtr_dependency_injection import (
    BUNDLE_PASS_PRIORITY,
    Bundle,
    ContainerBuilder,
    PassStage,
    ServiceConfigurator,
    ServiceLocator,
    as_bundle,
)

from xtr_mime.exception import LogicError
from xtr_mime.html_to_text_converter.default_html_to_text_converter import (
    DefaultHtmlToTextConverter,
)
from xtr_mime.html_to_text_converter.html_to_text_converter_interface import (
    HtmlToTextConverterInterface,
)
from xtr_mime.mime_type_guesser_interface import MimeTypeGuesserInterface
from xtr_mime.mime_types import MimeTypes
from xtr_mime.mime_types_interface import MimeTypesInterface

from .add_mime_type_guesser_pass import MIME_TYPE_GUESSER_TAG, AddMimeTypeGuesserPass
from .mime_config import MimeConfig

__all__ = ["MimeBundle"]


@final
@as_bundle("mime", config=MimeConfig)
class MimeBundle(Bundle[MimeConfig]):
    """Registers the MIME types table and the HTML-to-text converter."""

    @override
    def build(self, builder: ContainerBuilder) -> None:
        """Tag every guesser class, and register the pass handing them to the table.

        The pass runs after every bundle's ``process`` hook, so a guesser a bundle tags there
        joins too.
        """
        _ = builder.register_for_autoconfiguration(MimeTypeGuesserInterface).add_tag(
            MIME_TYPE_GUESSER_TAG
        )
        builder.add_compiler_pass(
            AddMimeTypeGuesserPass(),
            stage=PassStage.BEFORE_OPTIMIZATION,
            priority=BUNDLE_PASS_PRIORITY,
        )

    @override
    def load_extension(
        self,
        config: MimeConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the table, under both its interfaces, and the converter."""
        _ = services.set(_mime_types).set_arguments(
            {
                "extra_map": {key: list(value) for key, value in config.extra_map.items()},
                "guesser_names": [],
            }
        )
        services.alias(MimeTypesInterface, MimeTypes)
        services.alias(MimeTypeGuesserInterface, MimeTypes)
        _ = services.set(DefaultHtmlToTextConverter)
        services.alias(HtmlToTextConverterInterface, DefaultHtmlToTextConverter)


async def _mime_types(
    guessers: ServiceLocator[MimeTypeGuesserInterface],
    extra_map: Mapping[str, Sequence[str]],
    guesser_names: Sequence[str],
) -> MimeTypes:
    """Build the table and register its guessers.

    Args:
        guessers: The guessers offered to the table, built only when the table is.
        extra_map: The configured extensions by MIME type.
        guesser_names: The qualifiers of the tagged guessers, asked first first — written by
            :class:`~xtr_mime.bundle.AddMimeTypeGuesserPass`.

    Raises:
        LogicError: When a service tagged as a guesser does not have a guesser's methods.
    """
    table = MimeTypes(extra_map)
    # A guesser registered later is asked earlier, so the first to ask goes in last.
    for name in reversed(guesser_names):
        guesser = await guessers.get(name)
        # A tag is a string anyone can put on any service; the type it promises is not checked.
        if not isinstance(guesser, MimeTypeGuesserInterface):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise LogicError(
                f"{type(guesser).__qualname__} is tagged {MIME_TYPE_GUESSER_TAG!r} but is not a "
                f"guesser: it needs is_guesser_supported() and guess_mime_type()"
            )
        table.register_guesser(guesser)
    return table
