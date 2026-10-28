"""Answering the public route a provider pushes its logout tokens to.

The route is the application's to map — the bundle registers this handler
as a service, qualified by the firewall whose provider pushes to it, and
the application serves it at the path it configured as the back-channel
logout's route:

```python
from typing import Annotated
from fastapi import Form
from xtr_dependency_injection import Target
from xtr_http_kernel.bridge import Response

from xtr_security import OidcBackChannelLogoutHandler


@app.post("/logout/backchannel")
async def backchannel_logout(
    logout_token: Annotated[str | None, Form()] = None,
    answer: Annotated[OidcBackChannelLogoutHandler, Target("main")] = None,
) -> Response:
    return await answer(logout_token)
```

The endpoint is public and unauthenticated by design — the request comes
from the provider, carrying nothing of the browser that logged in — so the
token it presents is the whole proof, and a refusal answers with the bare
status and no detail: the reason is the verifier's to name in the log, not
the caller's to read.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_http_kernel.bridge import Response
from xtr_security_core.exception import AuthenticationError

if TYPE_CHECKING:
    from xtr_security_http.oidc import OidcBackChannelLogout

__all__ = ["OidcBackChannelLogoutHandler"]


@final
class OidcBackChannelLogoutHandler:
    """Answers a provider's pushed logout token with the status it amounts to.

    The bundle registers one per OIDC firewall whose back-channel logout is
    enabled, qualified by the firewall's name — the handler is the provider's
    to reach and the application's to map, and two providers push to two
    firewalls' routes.
    """

    __slots__ = ("_logout",)

    def __init__(self, logout: OidcBackChannelLogout) -> None:
        """Record what verifies the pushed token and writes its session end down.

        Args:
            logout: Verifies the logout token against the provider's keys
                and records the session it names as ended.
        """
        self._logout = logout

    async def __call__(self, logout_token: str | None) -> Response:
        """Answer ``logout_token`` the way the back-channel logout's caller reads it.

        A missing token is a bad request, and so is one the verification
        refuses — both answer the bare status, the refusal's reason kept to
        the log. A token that verifies and records its session end is
        acknowledged.

        Args:
            logout_token: The ``logout_token`` parameter of the posted form,
                or ``None`` when the form carried none.

        Returns:
            The response the route answers with: ``400`` for a request that
            is not one the provider signed, ``200`` for one that is.
        """
        if not logout_token:
            return Response(400)
        try:
            await self._logout.logout(logout_token)
        except AuthenticationError:
            return Response(400)
        return Response(200)
