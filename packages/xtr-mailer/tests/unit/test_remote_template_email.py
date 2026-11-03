"""An email whose body a mail provider renders from a template it hosts.

Upstream's two serialization cases (a round trip through ``serialize``, and an unserialize
refusing a template slot of the wrong class) are ported through the queue, which carries a
queued email as plain data: ``tests/integration/test_queued_email.py`` and
``test_queued_email_refusals.py``. A copy, which is what a sent message keeps, is checked here.
"""

from __future__ import annotations

import copy
import re

import pytest
from xtr_mime import LogicError, TextPart

from xtr_mailer import RemoteTemplateEmail


def _addressed() -> RemoteTemplateEmail:
    return RemoteTemplateEmail().from_("fabien@example.com").to("you@example.com")


def test_the_template_is_set_and_taken_away() -> None:
    email = RemoteTemplateEmail()
    assert email.get_remote_template() is None

    _ = email.template("welcome", {"firstName": "Fabien"})
    template = email.get_remote_template()
    assert template is not None
    assert template.get_reference() == "welcome"
    assert template.get_variables() == {"firstName": "Fabien"}

    _ = email.template(None)
    assert email.get_remote_template() is None


def test_an_email_with_a_template_and_no_body_is_valid() -> None:
    _addressed().template("welcome").ensure_validity()


def test_an_email_with_a_template_and_a_text_body_is_not_valid() -> None:
    email = _addressed().template("welcome").text("some text")

    with pytest.raises(
        LogicError,
        match=re.escape(
            "An email using a remote template cannot have a text or an HTML part; its body is "
            "rendered by the mail provider."
        ),
    ):
        email.ensure_validity()


def test_an_email_with_a_template_and_an_html_body_is_not_valid() -> None:
    email = _addressed().template("welcome").html("<b>some html</b>")

    with pytest.raises(LogicError, match="cannot have a text or an HTML part"):
        email.ensure_validity()


def test_an_email_without_a_template_still_needs_a_body() -> None:
    with pytest.raises(
        LogicError, match=re.escape("A message must have a text or an HTML part or attachments.")
    ):
        _addressed().ensure_validity()


def test_an_email_without_a_template_has_the_body_it_was_given() -> None:
    body = _addressed().text("some text").get_body()

    assert isinstance(body, TextPart)
    assert body.get_body() == "some text"


def test_the_body_is_a_placeholder_naming_the_template() -> None:
    body = RemoteTemplateEmail().template("welcome").get_body()

    assert isinstance(body, TextPart)
    assert body.get_body() == (
        'This email is rendered by the mail provider from its "welcome" template.'
    )


def test_a_copy_keeps_the_template() -> None:
    email = _addressed().template("welcome", {"firstName": "Fabien"})

    copied = copy.copy(email)

    template = copied.get_remote_template()
    assert template is not None
    assert template.get_reference() == "welcome"
    assert template.get_variables() == {"firstName": "Fabien"}
    assert [address.get_address() for address in copied.get_from()] == ["fabien@example.com"]


def test_an_email_with_a_template_renders() -> None:
    rendered = _addressed().template("welcome").to_string()

    assert 'from its "welcome" template.' in rendered
