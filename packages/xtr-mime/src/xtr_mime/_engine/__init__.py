"""The one place xtr-mime talks to Python's ``email`` package.

Everything that ends up on the wire — encoded words, folding, parameter encoding, transfer
encodings, boundaries laid out between parts — is the ``email`` package's work. The rest of
xtr-mime keeps its own typed model and hands it to the functions here, so no ``email`` type
leaks into a public signature and a change in the package's behaviour has one place to land.

Some of the package's habits are worked around rather than accepted:

* an international domain is punycoded before it reaches an address header, because the
  package writes a raw Unicode domain as an encoded word no server accepts (CPython
  gh-83938);
* a non-ASCII local part, which the package's address reader refuses, is written as raw
  UTF-8 (RFC 6532) — the form an SMTPUTF8 session carries — in that header only;
* message identifiers are written as ``<id>`` tokens folded between ids, never as the encoded
  words the package makes of a long unstructured value;
* a word of unstructured text too long for a line is written as it is, on a line of its own,
  never as the encoded words the package splits it into — a URL or a JSON value must reach a
  reader as written — unless it holds ``=?``, which a lenient reader decodes wherever it finds
  it: a word holding it, long or short, is written as encoded words;
* trees are built from plain parts with an explicit boundary, never with the package's
  ``add_related``/``add_alternative`` helpers (they decide the nesting themselves), and the
  ``MIME-Version`` header the package's content setter adds is taken off every part — only a
  whole message carries it, and xtr-mime writes that one itself.
* a body a signature covers is never read back and written again: the package's reader and
  writer change the bytes of a header they did not build — a fold before a long word, the
  whitespace after a colon, a bare CR — so such a body is held as bytes and written as they
  are (:func:`build_verbatim`).

Header injection is refused here, not left to the package: whether it keeps a line break out
of a header depends on its patch level (the CVE-2024-6923 fix is missing from 3.11.0-3.11.9
and 3.12.0-3.12.4). Every value is refused if it holds a control character other than TAB, a
line separator or a lone surrogate; every field is checked as the package's generator writes
it — a parsed part's included, and inside ``multipart/signed``, which it writes unfolded — to
carry a name without a colon, to continue only on lines starting with a space or a tab, to hold
none of those characters and to keep its lines within 998 octets; and an address header must
read back to the addresses it was given. A parsed part's header is written as it was read, and
an address header among them must still read as the addresses it held: some releases refold
it by decoding a name into what reads as another address. A multipart is written only with
the boundary it carries; the generator would otherwise make one up and rewrite Content-Type
from the parameters it decoded.

A header name holding a colon (``h:Sender``) exists only for a transport that reads it as a
form field: a reader ends a name at its first colon, so ``Bcc:victim@example.com,x`` would be
read as a Bcc header. :func:`header_body` renders the body of such a header; nothing that
writes a field takes its name.

A header must also read back to the text it was given, as a mail client reads RFC 2047 — not
as the package's own lenient reader does. Python 3.11 and 3.12.0 fold a long name so a client
joins two of its words, and the package decodes an encoded word found in a value; when what
the package writes does not read back, the engine writes the field itself from the package's
encoded words (``email.header.Header``), and refuses it if that does not read back either. A
failure of the package on a value it cannot handle comes out as this package's own error.

The work is split by what it writes: :mod:`._grammar` holds the checks, :mod:`._policy` the
policy and header classes, :mod:`._unstructured`, :mod:`._parameters`, :mod:`._addresses` and
:mod:`._address_list` each kind of value, :mod:`._fold` the fields, :mod:`._build` the parts
and :mod:`._render` the bytes.
"""

from __future__ import annotations

from ._addresses import encode_idn_address
from ._build import (
    build_binary,
    build_message,
    build_multipart,
    build_text,
    build_verbatim,
    prepend_fields,
    set_fields,
)
from ._fold import fold_header, header_body, header_field
from ._grammar import check_folded, check_message_id
from ._policy import EnginePart
from ._render import parse, render, to_bytes, to_string
from ._values import (
    BinaryLeaf,
    HeaderValue,
    Mailbox,
    MailboxGroup,
    MessageIds,
    Parameterized,
    Path,
    TextLeaf,
)

__all__ = [
    "BinaryLeaf",
    "EnginePart",
    "HeaderValue",
    "Mailbox",
    "MailboxGroup",
    "MessageIds",
    "Parameterized",
    "Path",
    "TextLeaf",
    "build_binary",
    "build_message",
    "build_multipart",
    "build_text",
    "build_verbatim",
    "check_folded",
    "check_message_id",
    "encode_idn_address",
    "fold_header",
    "header_body",
    "header_field",
    "parse",
    "prepend_fields",
    "render",
    "set_fields",
    "to_bytes",
    "to_string",
]
