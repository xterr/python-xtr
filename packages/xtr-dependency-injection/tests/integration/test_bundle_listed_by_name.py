"""An application listing a development tool's bundle by name, built where the tool is absent.

The tool's package is not written until a test installs it: a deployment does
not install a development dependency, so the application's bundle list names
the tool's bundle by string rather than importing it. Built for ``prod``, where
the list leaves it disabled, the kernel boots without the package; built for
``dev``, where the list activates it, the kernel says the package is missing —
until it is installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_dependency_injection import Kernel, KernelInterface
from xtr_dependency_injection.exception import MissingBundleError

if TYPE_CHECKING:
    from tests.support.modules import ScratchModules

pytestmark = pytest.mark.anyio

DEV_TOOLS = "acme_dev_tools.bundle:DevToolsBundle"

MAIL = """
from xtr_dependency_injection import Bundle, as_bundle


@as_bundle("mail")
class MailBundle(Bundle):
    pass
"""

TOOLS = """
from xtr_dependency_injection import Bundle, as_bundle


@as_bundle("dev_tools")
class DevToolsBundle(Bundle):
    pass
"""

APP_BUNDLES = f"""
from acme_mail.bundle import MailBundle

BUNDLES = {{
    MailBundle: {{"all": True}},
    "{DEV_TOOLS}": {{"dev": True}},
}}
"""


@pytest.fixture
def application(scratch_modules: ScratchModules) -> ScratchModules:
    scratch_modules.write({"acme_mail.bundle": MAIL, "acme_shop.config.bundles": APP_BUNDLES})
    return scratch_modules


@pytest.mark.usefixtures("application")
async def test_it_boots_in_prod_without_the_package_of_the_bundle_listed_by_name() -> None:
    async with await Kernel("acme_shop", env="prod", environ={}).boot() as booted:
        info = await booted.container.get(KernelInterface)

    assert info.bundles == ("kernel", "mail")


@pytest.mark.usefixtures("application")
def test_it_reports_the_bundle_listed_by_name_as_disabled_in_prod() -> None:
    compiled = Kernel("acme_shop", env="prod", environ={}).build()

    (tools,) = [report for report in compiled.report.bundles if report.qualname == DEV_TOOLS]
    assert (tools.source, tools.state) == ("listed", "env_disabled")


@pytest.mark.usefixtures("application")
def test_in_dev_it_names_the_bundle_whose_package_is_missing() -> None:
    with pytest.raises(MissingBundleError) as caught:
        _ = Kernel("acme_shop", env="dev", environ={}).build()

    assert caught.value.name == DEV_TOOLS


async def test_in_dev_it_activates_the_bundle_listed_by_name_once_installed(
    application: ScratchModules,
) -> None:
    application.write({"acme_dev_tools.bundle": TOOLS})

    async with await Kernel("acme_shop", env="dev", environ={}).boot() as booted:
        info = await booted.container.get(KernelInterface)

    assert info.bundles == ("kernel", "dev_tools", "mail")
