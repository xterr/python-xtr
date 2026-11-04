"""The xtr-dependency-injection bundle for xtr-mime."""

from __future__ import annotations

from .add_mime_type_guesser_pass import MIME_TYPE_GUESSER_TAG, AddMimeTypeGuesserPass
from .mime_bundle import MimeBundle
from .mime_config import MimeConfig

__all__ = [
    "MIME_TYPE_GUESSER_TAG",
    "AddMimeTypeGuesserPass",
    "MimeBundle",
    "MimeConfig",
]
