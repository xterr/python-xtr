"""The console command sending a test email, on xtr-console.

Needs xtr-console installed beside this package. Importing this package declares
``mailer:test`` with ``@as_command``, like any other command module; the rest of the mailer
never needs it, so it works without a console.

A container builds the command with the transport it sends through. Run without one, the
console cannot fill that parameter and reports it missing rather than build the command bare.
"""

from __future__ import annotations

from .mailer_test_command import MailerTestCommand

__all__ = ["MailerTestCommand"]
