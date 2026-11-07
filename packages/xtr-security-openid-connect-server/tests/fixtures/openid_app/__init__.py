"""A deployment of the authorization server with the OpenID Connect provider listed beside it.

Nothing in it names the provider's flow or answer: the provider's bundle puts
them in place. Each environment it is served in changes one setting, so a test
picks the environment whose setting it is about.
"""

from __future__ import annotations
