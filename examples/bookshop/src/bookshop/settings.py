"""Typed settings from the same ``.env`` cascade — without touching ``os.environ``.

``DotenvSettings`` is a pydantic-settings ``BaseSettings`` whose source reads the layered
cascade in a *sandboxed copy* of the environment. Source priority: init arguments > real
environment variables > the dotenv cascade > secret files > field defaults.

This is the alternative to ``env()`` for code that wants one validated object rather than
placeholders — both read the same files.
"""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from pydantic_settings import SettingsConfigDict
from xtr_dependency_injection import as_service
from xtr_dotenv import DotenvSettings

from bookshop.env.tier import Tier
from bookshop.kernel import ENV_KEY, PROJECT_DIR, TEST_ENVS

__all__ = ["ShopSettings", "shop_settings"]


class ShopSettings(DotenvSettings):
    """The ``SHOP_*`` variables, validated and typed.

    The four ``_dotenv_*`` class variables describe the cascade; the rest is ordinary
    pydantic-settings (``env_prefix`` maps ``name`` to ``SHOP_NAME``).
    """

    _dotenv_path: ClassVar[str] = str(PROJECT_DIR / ".env")
    _dotenv_env_key: ClassVar[str] = ENV_KEY
    _dotenv_default_env: ClassVar[str] = "dev"
    _dotenv_test_envs: ClassVar[tuple[str, ...]] = TEST_ENVS

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="SHOP_", extra="ignore", frozen=True
    )

    name: str = "Bookshop"
    page_size: int = 20
    maintenance: bool = False
    member_discount: Decimal = Decimal(0)
    tier: Tier = Tier.FREE
    currencies: str = "EUR"


@as_service
def shop_settings() -> ShopSettings:
    """Provide the settings as a singleton; the cascade is read once, when first injected."""
    return ShopSettings()
