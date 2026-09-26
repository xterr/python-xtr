"""Logging: every handler type, every processor type, every formatter type, and capture.

dev/test use :func:`logging_config`; prod uses :func:`logging_config_prod` — a conditional
base wins over an unconditional one. A ``stdlib`` handler and ``capture`` exclude each other
(``CaptureConflictError``), so dev/test show capture and prod shows the stdlib handler.

The ``search`` and ``messenger`` channels are not listed here: the fulltext and messenger
bundles prepend them to this config (``debug:config logging`` shows the steps).
"""

from __future__ import annotations

from xtr_dependency_injection import configure, env, when
from xtr_logging.bundle import LoggingConfig
from xtr_logging.config import (
    BufferHandlerSpec,
    CapturedLoggerSpec,
    CaptureSpec,
    ConsoleFormatterSpec,
    ConsoleHandlerSpec,
    ContextVarsProcessorSpec,
    DeduplicationHandlerSpec,
    FallbackGroupHandlerSpec,
    FilterHandlerSpec,
    FingersCrossedHandlerSpec,
    GroupHandlerSpec,
    HostnameProcessorSpec,
    IntrospectionProcessorSpec,
    JsonFormatterSpec,
    LineFormatterSpec,
    NullHandlerSpec,
    PlaceholderProcessorSpec,
    ProcessIdProcessorSpec,
    QueueHandlerSpec,
    RotatingFileHandlerSpec,
    SamplingHandlerSpec,
    ServiceHandlerSpec,
    ServiceProcessorSpec,
    StdlibHandlerSpec,
    StreamHandlerSpec,
    SyslogHandlerSpec,
    TagProcessorSpec,
    UidProcessorSpec,
    WhatFailureGroupHandlerSpec,
)

__all__ = ["logging_config", "logging_config_prod"]

_CHANNELS = ("catalog", "orders", "security", "http")
_LOG = "%shop.log_dir%"


