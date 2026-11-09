"""The steps the provider adds to a firewall's chain.

:class:`OpenIdPromptListener` decides, at the authorization endpoint, whether
the end-user has to sign in again before a client may sign them in, or must
not be shown a login page at all.
"""

from __future__ import annotations

from .open_id_prompt_listener import OpenIdPromptListener

__all__ = ["OpenIdPromptListener"]
