"""The addresses a user switch is asked by: paths, URLs and forms."""

from __future__ import annotations

from .impersonate_url_generator import ImpersonateUrlGenerator
from .impersonation_form import ImpersonationForm
from .switch_user_config import SwitchUserConfig
from .switch_user_config_lookup_interface import SwitchUserConfigLookupInterface

__all__ = [
    "ImpersonateUrlGenerator",
    "ImpersonationForm",
    "SwitchUserConfig",
    "SwitchUserConfigLookupInterface",
]
