"""The console commands the security bundle registers when a console is active.

``debug:firewall`` reads the firewalls an application configured; the password
hasher's ``security:hash-password`` is registered here too, so it reaches the
factory the bundle wired — the command ships with xtr-password-hasher, which has
no bundle of its own.
"""

from __future__ import annotations

from xtr_password_hasher.command.user_password_hash_command import UserPasswordHashCommand

from .debug_firewall_command import DebugFirewallCommand

__all__ = ["DebugFirewallCommand", "UserPasswordHashCommand"]
