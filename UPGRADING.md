# Upgrading

## To 7.0

7.0 makes every unit of work — a request, a message, a command — keep its own state when several
run at once, closes the races that let a burst of requests slip past a check, and turns on safer
defaults. Every package moves to 7.0 together. Below, each package lists what can change for an
application or a library built on it, and how to keep the old behaviour where that is still
possible. A package not listed changes nothing you can observe.

No package ships a database migration for 7.0: no table gains or loses a column.

### Every package

- Python 3.14.4 or later is required (`requires-python = ">=3.14.4"`). Python 3.14.0 to 3.14.3
  are left out: their email header folding never returns for some subjects — words mixed with
  long runs of spaces — which would hang xtr-mime and everything that sends mail through it.
- `typing-extensions` is no longer a dependency of any package. Import `override`, `Self`,
  `TypeIs`, `Unpack` and `TypedDict` from `typing`; xtr-maker's generated code does.
- Third-party dependencies need at least the first release that supports Python 3.14, and that
  every package's tests pass on:

  | Dependency | Was | Now | Used by |
  |---|---|---|---|
  | `aio-pika` | 9.4 | 9.6 | xtr-amqp-messenger |
  | `aiosmtplib` | 5.1 | 5.1.3 | xtr-mailer — earlier releases let a line break into a command and whitespace into the local hostname |
  | `anyio` | 4.0 | 4.10 | every package that depends on it |
  | `asyncmy` | 0.2.9 | 0.2.12 | xtr-orm `mysql` |
  | `asyncpg` | 0.29 | 0.31 | xtr-orm `postgres` |
  | `cryptography` | 43, 45 | 46 | xtr-mime `dkim` and `smime`, xtr-recipes |
  | `email-validator` | 2.3 | 2.4 | xtr-mime |
  | `fastapi` | 0.121.3 | 0.143.1 | xtr-dependency-injection `fastapi`, as every package serving requests already required |
  | `idna` | 3.10 | 3.11 | xtr-mime |
  | `libcst` | 1.4 | 1.8.6 | xtr-maker |
  | `msgspec` | 0.18 | 0.20 | xtr-logging, xtr-orm-messenger |
  | `pydantic-settings` | 2.4 | 2.12 | xtr-dotenv |
  | `pynacl` | 1.5 | 1.6 | xtr-cache `sodium` |
  | `python-dotenv` | 1.0 | 1.2.2 | xtr-dotenv |
  | `python-multipart` | 0.0.9, 0.0.18 | 0.0.21 | xtr-http-kernel, xtr-security-oauth2-server, xtr-security-openid-connect-server |
  | `redis` | 5.0 | 7.1 | xtr-cache, xtr-lock and xtr-rate-limiter `redis` |
  | `rich` | 13.6 | 15.0 | xtr-console — earlier releases warn instead of answering empty when a hidden question meets input that has ended |
  | `sqlalchemy` | 2.0.41 | 2.0.52 | xtr-orm, xtr-orm-messenger, xtr-ai-orm-conversation-store |
  | `starlette` | 1.3.1 | 1.6 | xtr-security-http, as xtr-http-kernel already required |
  | `taskiq-aio-pika` | 0.6.0 | 0.6.1 | xtr-amqp-messenger |

  Every other floor already supported Python 3.14 and stays as it was.

### xtr-dependency-injection

- `Kernel(concurrent_scoped_access=...)` defaults to `True`, and `create_container()` compiles the
  same way: two tasks of one unit asking for the same scoped service get one instance. Passing
  `concurrent_scoped_access=True` is no longer needed.
- A `bind_callable` call made outside any unit of work now opens a unit of its own for the call,
  so its scoped services are built for that call and closed after it.
- A unit's container refuses to resolve once its unit has exited (`UnitOfWorkClosedError`), and
  every container refuses once its kernel has shut down (`KernelShutDownError`).
- Closing a unit is shielded from cancellation and bounded at 30 seconds
  (`ScopeTeardownTimeoutError` when nothing else is being raised). A cleanup that fails after a
  clean unit raises an `ExceptionGroup` of what failed, no longer wireup's `ContainerCloseError`.
  A failing or hung cleanup while the unit raised is a
  note on the unit's own error, and is also logged once as a warning on the
  `xtr_dependency_injection` standard-library logger.
- Shutting a kernel down waits up to 30 seconds for the units still open, after the shutdown hooks
  and before the bundles shut down.
- Only built singletons are reset between messages (`kernel.reset`); scoped and transient services
  end with their unit, so they need no `__weakref__` and are no longer tracked.
- State kept for one unit belongs to a `UnitParticipantInterface` participant (tag
  `kernel.unit_participant`); a context variable that must not reach a new connection is
  registered with `register_detached_variable` (`DetachedVariableConflictError` when registered
  twice with different values). `open_unit_of(container)` and `detached_context()` are new.
- In a debug kernel, a singleton factory reading `current_unit_of_work()` or `current_connection()`
  raises `UnitReadDuringSingletonBuildError`.
- A note about a failed rollback after a failed boot, or about a failed cleanup, names an error
  that cannot be printed as `[unprintable module.Class]` instead of replacing the error.

