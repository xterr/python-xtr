"""Turning a :class:`SecurityConfig` into the container definitions it describes.

Split out of the bundle so each concern reads on its own: the voters and their
optional tracing, the password hashers, the user providers, and — the large one —
the per-firewall wiring that gathers an authenticator manager, an access map, an
entry point and the firewall's own dispatcher into a
:class:`~xtr_security.bundle.firewall_context.FirewallContext`, and every context
into the HTTP edge's :class:`~xtr_security_http.firewall_map.FirewallMap`.

Every factory declares the services it needs as typed parameters — a bare type
for an unqualified service, ``Annotated[T, Target(name)]`` for a qualified one,
``Mapping[Hashable, T]`` for a set collected by type, and
``ServiceLocator[T]`` for the same set reached lazily by name — so none is handed
the whole container to probe. A factory built per firewall or per configured name
is a closure that captures the static parts of its firewall (its name, its access
map, the qualifiers of its authenticators) and has the container fill the rest.

This module is the wiring's front door: the concerns live in the ``_``-prefixed
modules beside it, each under the size a reviewer holds in their head, and the
bundle and the tests import them through here.
"""

from __future__ import annotations

from xtr_security.bundle._firewall_wiring import build_firewall_map
from xtr_security.bundle._hasher_wiring import (
    DUMMY_PASSWORD_HASHER_QUALIFIER,
    register_hashers,
)
from xtr_security.bundle._provider_wiring import (
    register_user_providers,
)
from xtr_security.bundle._voter_wiring import VOTER_TAG, register_voters

__all__ = [
    "DUMMY_PASSWORD_HASHER_QUALIFIER",
    "VOTER_TAG",
    "build_firewall_map",
    "register_hashers",
    "register_user_providers",
    "register_voters",
]
