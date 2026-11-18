from __future__ import annotations

import xtr_mailer.data_collector as package
from xtr_mailer.data_collector import MailerDataCollector


def test_the_package_exports_the_collector() -> None:
    assert package.__all__ == ["MailerDataCollector"]
    assert package.MailerDataCollector is MailerDataCollector
