"""Emails people send every day, in every script, which the queue must carry and send.

Each is ordinary on its own — a mailing to a few hundred people named in Cyrillic, minutes
with fifty accented attachments, a thousand Bcc recipients named in Arabic — and the last holds
most of them at once. None comes near what a forged message would hold.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from xtr_mime import Address, Email

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["ORDINARY"]

# Names as people write them, about thirty octets each.
_NAMES: Final = {
    "Cyrillic": "Александр Иванов",
    "Greek": "Γιώργος Παπαδόπουλος",
    "CJK": "张伟明 (王小红)",
    "Arabic": "محمد عبد الله",
}
_SUBJECT: Final = ("Повестка дня собрания совета директоров, пункт " * 12)[:500]


def _email() -> Email:
    return Email().from_(Address("a@example.com", "Équipe Réunions")).to("b@example.com").text("t")


def _attachments(count: int) -> Email:
    email = _email()
    for index in range(count):
        _ = email.attach(b"%PDF-1.4", f"Procès-verbal réunion {index:02}.pdf")
    return email


def _named(script: str, count: int) -> list[Address]:
    return [Address(f"u{index}@example.com", _NAMES[script]) for index in range(count)]


def _bcc(script: str, count: int) -> Callable[[], Email]:
    return lambda: _email().bcc(*_named(script, count))


def _emoji_cc() -> list[Address]:
    return [
        Address(f"c{index}@example.org", f"Maria \U0001f338 García {index}") for index in range(50)
    ]


def _lists(email: Email) -> Email:
    url = "https://lists.example.com/unsubscribe/" + "a1b2c3d4" * 40
    headers = email.get_headers()
    _ = headers.add_text_header(
        "List-Unsubscribe", f"<{url}>, <mailto:leave@example.com?subject={url[-200:]}>"
    )
    _ = headers.add_text_header("List-Unsubscribe-Post", "List-Unsubscribe=One-Click")
    _ = headers.add_text_header("List-Id", "Board meetings <board.lists.example.com>")
    _ = headers.add_text_header("List-Archive", f"<https://lists.example.com/archive/{'x' * 300}>")
    return email


def _references(email: Email) -> Email:
    ids = [f"CA{index:018d}abcdefghijklmnop@mail.example.com" for index in range(200)]
    _ = email.get_headers().add_id_header("References", ids)
    return email


def _all_at_once() -> Email:
    email = _references(_lists(_attachments(50))).subject(_SUBJECT)
    _ = email.to(*_named("Cyrillic", 300)).cc(*_emoji_cc())
    return email.bcc(*[Address(f"b{index}@example.net", _NAMES["Arabic"]) for index in range(1000)])


ORDINARY: Final[dict[str, Callable[[], Email]]] = {
    "50 accented attachments": lambda: _attachments(50),
    "100 accented attachments": lambda: _attachments(100),
    **{
        f"{count} Bcc named in {script}": _bcc(script, count)
        for script in _NAMES
        for count in (200, 1000)
    },
    "To 300 named in Cyrillic": lambda: _email().to(*_named("Cyrillic", 300)),
    "50 Cc with emoji in names": lambda: _email().cc(*_emoji_cc()),
    "500-character subject": lambda: _email().subject(_SUBJECT),
    "long List headers": lambda: _lists(_email()),
    "200 References": lambda: _references(_email()),
    "all at once": _all_at_once,
}
"""Each ordinary email, by what it holds."""