### xtr-service-contracts

- `UnitParticipantInterface` is new: `unit_began()` and `unit_ended(token)`.

### xtr-http-kernel

- `LogUnitListener` is removed: the log unit of a request comes from xtr-logging's
  `LogUnitParticipant`, which the logging bundle registers.
- `setup()` serves every connection in a detached context, so nothing a library keeps for one
  request reaches the next request on the same connection. A server's `--reset-contextvars` (or
  `reset_contextvars=True`) is needed only for the application's own context variables.
  Middleware added after `setup()` runs outside the request's unit of work.
- Every request finishes, whatever ends it: one `ResponseEvent` per request, `FinishRequestEvent`
  on every path, and the terminate step bounded at 30 seconds, in its own task.
- `HttpKernelConfig.max_body_size` defaults to 10 MiB; a larger body is answered `413` before the
  application sees it. Set it to `None` to lift the limit, or raise it per route.
- `HttpKernelConfig.trusted_hosts` (empty by default) refuses any other `Host` with a `400` before
  the lifecycle. A malformed `Host` no longer fails the request.
- A `4xx` exception is logged at `INFO`, not `ERROR`.
- `starlette>=1.6` is required.

### xtr-http-foundation

- Session storage: `write(session_id, data, ttl, *, must_exist=False) -> bool`; a write to an
  entry that must exist but is gone is refused, and a destroyed session is never written back.
- Only an id of the generated length (48 hexadecimal characters) is reattached; any other cookie
  value starts a new session.
- `SessionCookieConfig.secure` defaults to unset: the cookie is `Secure` over https and not over
  plain http. `secure=False` keeps it insecure everywhere. A `__Host-` or `__Secure-` name, or
  `samesite="none"`, refuses an insecure cookie.
- A session starts once per request, however many tasks read it at once.

### xtr-security

- A stateful firewall's logout and switch-user ask for a CSRF token by default (`enable_csrf`
  unset means "on for stateful firewalls"). Render their URLs through the generators, or set
  `enable_csrf=False` to keep the old behaviour.
- A saved target from another origin is dropped after login; a path matcher strips `root_path`
  on a segment boundary only.
- `LoginLinkConfig.max_uses` (unset by default) limits how often one login link logs in.
- Successful logins count against the per-IP login limit, so a burst of requests cannot slip past
  it; the local per-user count is reset by a success, the per-IP count is not refunded.
- Remember-me cookies are `Secure` over https by default (`RememberMeConfig(secure=False)` keeps
  them insecure).
- With the logging bundle active, the oauth2 and userinfo token handlers write the failures their
  server explains to the application's logger; with the clock bundle active, introspected times
  are judged by the application's clock. Authenticator factories now receive the real container
  builder instead of `None`.
- `Kernel(concurrent_scoped_access=True)` is no longer a step of this bundle's setup: it is the
  default.

### xtr-security-core

- `TokenProviderInterface.update_token(series, expected_value, token_value, last_used) -> bool` is
  conditional: it writes only while the stored value is still `expected_value`, so two requests
  rotating one remember-me token at once rotate it once.

### xtr-security-http

- The remember-me handler rotates a token once under concurrent requests, and a losing rotation
  stages no cookie.
- The access-token handlers name an error that cannot be printed by its class.

### xtr-security-oauth2-server-core and xtr-security-oauth2-server

- Two concurrent redemptions of one authorization code, or one device code, issue one pair of
  tokens. `DeviceCodeRepositoryInterface.revoke_device_code` returns whether it won, and gains
  `record_device_code_decision` and `record_device_code_poll`, each a conditional write returning a
  `bool`. Device flows in progress during the upgrade fail once.
- A spent or foreign device code is answered `invalid_grant`.
- Basic client credentials are form-decoded (`%` and `+`); Basic and body credentials together
  are refused; a public client cannot introspect; `invalid_grant` carries no hint.
- A custom response type implements `set_refresh_token_scopes`; a narrowed refresh keeps the
  original scopes on the next refresh token.
- A password grant for a user named like the client it goes through issues no token.
- Every authorization redirect carries `iss`; `make_redirect_uri` needs `set_private_key`. An
  unregistered scope is refused at `/authorize` with `invalid_scope`. A stored redirect URI with a
  fragment no longer loads: register it without one.

### xtr-security-openid-connect-server

- The build refuses an HMAC ID-token algorithm, and a login firewall that does not list
  `PROMPT_LISTENER`.
- `login_required` and `consent_required` redirects carry `iss`.

### xtr-logging

- `LoggingConfig` redacts credentials by default; listing `processors` replaces that default, so
  add the redacting processor yourself when you list your own.
- `include_stacktraces` no longer implies `allow_inline_line_breaks`; bidirectional control
  characters and U+2028/U+2029 are stripped from records.
- Fields declared `repr=False` are not logged.
- Deduplication keeps digests, not the records' text (an existing store stops matching once), and
  holds 10 000 entries by default.
- `RotatingFileHandler` follows the clock it is given, not the record's date.
- `clear_context()` inside a unit keeps the lasting values bound outside it.

