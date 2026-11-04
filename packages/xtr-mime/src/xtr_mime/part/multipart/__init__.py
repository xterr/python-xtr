"""The multipart kinds: mixed, alternative, related, digest, and the HTTP form upload."""

from __future__ import annotations

from .alternative_part import AlternativePart
from .digest_part import DigestPart
from .form_data_part import FormDataPart
from .mixed_part import MixedPart
from .related_part import RelatedPart

__all__ = ["AlternativePart", "DigestPart", "FormDataPart", "MixedPart", "RelatedPart"]
