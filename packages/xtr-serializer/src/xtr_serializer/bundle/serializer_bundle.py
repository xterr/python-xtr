"""The xtr-serializer bundle: a serializer per name, holding every normalizer and encoder tagged.

An application listing :class:`SerializerBundle` gets a :class:`~xtr_serializer.Serializer`
under ``SerializerInterface``, ``NormalizerInterface``, ``DenormalizerInterface``,
``EncoderInterface`` and ``DecoderInterface`` — unqualified for the default serializer, and
under its name for each one configured in ``named_serializers``. Each holds the pydantic
normalizer and the JSON encoder, and every service the application or another bundle tags
:data:`~xtr_serializer.bundle.NORMALIZER_TAG` or :data:`~xtr_serializer.bundle.ENCODER_TAG` for
it. A class subclassing one of the interfaces is tagged without being told.

In debug mode, with a console bundle active, ``debug:serializer`` shows how a class is read and
written.
"""

from __future__ import annotations

from typing import Final, final

from typing_extensions import override
from xtr_dependency_injection import (
    BUNDLE_PASS_PRIORITY,
    Bundle,
    ContainerBuilder,
    PassStage,
    ServiceConfigurator,
    as_bundle,
    bundle_active,
    required_bundle,
)

from xtr_serializer.encoder.decoder_interface import DecoderInterface
from xtr_serializer.encoder.encoder_interface import EncoderInterface
from xtr_serializer.encoder.json_encoder import JsonEncoder
from xtr_serializer.normalizer.denormalizer_interface import DenormalizerInterface
from xtr_serializer.normalizer.normalizer_interface import NormalizerInterface
from xtr_serializer.normalizer.pydantic_normalizer import PydanticNormalizer
from xtr_serializer.serializer import Serializer
from xtr_serializer.serializer_interface import SerializerInterface

from .serializer_config import ALL_SERIALIZERS, SerializerConfig
from .serializer_pass import ENCODER_TAG, NORMALIZER_TAG, SerializerPass

__all__ = ["SerializerBundle"]

_PYDANTIC_PRIORITY: Final = -1000
"""Last: the pydantic normalizer handles nearly any type, so a narrower one goes first."""

_INTERFACES: Final = (
    SerializerInterface,
    NormalizerInterface,
    DenormalizerInterface,
    EncoderInterface,
    DecoderInterface,
)


@final
@required_bundle("xtr_console.bundle:ConsoleBundle", ignore_on_invalid=True)
@as_bundle("serializer", config=SerializerConfig)
class SerializerBundle(Bundle[SerializerConfig]):
    """Registers the serializers, and hands each the normalizers and encoders tagged for it."""

    def __init__(self) -> None:
        """Start with the default configuration, until the kernel hands the resolved one."""
        self._config = SerializerConfig()

    @override
    def build(self, builder: ContainerBuilder) -> None:
        """Tag every normalizer and encoder class, and register the pass handing them over.

        The pass runs after every bundle's ``process`` hook, so a service a bundle tags there
        joins its serializer too.
        """
        for interface in (NormalizerInterface, DenormalizerInterface):
            _ = builder.register_for_autoconfiguration(interface).add_tag(NORMALIZER_TAG)
        for interface in (EncoderInterface, DecoderInterface):
            _ = builder.register_for_autoconfiguration(interface).add_tag(ENCODER_TAG)
        builder.add_compiler_pass(
            SerializerPass(), stage=PassStage.BEFORE_OPTIMIZATION, priority=BUNDLE_PASS_PRIORITY
        )

    @override
    def load_extension(
        self,
        config: SerializerConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the built-in normalizer and encoder, a serializer per name, and the command.

        The command joins in debug mode only, when a console bundle is active.
        """
        self._config = config
        _ = services.set(_pydantic_normalizer).add_tag(
            NORMALIZER_TAG, priority=_PYDANTIC_PRIORITY, built_in=True, serializer=ALL_SERIALIZERS
        )
        _ = services.set(_json_encoder).add_tag(
            ENCODER_TAG, priority=0, built_in=True, serializer=ALL_SERIALIZERS
        )
        contexts = {None: dict(config.default_context)}
        contexts |= {
            name: {**config.default_context, **named.default_context}
            for name, named in config.named_serializers.items()
        }
        for name, context in contexts.items():
            _ = services.set(Serializer, qualifier=name).set_argument("default_context", context)
            for interface in _INTERFACES:
                services.alias(interface, Serializer, alias_qualifier=name, target_qualifier=name)
        if builder.get_parameter("kernel.debug") and bundle_active(builder, "console"):
            services.load("xtr_serializer.command")

    @override
    async def boot(self) -> None:
        """Build every serializer, so a service tagged as what it is not fails here."""
        container = self.container
        if container is None:  # pragma: no cover — the kernel sets this before boot.
            message = "SerializerBundle.boot ran without a container"
            raise RuntimeError(message)

        for name in (None, *self._config.named_serializers):
            _ = await container.get(Serializer, name)


# The built-ins are built by factories rather than from their classes: each takes a default
# context the container has nothing to give, and the serializer holding them merges its own.


def _pydantic_normalizer() -> PydanticNormalizer:
    return PydanticNormalizer()


def _json_encoder() -> JsonEncoder:
    return JsonEncoder()