### xtr-event-dispatcher

- A listener service that is not a singleton is refused at build (`InvalidListenerError`).
- `ScopedEventDispatcher.reset()` is async.
- In debug mode, a traced dispatcher's per-request trace is reset for every new connection.

### xtr-messenger

- `xtr_messenger.bridge.amqp` is removed: import from `xtr_amqp_messenger.transport`.
- Only singletons are reset between messages; a failing reset is logged on `messenger` and never
  changes a message's outcome.
- A held-back follow-up that fails no longer fails, or re-runs, its committed parent: it is
  announced on its own (`WorkerMessageFailedEvent`, `will_retry=False`).
  `DelayedMessageHandlingError(envelope, failures)` carries each follow-up with its error.
- `RetryingReceiverInterface.will_retry(envelope)` and `WorkerMessageFailedEvent.will_retry` are
  new.
- A stopping worker waits up to 30 seconds for the messages in hand, then cancels them; a
  cancelled handler counts as a failed attempt.

### xtr-amqp-messenger

- See xtr-messenger: the bridge module moved here.
- No behaviour change, but the README now states the retry delay (each retry waits n times the
  one before it, from `base_delay_seconds`, at most 60 seconds) and how to bound `taskiq.dlq`: with a RabbitMQ
  policy, since declaring limits on the existing queue fails with `PRECONDITION_FAILED`.

### xtr-orm

- SQL parameters are hidden from errors and logs outside debug (`hide_parameters`).
- A message dispatched from code already in a transaction runs in a savepoint: the caller's work is
  neither committed nor rolled back by it.
- `orm_close_connection` closes the unit's session before its connection's pool.
- `orm_open_transaction_logger` logs the message type and id, never its body.

### xtr-orm-messenger

- A rejected `orm://` message is retried — `max_attempts` (3), `base_delay_seconds` (1.0) — then
  moved to `failure_queue` (`"failed"`) instead of deleted.
- A message a long handler holds is kept alive automatically; handlers must still be idempotent.
- A claim cancelled midway is released; a dropped LISTEN connection is replaced.

### xtr-console

- A command is cancelled on SIGTERM: its shutdown hooks run and it exits `143`. A second SIGTERM
  uses the handler in force before the command.
- `debug:*` commands print application text literally.
- An error that cannot be printed is reported as `[unprintable module.Class]`.

### xtr-cache

- A cached value that fails to unpickle is a miss for that key only; the rest of a batch read is
  kept.
- `WarmedCache.lock()` is async (`async with`); `cache:clear` keeps the lock file.

### xtr-storage

- `LocalAdapter` writes replace the file (a new inode: hard links to the old file no longer see
  updates). A local storage rooted at `/` works.

### xtr-serializer

- The default context is read-only to the steps that read it.

### xtr-lock

- After a failed read-to-write upgrade, a lock re-reads from its store whether it still holds the
  read lock.

### xtr-rate-limiter

- A shared limiter keeps its limit under concurrent consumers, and works across event loops.

### xtr-http-client

- `HttpxHttpClient` keeps its connection pools per event loop: `aclose()` closes the running loop's
  pools only.
- A custom `RetryStrategyInterface` reads `Retry-After` from `context.response`; a server's
  `Retry-After` is capped at 60 seconds by default.
- The private-network guard sends no default headers or query on a cross-origin redirect.
- A request's resolved address pins that request only; traces are bounded and mask credentials.
- A `ThrottlingHttpClient` booking is never handed back.

### xtr-webhook

- Signatures default to the Standard Webhooks format at both ends; set `signature_format="legacy"`
  on both to talk to 6.x peers.
- `RequestParser` claims every `POST` and decodes it only after the signature is verified; the
  private-network guard is on by default. `WebhookConfig.id_store` / `id_ttl` acknowledge a
  duplicate without handling it again.

### xtr-mailer

- SMTP refuses `AUTH` over an unencrypted session to a server that is not on this machine; use TLS
  or add `allow_plain_auth=1` to the DSN.

### xtr-notifier

- `NotificationLoggerListener` is registered in debug only; failure reports carry no traceback
  unless `include_traceback=True`, and skip the notifier's own messages.

### xtr-telegram-notifier

- Uploads are read when the option is set and travel as base64 (larger queued payloads); an error
  names its cause's class.

### xtr-ai

- A delegated agent runs under the caller's `usage_limits`; its own no longer apply.
- A service that is not a singleton under one of the abstract ai keys is refused at build.
- Platform `options` values are hidden in `repr`; each platform keeps at most 64 models.
- `AgentCallCommand` takes a `ScopeFactoryInterface`: each prompt of `ai:agent:call` is a unit of
  work of its own.

### xtr-remote-event

- Consumers are built in the unit of work of the message they consume, so a consumer may be
  scoped; `ConsumeRemoteEventHandler` and its locator are scoped.

### xtr-workflow

- One transition at a time is applied per subject; a store implementing
  `CompareAndSetMarkingStoreInterface` refuses a transition whose marking changed meanwhile.

### xtr-scheduler

- `CheckpointInterface.keep()` is new: a batch whose lock is lost stops without saving.
