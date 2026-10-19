"""The firewall a request passes, its listeners and its exception listener.

The :class:`Firewall` — the subscriber that runs, over the kernel lifecycle's
events, the firewall a request matched — the
:class:`AccessListener` that decides a request against a firewall's rules, the
:class:`AuthenticatorManagerListener` that runs a firewall's authenticators as
a chain step, the :class:`ChannelListener` that redirects a request onto the
scheme its matched rule demands, the :class:`ContextListener` that restores the
token a session carries into the request, the :class:`ExceptionListener` that
turns a security error into a response, the :class:`LogoutListener` that
carries a logout out through the logout event, and the
:class:`FirewallListenerInterface` every listener of a
firewall's chain implements — with :class:`AbstractListener` as the template a
concrete listener starts from — kept together in one folder.
"""

from __future__ import annotations

from .abstract_listener import AbstractListener
from .access_listener import AccessListener
from .authenticator_manager_listener import AuthenticatorManagerListener
from .channel_listener import ChannelListener
from .context_listener import ContextListener
from .exception_listener import ExceptionListener
from .firewall import Firewall
from .firewall_listener_interface import FirewallListenerInterface
from .logout_listener import LogoutListener
from .refresh_user_result import RefreshUserResult

__all__ = [
    "AbstractListener",
    "AccessListener",
    "AuthenticatorManagerListener",
    "ChannelListener",
    "ContextListener",
    "ExceptionListener",
    "Firewall",
    "FirewallListenerInterface",
    "LogoutListener",
    "RefreshUserResult",
]
