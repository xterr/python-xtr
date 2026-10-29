"""Names a file's MIME type from its content, through libmagic."""

from __future__ import annotations

from importlib import import_module
from typing import final

from typing_extensions import override

from ._readable_file import ensure_readable_file
from .exception import LogicError, MimeRuntimeError
from .mime_type_guesser_interface import MimeTypeGuesserInterface

__all__ = ["MagicMimeTypeGuesser"]


@final
class MagicMimeTypeGuesser(MimeTypeGuesserInterface):
    """Reads a file's first bytes and names its type, as the ``file`` command does.

    A file's name says what someone called it; its bytes say what it is, which is what matters
    for, say, an upload claiming to be an image. libmagic keeps the signatures that tell.

    Needs the ``magic`` extra (``xtr-mime[magic]``, which brings python-magic) and libmagic
    itself, which no wheel ships: ``brew install libmagic``, ``apt install libmagic1``. Without
    either, :meth:`is_guesser_supported` answers ``False`` and :class:`~xtr_mime.MimeTypes`
    asks its other guessers. Nothing is loaded before that first question, so building one
    costs nothing and importing this package never needs the extra.
    """

    __slots__ = ("_supported",)

    _supported: bool | None

    def __init__(self) -> None:
        """Build a guesser that loads libmagic the first time it is asked whether it can run."""
        self._supported = None

    @override
    def is_guesser_supported(self) -> bool:
        """Tell whether python-magic and libmagic load, trying once per guesser.

        A failed load is not retried: on some hosts finding libmagic runs a program, and
        :class:`~xtr_mime.MimeTypes` asks before every guess.
        """
        if self._supported is None:
            self._supported = _magic_loads()
        return self._supported

    @override
    def guess_mime_type(self, path: str) -> str | None:
        """Name the type libmagic reads in the file at ``path``.

        Returns:
            The MIME type, or ``None`` when libmagic answers nothing.

        Raises:
            InvalidArgumentError: When ``path`` does not name a file this process may read.
            LogicError: When python-magic or libmagic does not load.
            MimeRuntimeError: When libmagic fails, its database missing or unreadable; libmagic's
                own error is its cause.
        """
        ensure_readable_file(path)
        if not self.is_guesser_supported():
            raise LogicError(f'The "{type(self).__name__}" guesser is not supported.')

        import magic  # noqa: PLC0415 — the magic extra is optional; is_guesser_supported() loaded it.

        try:
            # python-magic's stub leaves the path parameter's PathLike unparameterised.
            mime_type = magic.from_file(path, mime=True)  # pyright: ignore[reportUnknownMemberType]
        except magic.MagicException as error:
            # libmagic's message comes as bytes, so it travels as the cause, not in this text.
            raise MimeRuntimeError(
                f'libmagic could not guess the MIME type of the "{path}" file.'
            ) from error

        # Some libmagic releases name an Office document's type twice in a row, unseparated.
        half = mime_type[: len(mime_type) // 2]
        if half * 2 == mime_type:
            mime_type = half

        return mime_type or None


def _magic_loads() -> bool:
    """Tell whether ``magic`` imports: python-magic installed, and libmagic found and opened."""
    try:
        _ = import_module("magic")
    except (ImportError, OSError):
        return False
    return True
