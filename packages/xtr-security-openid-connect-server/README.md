# xtr-security-openid-connect-server

**OpenID Connect for the xtr OAuth 2.0 authorization server.**

This package makes [xtr-security-oauth2-server](../xtr-security-oauth2-server) an OpenID Connect
provider for the authorization code flow: a client asking for the `openid` scope gets an ID token
naming the user who signed in, reads that user's claims from a userinfo endpoint, and finds both
described in a discovery document. It is being built: so far it ships its bundle, which registers
nothing yet.

## Use in an application

- **Install** — `uv add xtr-security-openid-connect-server`.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate* step below, and no other: it
  lists `OpenIdConnectServerBundle` in `<app>/config/bundles.py`.
- **Activate** — `OpenIdConnectServerBundle: {"all": True}` in `BUNDLES` in
  `<app>/config/bundles.py`, imported from `xtr_security_openid_connect_server.bundle`.
- **Brings along** — the [OAuth 2.0 authorization server](../xtr-security-oauth2-server), the
  [security bundle](../xtr-security), the [clock](../xtr-clock), the
  [event dispatcher](../xtr-event-dispatcher) and the [HTTP kernel](../xtr-http-kernel), because
  this bundle requires them.
- **Configure** — nothing yet: the bundle builds and boots with no configuration.
- **Environment** — nothing yet.
- **Ignore** — nothing yet.
- **Remove** — `uv run xtr-recipes recipes:remove xtr-security-openid-connect-server`, which takes
  the bundle out of `BUNDLES` again.
- **Check** — `debug:bundles` lists `openid_connect_server` as active, with `oauth2_server` among
  the bundles it requires.

## Kernel / bundle

```python
# app/config/bundles.py
from xtr_security_openid_connect_server.bundle import OpenIdConnectServerBundle

BUNDLES = {OpenIdConnectServerBundle: {"all": True}}
```

`OpenIdConnectServerBundle` (name `openid_connect_server`, config `OpenIdConnectServerConfig`)
requires the [OAuth 2.0 authorization server](../xtr-security-oauth2-server),
[security](../xtr-security), [clock](../xtr-clock), [event dispatcher](../xtr-event-dispatcher)
and [HTTP kernel](../xtr-http-kernel) bundles, so listing it alone brings every one of them along.
It builds and boots with no configuration.
