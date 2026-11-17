from __future__ import annotations

import xtr_http_client.data_collector as package
from xtr_http_client.data_collector.http_client_data_collector import HttpClientDataCollector


def test_the_collector_is_exported() -> None:
    assert package.__all__ == ["HttpClientDataCollector"]
    assert package.HttpClientDataCollector is HttpClientDataCollector
