from __future__ import annotations

import pytest

from xtr_web_profiler.bundle import WebProfilerConfig
from xtr_web_profiler.exception import InvalidArgumentError


def test_the_toolbar_is_on_and_nothing_else_by_default() -> None:
    config = WebProfilerConfig()

    assert (config.toolbar, config.ajax_replace, config.intercept_redirects) == (True, False, False)
    assert config.file_link_format is None


def test_excluded_ajax_paths_must_be_a_regular_expression() -> None:
    with pytest.raises(InvalidArgumentError, match="not a regular expression"):
        _ = WebProfilerConfig(excluded_ajax_paths="(")


def test_a_file_link_format_must_name_the_file() -> None:
    with pytest.raises(InvalidArgumentError, match=r"\{file\}"):
        _ = WebProfilerConfig(file_link_format="vscode://open")
