"""The testing package lists its checks, and the package itself never imports it."""

from __future__ import annotations

import subprocess
import sys

import xtr_mime.testing


def test_the_testing_package_exports_every_check() -> None:
    assert set(xtr_mime.testing.__all__) == {
        "assert_email_address_contains",
        "assert_email_attachment_count",
        "assert_email_has_header",
        "assert_email_header_not_same",
        "assert_email_header_same",
        "assert_email_html_body_contains",
        "assert_email_html_body_not_contains",
        "assert_email_not_has_header",
        "assert_email_subject_contains",
        "assert_email_subject_not_contains",
        "assert_email_text_body_contains",
        "assert_email_text_body_not_contains",
    }


def test_importing_the_package_leaves_the_testing_package_out() -> None:
    completed = subprocess.run(
        [sys.executable, "-c", "import sys, xtr_mime; print('xtr_mime.testing' in sys.modules)"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.stdout == "False\n", completed.stderr
