"""What an SMTP session said and heard, with the credentials it carried taken out."""

from __future__ import annotations

from typing import Final, final

__all__ = ["REDACTED", "SmtpTranscript"]

REDACTED: Final = "[redacted]"


@final
class SmtpTranscript:
    """The lines of one session, and the secrets no line or error may show.

    A server may echo what it was sent: a reply quoting an ``AUTH`` payload, or the
    password, would carry it into an error or a debug log. :meth:`scrub` takes out every
    secret the session knows — the password and each ``AUTH`` line sent — and, from a reply
    to an ``AUTH`` exchange, the user name too. The user name is left elsewhere: it is often
    the sender's address, which a refusal of ``MAIL FROM`` rightly names.
    """

    __slots__ = ("_identities", "_learned", "_lines", "_secrets")

    def __init__(self) -> None:
        """Start empty, knowing no secret."""
        self._lines: list[str] = []
        self._secrets: set[str] = set()
        self._identities: set[str] = set()
        self._learned: set[str] = set()

    def conceal(self, secret: str, identity: str = "") -> None:
        """Keep ``secret`` out of every line, and ``identity`` out of replies to ``AUTH``."""
        if secret:
            self._secrets.add(secret)
        if identity:
            self._identities.add(identity)

    def learn(self, secret: str) -> None:
        """Keep ``secret``, a line sent while authenticating, out of every line of the session."""
        if secret:
            self._learned.add(secret)

    def reset(self) -> None:
        """Forget the lines and what was learned, for a new session; keep what was concealed."""
        self._lines = []
        self._learned = set()

    def scrub(self, text: str, *, authenticating: bool = False) -> str:
        """Return ``text`` with every secret replaced, longest first so none is left half-shown."""
        secrets = self._secrets | self._learned
        if authenticating:
            secrets |= self._identities
        for secret in sorted(secrets, key=len, reverse=True):
            text = text.replace(secret, REDACTED)
        return text

    def record(self, shown: str | None, reply: str, *, authenticating: bool = False) -> None:
        """Add the line sent, already redacted, and the reply it got, scrubbed."""
        if shown is not None:
            self._lines.append(f"> {shown}\n")
        if reply:
            scrubbed = self.scrub(reply, authenticating=authenticating)
            self._lines.extend(f"< {line}\n" for line in scrubbed.split("\r\n"))

    def take(self) -> str:
        """Return the lines recorded since the last call, and forget them."""
        lines, self._lines = self._lines, []
        return "".join(lines)
