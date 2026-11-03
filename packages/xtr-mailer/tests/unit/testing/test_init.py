"""The testing package lists its checks, and the package itself never imports it."""

from __future__ import annotations

import subprocess
import sys

import xtr_mailer.testing


def test_the_testing_package_exports_every_check() -> None:
    assert set(xtr_mailer.testing.__all__) == {
        "PASSWORD",
        "USER",
        "FactoryCases",
        "assert_email_count",
        "assert_email_is_not_queued",
        "assert_email_is_queued",
        "assert_factory_cases",
        "assert_queued_email_count",
    }


def test_importing_the_package_leaves_the_testing_package_out() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys, xtr_mailer, xtr_mailer.transport, xtr_mailer.event; "
                "print('xtr_mailer.testing' in sys.modules)"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.stdout == "False\n", completed.stderr
