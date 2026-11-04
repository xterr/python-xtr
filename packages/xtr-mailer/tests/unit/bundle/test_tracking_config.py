from __future__ import annotations

import pytest

from xtr_mailer.bundle import TrackingConfig


def test_with_no_configuration_each_provider_keeps_its_default() -> None:
    assert TrackingConfig().is_configured() is False


@pytest.mark.parametrize("config", [TrackingConfig(opens=False), TrackingConfig(clicks=True)])
def test_asking_for_opens_or_clicks_tracks_every_email(config: TrackingConfig) -> None:
    assert config.is_configured() is True
