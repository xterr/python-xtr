"""What S/MIME signing and encrypting share without cryptography: the files, and the part made.

The certificates and keys are read from files, as their paths are given; what cryptography
writes becomes the :class:`~xtr_mime.part.SMimePart` a message carries, its body as written.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, final

from xtr_mime._engine import parse
from xtr_mime._error_text import escaped
from xtr_mime.exception import MimeRuntimeError
from xtr_mime.part import SMimePart

__all__ = ["PemFile", "read_part", "read_pem_file"]

_FILE_PREFIX: Final = "file://"
# Headers never hold an empty line, so the first one ends them; cryptography ends the lines of
# an enveloped message with a bare line feed, and those of a signed one with CRLF.
_END_OF_HEADERS: Final = re.compile(rb"\r?\n\r?\n")


@final
@dataclass(frozen=True, slots=True, repr=False)
class PemFile:
    """A file of PEM text: the path errors name, and what it holds — maybe a private key."""

    path: str
    content: bytes


def read_pem_file(path: str | os.PathLike[str]) -> PemFile:
    """Read the file at ``path``; a string may start with ``file://``.

    Raises:
        MimeRuntimeError: The file does not exist or cannot be read, or the path is not one
            the file system accepts: a null byte, or text it cannot encode, in it.
    """
    shown = os.fspath(path).removeprefix(_FILE_PREFIX)
    try:
        return PemFile(shown, Path(shown).read_bytes())
    except FileNotFoundError as error:
        raise MimeRuntimeError(f'File does not exist: "{escaped(shown)}".') from error
    except OSError as error:
        raise MimeRuntimeError(
            f'Unable to read the file "{escaped(shown)}": {error.strerror}.'
        ) from error
    except ValueError as error:
        # UnicodeEncodeError among them, whose text quotes the path unescaped.
        raise MimeRuntimeError(
            f'Unable to read the file "{escaped(shown)}": the path is not one the file system '
            "accepts."
        ) from error


def read_part(output: bytes) -> SMimePart:
    """Read what cryptography wrote — headers, a blank line, a body — into a part.

    The part keeps the media type and the Content-Type parameters written, and the body as
    written, every line ending in CRLF: only the headers are read by the engine, the body is
    what a signature covers. The other headers written — ``MIME-Version`` among them — are
    left to the message and to the caller.
    """
    head, body = _END_OF_HEADERS.split(output, maxsplit=1)
    tree = parse(head + b"\r\n\r\n")
    parameters = dict(tree.get_params([])[1:])
    return SMimePart(body, tree.get_content_maintype(), tree.get_content_subtype(), parameters)
