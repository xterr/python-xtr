"""The xtr-web-profiler bundle: the toolbar on every page, and the pages showing each profile.

Listed for the development environment, it turns the http kernel's profiler
on there, puts the toolbar middleware just outside the request lifecycle,
and contributes two route resources — ``web_profiler_wdt`` and
``web_profiler`` — that a routes file of the development environment
includes.
"""

from __future__ import annotations

import warnings
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Final, final, override

from jinja2 import Environment  # noqa: TC002 — read at runtime by the container
from xtr_dependency_injection import Bundle, as_bundle, required_bundle
from xtr_http_kernel import MIDDLEWARE_TAG
from xtr_http_kernel.bundle import HttpKernelBundle, HttpKernelConfig
from xtr_http_kernel.data_collector import DataCollectorTemplates
from xtr_http_kernel.profiler import Profiler  # noqa: TC002 — read at runtime by the container

from xtr_web_profiler.controller.profiler_controller import ProfilerController
from xtr_web_profiler.csp.content_security_policy_handler import ContentSecurityPolicyHandler
from xtr_web_profiler.csp.nonce_generator import NonceGenerator
from xtr_web_profiler.profiler.template_manager import TemplateManager
from xtr_web_profiler.templating.environment_factory import create_environment

from .web_debug_toolbar_middleware_factory import WebDebugToolbarMiddlewareFactory
from .web_profiler_config import WebProfilerConfig

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

__all__ = ["WEB_DEBUG_TOOLBAR_PRIORITY", "WebProfilerBundle"]

WEB_DEBUG_TOOLBAR_PRIORITY: Final = 1024
"""Where the toolbar middleware sits: outside the request lifecycle's, at its default 0.

It must stay outside — above ``HttpKernelConfig.middleware_priority`` — to
see the ``X-Debug-Token`` the lifecycle's listeners put on a response.
"""

_PRODUCTION: Final = "prod"


@final
@required_bundle(HttpKernelBundle)
@as_bundle("web_profiler", config=WebProfilerConfig)
class WebProfilerBundle(Bundle[WebProfilerConfig]):
    """Registers the toolbar middleware, the profiler's pages and their route resources."""

    @override
    def prepend_extension(self, builder: ContainerBuilder) -> None:
        """Turn the http kernel's profiler on, wherever this bundle is listed.

        An application turning it off again — with a transform of the http
        kernel's configuration — keeps the pages, which then answer 404.
        """
        builder.prepend_extension_config(HttpKernelConfig, _with_profiler)

    @override
    def load_extension(
        self,
        config: WebProfilerConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the pages, the template environment and the toolbar middleware.

        Warns when the kernel runs in production: every profile holds every
        request's headers, cookies and state, readable by whoever reaches the
        pages.
        """
        if builder.get_parameter("kernel.environment") == _PRODUCTION:
            warnings.warn(
                "The web profiler is active in the prod environment: it exposes the data of "
                "every request. List WebProfilerBundle for the dev environment only.",
                UserWarning,
                stacklevel=2,
            )
        profiling = builder.get_extension_config(HttpKernelConfig).profiler.enabled
        project_dir = Path(str(builder.get_parameter("kernel.project_dir")))
        _ = services.set(_environment(config.file_link_format))
        _ = services.set(NonceGenerator)
        _ = services.set(_csp_handler)
        if profiling:
            _ = services.set(_template_manager)
            _ = services.set(_controller(project_dir))
            if config.toolbar or config.intercept_redirects:
                _ = services.set(_middleware_factory(config)).add_tag(
                    MIDDLEWARE_TAG, priority=WEB_DEBUG_TOOLBAR_PRIORITY
                )
        else:
            _ = services.set(_unprofiled_controller(project_dir))
        services.load("xtr_web_profiler.routing")


def _with_profiler(config: HttpKernelConfig) -> HttpKernelConfig:
    return replace(config, profiler=replace(config.profiler, enabled=True))


def _environment(file_link_format: str | None) -> Callable[[], Environment]:
    def environment() -> Environment:
        return create_environment(file_link_format)

    return environment


def _csp_handler(generator: NonceGenerator) -> ContentSecurityPolicyHandler:
    return ContentSecurityPolicyHandler(generator)


def _template_manager(
    environment: Environment, templates: DataCollectorTemplates
) -> TemplateManager:
    return TemplateManager(environment, templates)


def _controller(project_dir: Path) -> Callable[[Profiler, TemplateManager], ProfilerController]:
    def controller(profiler: Profiler, manager: TemplateManager) -> ProfilerController:
        return ProfilerController(profiler, manager, project_dir)

    return controller


def _unprofiled_controller(project_dir: Path) -> Callable[[Environment], ProfilerController]:
    def controller(environment: Environment) -> ProfilerController:
        return ProfilerController(
            None, TemplateManager(environment, DataCollectorTemplates()), project_dir
        )

    return controller


def _middleware_factory(
    config: WebProfilerConfig,
) -> Callable[[TemplateManager, ContentSecurityPolicyHandler], WebDebugToolbarMiddlewareFactory]:
    def middleware_factory(
        manager: TemplateManager, csp: ContentSecurityPolicyHandler
    ) -> WebDebugToolbarMiddlewareFactory:
        return WebDebugToolbarMiddlewareFactory(config, manager, csp)

    return middleware_factory
