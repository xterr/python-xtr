<div align="center">

# xtr-security-oauth2-server

**An OAuth 2.0 authorization server and resource-server authenticator for xtr security.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

The [security family](../xtr-security) authenticates a request that already carries a credential,
and [xtr-security-jwt](../xtr-security-jwt) signs tokens for an application's own users — neither
issues a token to a *third party*. This package is that half: an authorization server an
application hosts, which registers clients, runs the OAuth 2.0 grants against them, issues access
and refresh tokens, and a firewall authenticator that accepts those tokens back on a protected
route.

> 🚧 Being built. The surface is still landing package by package; the sections this README will
> carry — Install, Quick start, Configure, Endpoints, Services, Events, Commands, Errors and
> Layout — arrive with the code they describe. *Use in an application* is here already, because
> the recipe that makes it declarative is.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what
removing it undoes.

- **Install** — `uv add xtr-security-oauth2-server`; add `[orm]` to keep clients and credentials
  in a database, `[console]` for the commands.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate*, *Configure*, *Environment*
  and *Ignore* steps below, and no other: it lists `OAuth2ServerBundle`, writes a starting
  `<app>/config/oauth2_server.py`, `OAUTH2_SERVER_PRIVATE_KEY_PATH=%kernel.project_dir%/secrets/oauth2.pem`
  and a commented-out `OAUTH2_SERVER_ENCRYPTION_KEY` in `.env`, and adds `/secrets/*.pem` and
  `/secrets/*.jwks.json` to `.gitignore`. It prints what a recipe cannot make for you: minting the
  key pair and the encryption key, naming this deployment's issuer, including the router, the
  firewall the authorization endpoint needs, the listener that answers the consent question,
  `OAuth2AuthenticatorConfig()` on the API's firewall, registering a client, and the revision a
  database store takes.
- **Activate** — `OAuth2ServerBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`, imported
  from `xtr_security_oauth2_server.bundle`. Then include the router where the application is
  served — `app.include_router(routes())`, at the root and under no prefix, because the
  description of this server lives at a fixed path under its issuer — build the kernel with
  `concurrent_scoped_access=True` and call `setup(app, kernel)`, as the security family requires.
  Put an unbound `Firewall()` on the application itself: the router shipped here carries no
  dependency of its own, so that is what establishes the resource owner on `/authorize`. Which
  requests it claims is the firewall pattern's to decide, which is what keeps `/token`, `/revoke`,
  `/introspect`, `/device-code` and the `.well-known` paths outside it — authenticating the
  *client* there is this server's own job.
- **Brings along** — the [security bundle](../xtr-security), the [clock](../xtr-clock), the
  [event dispatcher](../xtr-event-dispatcher) and the [HTTP kernel](../xtr-http-kernel) always,
  because this bundle requires them; the [logging](../xtr-logging) bundle when xtr-logging is
  installed, which is where an authorization request arriving with no resource owner is reported,
  on the `oauth2_server` channel; the [console](../xtr-console) bundle when xtr-console is
  installed, for the commands.
- **Configure** — with no configuration the bundle builds and boots, and issues nothing: a
  `<app>/config/oauth2_server.py` `@configure` function returning an `OAuth2ServerConfig` says who
  this server is (`authorization_server.issuer`), what it signs and seals with
  (`private_key`, `encryption_key`), which scopes it knows (`scopes.available`) and where its
  clients and credentials live (`persistence`). Each of those is reported, by name and with the
  file to write it in, by the first service that cannot be built without it — never by the build,
  which would take the console down with it. A firewall in front of the API lists
  `OAuth2AuthenticatorConfig()` under its `authenticators`, and a listener on
  `OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE` answers the consent question.
- **Environment** — `OAUTH2_SERVER_PRIVATE_KEY_PATH`, the file the written
  `config/oauth2_server.py` reads the signing key from with
  `env("resolve:OAUTH2_SERVER_PRIVATE_KEY_PATH")`; and `OAUTH2_SERVER_ENCRYPTION_KEY`, the
  base64url of 32 random bytes that authorization codes and refresh tokens are sealed with.
  Neither is read while the application builds, so it runs before they are set; a request then
  reports the one that is missing.
- **Ignore** — the key files the key pair is written to, when they are written under the project:
  `/secrets/*.pem` for the private key, and `/secrets/*.jwks.json` for the public set written
  beside it.
- **Remove** — `uv run xtr-recipes recipes:remove xtr-security-oauth2-server`, then undo the steps
  it printed: the router, the firewalls, the consent listener and the client registrations are the
  application's own.
- **Check** — `debug:bundles` lists `oauth2_server` as active; `debug:config oauth2_server` shows
  the resolved issuer, lifetimes, flows and store; and `GET
  /.well-known/oauth-authorization-server` answers with this server's description.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-security-oauth2-server`; run the commands below from there.

```sh
uv sync --all-packages --all-extras
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest --cov
```

## License

MIT — see [LICENSE](LICENSE).
