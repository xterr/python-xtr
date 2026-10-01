"""``demo:security`` — the firewall, the roles and the ``ORDER_VIEW`` voter, served in process.

Each row is a claim the README makes about security, checked as it runs: the command exits 1 if
one does not hold, so it is the executable proof of ``config/security.py``. The web application
is served the way ``demo:rate-limit`` serves it — ``httpx.ASGITransport`` inside the app's own
lifespan, which boots and shuts the kernel down around the run — and every call goes through the
real firewall, authenticator and access-control map.

The flow a reader follows:

- ``/me`` with no token is answered 401 with a ``WWW-Authenticate: Bearer`` challenge;
- a password at ``/token`` mints a signed token, and ``/me`` with it is 200 and names the user;
- ``/admin/stats`` is 403 for a signed-in non-admin and 200 for the admin, through the role
  hierarchy (``ROLE_ADMIN`` reaches ``ROLE_USER``);
- a single order is 200 to the customer who placed it and 403 to another — the ``ORDER_VIEW``
  voter's owner check, run by ``IsGranted`` over the order the endpoint reads.

The login limiter (``orders_per_email``) and the router's per-client counts are reset first, the
way ``demo:rate-limit`` resets them, so the several tokens the demo mints are never throttled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Final, cast, final

import httpx
from xtr_console import ConsoleStyle, ExitCode, as_command
from xtr_dependency_injection import Injected
from xtr_rate_limiter import RateLimiterFactoryInterface
from xtr_service_contracts import ContainerInterface

__all__ = ["security"]

_CLIENT: Final = "127.0.0.1"
_HEADERS: Final = ["Claim", "Result", "Observed"]

_OK: Final = HTTPStatus.OK
_CREATED: Final = HTTPStatus.CREATED
_UNAUTHORIZED: Final = HTTPStatus.UNAUTHORIZED
_FORBIDDEN: Final = HTTPStatus.FORBIDDEN

_OWNER: Final = "ada@example.com"
_OTHER: Final = "lin@example.com"
_ADMIN: Final = "root@example.com"
# The demo users' passwords, matching the hashes in config/security.py; this is a dev-only
# command signing in against inline example accounts, not a real secret.
_PASSWORD: Final = "s3cret"  # noqa: S105
_OTHER_PASSWORD: Final = "passw0rd"  # noqa: S105
_ADMIN_PASSWORD: Final = "r00t"  # noqa: S105
_ISBN: Final = "978-0141439518"


@final
@dataclass
class _Checks:
    """The claims checked so far, and whether each held."""

    rows: list[list[str]] = field(default_factory=list)
    failed: int = 0

    def check(self, claim: str, held: bool, observed: str = "") -> None:
        """Record ``claim``, with what was observed."""
        self.rows.append([claim, "ok" if held else "FAILED", observed])
        self.failed += 0 if held else 1


@as_command("demo:security")
async def security(io: ConsoleStyle, container: Injected[ContainerInterface]) -> int:
    """Check the firewall, the roles and the owner voter against what the README says.

    Args:
        io: Where the command writes.
        container: This kernel's container, to reset the per-client counts the demo relies on.
    """
    io.title("Security")
    checks = _Checks()
    login = await container.get(RateLimiterFactoryInterface, "orders_per_email")
    await _reset_api_counts(container)
    await _run(checks, login)
    io.table(_HEADERS, checks.rows)

    if checks.failed:
        io.error(f"{checks.failed} claim(s) did not hold.")
        return ExitCode.FAILURE
    io.success(f"All {len(checks.rows)} claims held.")
    return ExitCode.SUCCESS


async def _reset_api_counts(container: ContainerInterface) -> None:
    """Clear the router's per-client counts, so the demo's calls are never rate-limited."""
    api = await container.get(RateLimiterFactoryInterface, "api")
    for route in (
        "POST~/token",
        "GET~/me",
        "GET~/admin/stats",
        "POST~/orders",
        "GET~/orders/{number}",
    ):
        await api.create(f"{_CLIENT}~{route}").reset()


async def _reset_login(login: RateLimiterFactoryInterface) -> None:
    """Forget the login count, the way an operator clears a limit between attempts."""
    await login.create(f"{_CLIENT}~POST~/token").reset()


async def _run(checks: _Checks, login: RateLimiterFactoryInterface) -> None:
    # Imported here: importing it builds the application, which serves from its own kernel.
    from bookshop.web.app import app  # noqa: PLC0415

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, client=(_CLIENT, 51234))
        async with httpx.AsyncClient(transport=transport, base_url="http://bookshop") as client:
            await _authentication(client, login, checks)
            await _roles(client, login, checks)
            await _ownership(client, login, checks)
            await _login_throttle(client, login, checks)


async def _token(
    client: httpx.AsyncClient,
    login: RateLimiterFactoryInterface,
    identifier: str,
    password: str,
) -> str:
    """Mint a token through the real ``/token`` endpoint, after clearing the login count.

    The login throttle (``orders_per_email``, two an hour) is proven on its own in
    :func:`_login_throttle`; here it is reset before each mint so the authorization checks,
    which need a token per user, are never the ones it refuses.
    """
    await _reset_login(login)
    response = await client.post("/token", json={"identifier": identifier, "password": password})
    return cast("str", _json(response)["access_token"])


def _bearer(token: str) -> dict[str, str]:
    """The authorization header carrying ``token``."""
    return {"Authorization": f"Bearer {token}"}


async def _authentication(
    client: httpx.AsyncClient, login: RateLimiterFactoryInterface, checks: _Checks
) -> None:
    """No token is 401 with a challenge; a minted token is 200 and names the user."""
    anonymous = await client.get("/me")
    challenge = _header(anonymous, "www-authenticate") or ""
    checks.check(
        "GET /me: no token is 401 with a Bearer challenge",
        anonymous.status_code == _UNAUTHORIZED and "bearer" in challenge.lower(),
        f"{anonymous.status_code} {challenge}",
    )

    token = await _token(client, login, _OWNER, _PASSWORD)
    me = await client.get("/me", headers=_bearer(token))
    body = _json(me)
    checks.check(
        "GET /me: a minted token is 200 and names the user",
        me.status_code == _OK and body.get("identifier") == _OWNER,
        f"{me.status_code} {body.get('identifier')}",
    )

    await _reset_login(login)
    wrong = await client.post("/token", json={"identifier": _OWNER, "password": "nope"})
    checks.check("POST /token: a wrong password is 401", wrong.status_code == _UNAUTHORIZED)


async def _roles(
    client: httpx.AsyncClient, login: RateLimiterFactoryInterface, checks: _Checks
) -> None:
    """A role rule: 403 for a signed-in non-admin, 200 for the admin."""
    user_token = await _token(client, login, _OWNER, _PASSWORD)
    denied = await client.get("/admin/stats", headers=_bearer(user_token))
    checks.check(
        "GET /admin/stats: a non-admin is 403",
        denied.status_code == _FORBIDDEN,
        str(denied.status_code),
    )

    admin_token = await _token(client, login, _ADMIN, _ADMIN_PASSWORD)
    granted = await client.get("/admin/stats", headers=_bearer(admin_token))
    checks.check(
        "GET /admin/stats: the admin is 200 (ROLE_ADMIN reaches ROLE_USER)",
        granted.status_code == _OK,
        f"{granted.status_code} {_json(granted)}",
    )


async def _ownership(
    client: httpx.AsyncClient, login: RateLimiterFactoryInterface, checks: _Checks
) -> None:
    """The ORDER_VIEW voter: the owner sees the order, another customer is refused."""
    owner_token = await _token(client, login, _OWNER, _PASSWORD)
    placed = await client.post(
        "/orders",
        json={"isbn": _ISBN, "quantity": 1, "email": _OWNER},
        headers=_bearer(owner_token),
    )
    checks.check(
        "POST /orders: the owner places an order",
        placed.status_code == _CREATED,
        str(placed.status_code),
    )
    number = cast("str", _json(placed)["number"])

    owned = await client.get(f"/orders/{number}", headers=_bearer(owner_token))
    checks.check(
        "GET /orders/{number}: the owner is granted ORDER_VIEW",
        owned.status_code == _OK and _json(owned).get("email") == _OWNER,
        f"{owned.status_code} {_json(owned).get('email')}",
    )

    other_token = await _token(client, login, _OTHER, _OTHER_PASSWORD)
    refused = await client.get(f"/orders/{number}", headers=_bearer(other_token))
    checks.check(
        "GET /orders/{number}: another customer is refused 403",
        refused.status_code == _FORBIDDEN,
        str(refused.status_code),
    )


async def _login_throttle(
    client: httpx.AsyncClient, login: RateLimiterFactoryInterface, checks: _Checks
) -> None:
    """The login throttle: two attempts an hour per client, the third refused."""
    await _reset_login(login)
    body = {"identifier": _OWNER, "password": _PASSWORD}
    statuses = [(await client.post("/token", json=body)).status_code for _ in range(3)]
    checks.check(
        "POST /token: two mints an hour, the third throttled 429",
        statuses == [_OK, _OK, HTTPStatus.TOO_MANY_REQUESTS],
        " ".join(str(code) for code in statuses),
    )


def _header(response: httpx.Response, name: str) -> str | None:
    """Read one response header; ``None`` when the response has none."""
    value: str | None = response.headers.get(name)  # pyright: ignore[reportAny] -- the client types its headers loosely
    return value


def _json(response: httpx.Response) -> dict[str, object]:
    """Read a response's JSON body, which every route of the shop answers with an object."""
    return cast("dict[str, object]", response.json())
