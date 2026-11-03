from __future__ import annotations

import shlex
import sys
from typing import TYPE_CHECKING

import pytest
from xtr_mime import Address, RawMessage

from tests.support.sendmail_fakes import FAKE_SENDMAIL, FakeSendmail
from xtr_mailer import Envelope, TransportError
from xtr_mailer.testing import FactoryCases, assert_factory_cases
from xtr_mailer.transport import (
    Dsn,
    NativeTransportFactory,
    SendmailTransport,
    Transport,
    native_transport_factory,
)

if TYPE_CHECKING:
    from pathlib import Path

_NOT_FOUND = (
    'No sendmail binary was found for the "native" transport; use a "sendmail://default" or '
    '"smtp://..." DSN.'
)


def _sendmail(directory: Path) -> Path:
    """An executable ``sendmail`` in ``directory`` that runs the stand-in."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "sendmail"
    _ = path.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} "{FAKE_SENDMAIL}" "$@"\n')
    path.chmod(0o755)
    return path


@pytest.fixture
def no_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Leave nothing on the path, and point the fallback at a file that does not exist."""
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(native_transport_factory, "FALLBACK_PATH", str(tmp_path / "missing"))


def test_it_serves_the_native_scheme_alone() -> None:
    assert_factory_cases(
        FactoryCases(
            create_factory=NativeTransportFactory,
            supports=[(Dsn("native", "default"), True), (Dsn("sendmail", "default"), False)],
            unsupported_scheme=[
                (
                    Dsn.from_string("sendmail://default"),
                    (
                        'The "sendmail" scheme is not supported; supported schemes for mailer '
                        '"native" are: "native".'
                    ),
                )
            ],
        )
    )


@pytest.mark.usefixtures("no_fallback")
def test_it_fails_when_no_sendmail_is_found() -> None:
    with pytest.raises(TransportError) as caught:
        _ = NativeTransportFactory().create(Dsn.from_string("native://default"))

    assert str(caught.value) == _NOT_FOUND


@pytest.mark.usefixtures("no_fallback")
def test_it_runs_the_sendmail_on_the_path_with_t_and_i(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sendmail = _sendmail(tmp_path / "with space")
    monkeypatch.setenv("PATH", str(sendmail.parent))

    transport = NativeTransportFactory().create(Dsn.from_string("native://default"))

    assert isinstance(transport, SendmailTransport)
    assert transport._command == shlex.join([str(sendmail), "-t", "-i"])


def test_it_falls_back_to_the_conventional_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sendmail = _sendmail(tmp_path / "sbin")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(native_transport_factory, "FALLBACK_PATH", str(sendmail))

    transport = NativeTransportFactory().create(Dsn.from_string("native://default"))

    assert transport._command == shlex.join([str(sendmail), "-t", "-i"])


@pytest.mark.usefixtures("no_fallback")
def test_a_fallback_that_cannot_be_run_is_not_used(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sendmail = _sendmail(tmp_path / "sbin")
    sendmail.chmod(0o644)
    monkeypatch.setattr(native_transport_factory, "FALLBACK_PATH", str(sendmail))

    with pytest.raises(TransportError) as caught:
        _ = NativeTransportFactory().create(Dsn.from_string("native://default"))

    assert str(caught.value) == _NOT_FOUND


@pytest.mark.anyio
@pytest.mark.usefixtures("no_fallback")
async def test_a_native_dsn_sends_through_the_host_sendmail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path)
    monkeypatch.setenv("PATH", str(_sendmail(tmp_path / "bin").parent))
    envelope = Envelope(Address("from@mail.com"), [Address("recipient@mail.com")])

    transport = Transport.from_dsn("native://default")
    _ = await transport.send(RawMessage(b"Subject: x\r\n\r\n.dot\r\n"), envelope)

    assert fake.argv[1:] == ["-i", "-ffrom@mail.com", "--", "recipient@mail.com"]
    assert fake.input == b"Subject: x\n\n.dot\n"
