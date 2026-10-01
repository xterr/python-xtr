"""Applications whose security configuration fails only when the build runs.

Each is a package the kernel scans: the configuration passes its own
``__post_init__`` but names something the bundle cannot wire — an authenticator
with no factory, or several authenticators with no way to choose an entry point —
so the build raises where a per-field check could not.
"""

from __future__ import annotations
