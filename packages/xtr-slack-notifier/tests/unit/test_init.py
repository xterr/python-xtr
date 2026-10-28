from __future__ import annotations

import xtr_slack_notifier


def test_it_exports_the_transport_its_factory_its_options_and_its_sent_message() -> None:
    assert xtr_slack_notifier.__all__ == [
        "SlackOptions",
        "SlackSentMessage",
        "SlackTransport",
        "SlackTransportFactory",
        "UpdateMessageSlackOptions",
    ]
