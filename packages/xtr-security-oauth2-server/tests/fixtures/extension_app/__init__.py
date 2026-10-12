"""A deployment whose authorization code flow is an add-on's, not this package's.

Everything an add-on built on this server does, driven for real: it prepends
the settings that put its own answer and its own flow in place of the shipped
ones, registers the grant tagged with a lifetime of its own, contributes a
field to the description this server publishes, and serves a route of its own
behind the authenticator this package ships. Nothing in the package knows this
exists.
"""

from __future__ import annotations