@configure
def logging_config() -> LoggingConfig:
    """The development configuration: something of everything.

    Paths reference parameters (``%shop.log_dir%``, ``%kernel.environment%``), resolved as
    the config is; the app file's level comes from ``env()``, read when the logger factory
    is built — ``default=`` is also what validation sees while the kernel builds.
    """
    return LoggingConfig(
        default_channel="app",
        channels=_CHANNELS,
        handlers={
            # ---- on every channel's stack, highest priority first ----------------------
            "console": ConsoleHandlerSpec(
                channels=("!http",),
                priority=100,
                stream="stderr",
                verbosity_levels={
                    "quiet": "error",
                    "normal": "warning",
                    "verbose": "notice",
                    "very_verbose": "info",
                    "debug": "debug",
                },
            ),
            "memory": ServiceHandlerSpec(id="memory", priority=90),
            "main": FingersCrossedHandlerSpec(
                handler="app_file",
                action_level="error",
                channel_levels={"orders": "warning"},
                buffer_size=500,
                stop_buffering=True,
                passthru_level="notice",
            ),
            "access": RotatingFileHandlerSpec(
                channels="http",
                path=f"{_LOG}/http.log",
                level="info",
                max_files=7,
                date_format="%%Y-%%m-%%d",
                filename_format="{filename}-{date}",
                formatter=JsonFormatterSpec(batch_mode="newlines", append_newline=True),
                bubble=False,
            ),
            # Consulted before "access" (higher priority): "access" does not bubble, so a
            # record it handles goes no further down the stack.
            "access_stdout": StreamHandlerSpec(
                channels=("http",),
                priority=10,
                path="stdout",
                level="info",
                formatter=ConsoleFormatterSpec(colors=False),
            ),
            "security": FingersCrossedHandlerSpec(
                channels=("security",),
                handler="audit_buffer",
                activation_strategy="security",
            ),
            "errors": FilterHandlerSpec(
                handler="errors_dedup", min_level="error", max_level="emergency"
            ),
            "notices": FilterHandlerSpec(
                handler="errors_file", accepted_levels=("notice", "alert")
            ),
            "catalog_debug": SamplingHandlerSpec(
                channels="catalog", handler="catalog_queue", factor=2
            ),
            "orders_fanout": GroupHandlerSpec(channels=("orders",), members=("blackhole",)),
            "syslog_guard": WhatFailureGroupHandlerSpec(
                channels=("security",), members=("syslog",)
            ),
            "fallback": FallbackGroupHandlerSpec(
                channels=("app",), members=("fallback_file", "blackhole")
            ),
            # ---- nested: named by a wrapper, so kept off every stack -------------------
            "app_file": StreamHandlerSpec(
                path=f"{_LOG}/%kernel.environment%.log",
                level=env("SHOP_LOG_LEVEL", default="debug"),
                file_permission=0o640,
                formatter=LineFormatterSpec(
                    # Percent signs are escaped: every string in a bundle config is resolved for
                    # %parameter% references, so a literal % is written %%.
                    format=(
                        "[%%datetime%%] %%channel%%.%%level_name%%: "
                        "%%message%% %%context%% %%extra%%\n"
                    ),
                    date_format="%%Y-%%m-%%dT%%H:%%M:%%S%%z",
                    allow_inline_line_breaks=False,
                    ignore_empty_context_and_extra=True,
                    include_stacktraces=True,
                ),
            ),
            "audit_buffer": BufferHandlerSpec(
                handler="audit_file", buffer_size=100, flush_on_overflow=True
            ),
            "audit_file": StreamHandlerSpec(path=f"{_LOG}/audit.jsonl", formatter="audit_json"),
            "errors_dedup": DeduplicationHandlerSpec(
                handler="errors_file",
                deduplication_level="error",
                time=60,
                store=f"{_LOG}/dedup.store",
            ),
            "errors_file": StreamHandlerSpec(path=f"{_LOG}/errors.log", nested=True),
            "catalog_queue": QueueHandlerSpec(handler="catalog_file", max_size=1000),
            "catalog_file": StreamHandlerSpec(path=f"{_LOG}/catalog.log"),
            "blackhole": NullHandlerSpec(level="debug"),
            "syslog": SyslogHandlerSpec(
                ident="bookshop", facility="local0", address="localhost:514", level="warning"
            ),
            "fallback_file": StreamHandlerSpec(path=f"{_LOG}/fallback.log", level="critical"),
        },
        processors=(
            PlaceholderProcessorSpec(date_format="%%Y-%%m-%%d", remove_used_context_fields=False),
            ContextVarsProcessorSpec(key="ctx"),
            UidProcessorSpec(length=8),
            ServiceProcessorSpec(id="request"),
            IntrospectionProcessorSpec(
                channel="orders", level="warning", skip_module_prefixes=("xtr_",), skip_frames=0
            ),
            HostnameProcessorSpec(handler="app_file"),
            ProcessIdProcessorSpec(handler="app_file"),
            TagProcessorSpec(channel="security", tags=("audit", "bookshop")),
        ),
        # Take over the standard library's logging: third-party records arrive on channels.
        capture=CaptureSpec(
            level="warning",
            channel="app",
            loggers={
                "asyncio": "error",
                "aio_pika": CapturedLoggerSpec(level="info", channel="app"),
                "taskiq": "warning",
            },
        ),
    )


@configure
@when("prod")
def logging_config_prod() -> LoggingConfig:
    """Production: JSON on standard error once something failed.

    The security channel is also forwarded to a standard-library logger that a log shipper
    already reads.
    """
    return LoggingConfig(
        channels=_CHANNELS,
        handlers={
            "console": ConsoleHandlerSpec(channels=("!http",)),
            "main": FingersCrossedHandlerSpec(
                handler="json", action_level="error", buffer_size=1000, passthru_level="warning"
            ),
            "json": StreamHandlerSpec(path="stderr", formatter=JsonFormatterSpec()),
            "security_stdlib": StdlibHandlerSpec(
                channels=("security",), logger="bookshop.security", level="notice"
            ),
            "memory": ServiceHandlerSpec(id="memory"),
        },
        processors=(
            PlaceholderProcessorSpec(),
            UidProcessorSpec(),
            ServiceProcessorSpec(id="request"),
        ),
    )
