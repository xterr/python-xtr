# Components

This page lists each xtr package by the job that it does. Each package has a
README with its full description and its examples. The API reference shows its
classes and functions.

To add a package to an application, read [Add a package](../setup/add-a-package.md).
To use a package alone, install it with `uv add` and read its README.

## Application and kernel

| Package | What it does | API |
|---|---|---|
| [xtr-dependency-injection](https://github.com/xterr/python-xtr/tree/main/packages/xtr-dependency-injection) | Collects the bundles of an application and builds its container. It also runs the start and the stop of the application. | [API](https://xterr.github.io/python-xtr/api/xtr_dependency_injection/) |
| [xtr-console](https://github.com/xterr/python-xtr/tree/main/packages/xtr-console) | Async console applications. A command is a function or a class, and the container gives it its services. | [API](https://xterr.github.io/python-xtr/api/xtr_console/) |
| [xtr-cli](https://github.com/xterr/python-xtr/tree/main/packages/xtr-cli) | Makes a new console application or web application in one command, and serves it. | [API](https://xterr.github.io/python-xtr/api/xtr_cli/) |
| [xtr-recipes](https://github.com/xterr/python-xtr/tree/main/packages/xtr-recipes) | Applies the recipe of each package to a project, and undoes it when you remove the package. | [API](https://xterr.github.io/python-xtr/api/xtr_recipes/) |
| [xtr-dotenv](https://github.com/xterr/python-xtr/tree/main/packages/xtr-dotenv) | Loads layers of `.env` files into the environment. It also gives the same layers as a typed settings model. | [API](https://xterr.github.io/python-xtr/api/xtr_dotenv/) |
| [xtr-logging](https://github.com/xterr/python-xtr/tree/main/packages/xtr-logging) | Channels, handlers, processors and formatters behind one logger interface. | [API](https://xterr.github.io/python-xtr/api/xtr_logging/) |
| [xtr-clock](https://github.com/xterr/python-xtr/tree/main/packages/xtr-clock) | A clock that the container gives to your code, a date and time with a time zone, and a frozen clock for tests. | [API](https://xterr.github.io/python-xtr/api/xtr_clock/) |

## HTTP

| Package | What it does | API |
|---|---|---|
| [xtr-http-kernel](https://github.com/xterr/python-xtr/tree/main/packages/xtr-http-kernel) | Serves a FastAPI application from the kernel. Events turn each request into a response. | [API](https://xterr.github.io/python-xtr/api/xtr_http_kernel/) |
| [xtr-http-foundation](https://github.com/xterr/python-xtr/tree/main/packages/xtr-http-foundation) | Matchers for a request, tools for IP networks, and the session of a request. | [API](https://xterr.github.io/python-xtr/api/xtr_http_foundation/) |
| [xtr-http-message](https://github.com/xterr/python-xtr/tree/main/packages/xtr-http-message) | HTTP requests, responses, streams, URIs and uploaded files, with one factory for all of them. | [API](https://xterr.github.io/python-xtr/api/xtr_http_message/) |
| [xtr-http-client](https://github.com/xterr/python-xtr/tree/main/packages/xtr-http-client) | An async HTTP client with typed options, scoped clients, retries, a guard for private networks and a mock client for tests. | [API](https://xterr.github.io/python-xtr/api/xtr_http_client/) |

## Security

| Package | What it does | API |
|---|---|---|
| [xtr-security](https://github.com/xterr/python-xtr/tree/main/packages/xtr-security) | The bundle of the security family. It configures and connects the security components. | [API](https://xterr.github.io/python-xtr/api/xtr_security/) |
| [xtr-security-core](https://github.com/xterr/python-xtr/tree/main/packages/xtr-security-core) | Users, tokens, roles, voters and the authorization decision. | [API](https://xterr.github.io/python-xtr/api/xtr_security_core/) |
| [xtr-security-http](https://github.com/xterr/python-xtr/tree/main/packages/xtr-security-http) | Firewalls, authenticators and bearer access tokens for HTTP requests. | [API](https://xterr.github.io/python-xtr/api/xtr_security_http/) |
| [xtr-security-csrf](https://github.com/xterr/python-xtr/tree/main/packages/xtr-security-csrf) | Protection against cross-site request forgery: it makes and checks tokens, and keeps them in the session. | [API](https://xterr.github.io/python-xtr/api/xtr_security_csrf/) |
| [xtr-password-hasher](https://github.com/xterr/python-xtr/tree/main/packages/xtr-password-hasher) | Password hashes behind one interface. The default is argon2id. It also upgrades old hashes. | [API](https://xterr.github.io/python-xtr/api/xtr_password_hasher/) |
| [xtr-security-jwt](https://github.com/xterr/python-xtr/tree/main/packages/xtr-security-jwt) | JSON Web Tokens that the application signs: key sets, an encoder and a token manager. | [API](https://xterr.github.io/python-xtr/api/xtr_security_jwt/) |
| [xtr-security-oauth2-server](https://github.com/xterr/python-xtr/tree/main/packages/xtr-security-oauth2-server) | An OAuth 2.0 authorization server, and an authenticator for a resource server. | [API](https://xterr.github.io/python-xtr/api/xtr_security_oauth2_server/) |
| [xtr-security-oauth2-server-core](https://github.com/xterr/python-xtr/tree/main/packages/xtr-security-oauth2-server-core) | The library of the OAuth 2.0 server: grants, servers, entities and response types. | [API](https://xterr.github.io/python-xtr/api/xtr_security_oauth2_server_core/) |

## Messages, events and workflows

| Package | What it does | API |
|---|---|---|
| [xtr-messenger](https://github.com/xterr/python-xtr/tree/main/packages/xtr-messenger) | A message bus with envelopes, stamps, a chain of middleware and transports. | [API](https://xterr.github.io/python-xtr/api/xtr_messenger/) |
| [xtr-scheduler](https://github.com/xterr/python-xtr/tree/main/packages/xtr-scheduler) | Recurring messages on the message bus, with cron and periodic triggers. | [API](https://xterr.github.io/python-xtr/api/xtr_scheduler/) |
| [xtr-event-dispatcher](https://github.com/xterr/python-xtr/tree/main/packages/xtr-event-dispatcher) | Sends events to listeners and subscribers by priority. A listener can stop the event. | [API](https://xterr.github.io/python-xtr/api/xtr_event_dispatcher/) |
| [xtr-remote-event](https://github.com/xterr/python-xtr/tree/main/packages/xtr-remote-event) | Events from other systems, as one value type, sent to the consumer of their source. | [API](https://xterr.github.io/python-xtr/api/xtr_remote_event/) |
| [xtr-webhook](https://github.com/xterr/python-xtr/tree/main/packages/xtr-webhook) | Receives webhooks as events after it checks them, and sends signed webhooks. | [API](https://xterr.github.io/python-xtr/api/xtr_webhook/) |
| [xtr-workflow](https://github.com/xterr/python-xtr/tree/main/packages/xtr-workflow) | Moves objects through workflows and state machines, with guards and events at each step. | [API](https://xterr.github.io/python-xtr/api/xtr_workflow/) |

## Data and resources

| Package | What it does | API |
|---|---|---|
| [xtr-orm](https://github.com/xterr/python-xtr/tree/main/packages/xtr-orm) | Async database engines, sessions and versioned schema migrations. | [API](https://xterr.github.io/python-xtr/api/xtr_orm/) |
| [xtr-cache](https://github.com/xterr/python-xtr/tree/main/packages/xtr-cache) | Cache pools in memory, in files or in Redis, with tags and protection against a stampede. | [API](https://xterr.github.io/python-xtr/api/xtr_cache/) |
| [xtr-storage](https://github.com/xterr/python-xtr/tree/main/packages/xtr-storage) | Files on a local disk, in memory or in object stores, behind one async interface. | [API](https://xterr.github.io/python-xtr/api/xtr_storage/) |
| [xtr-lock](https://github.com/xterr/python-xtr/tree/main/packages/xtr-lock) | Exclusive and shared locks in memory, in files, in Redis or in more than one store. | [API](https://xterr.github.io/python-xtr/api/xtr_lock/) |
| [xtr-rate-limiter](https://github.com/xterr/python-xtr/tree/main/packages/xtr-rate-limiter) | Limits on how often an action can occur, by fixed window, sliding window or token bucket. | [API](https://xterr.github.io/python-xtr/api/xtr_rate_limiter/) |

## Notifications

| Package | What it does | API |
|---|---|---|
| [xtr-notifier](https://github.com/xterr/python-xtr/tree/main/packages/xtr-notifier) | Sends notifications to chat, SMS and push channels through providers that a DSN configures. | [API](https://xterr.github.io/python-xtr/api/xtr_notifier/) |
| [xtr-slack-notifier](https://github.com/xterr/python-xtr/tree/main/packages/xtr-slack-notifier) | The Slack provider of `xtr-notifier`. | [API](https://xterr.github.io/python-xtr/api/xtr_slack_notifier/) |
| [xtr-telegram-notifier](https://github.com/xterr/python-xtr/tree/main/packages/xtr-telegram-notifier) | The Telegram provider of `xtr-notifier`. | [API](https://xterr.github.io/python-xtr/api/xtr_telegram_notifier/) |

## Contracts

Each contracts package contains only interfaces. [Contracts](../architecture/contracts.md)
describes why they exist.

| Package | Its interfaces | API |
|---|---|---|
| [xtr-cache-contracts](https://github.com/xterr/python-xtr/tree/main/packages/xtr-cache-contracts) | Cache reads, item pools, tags and namespaces. | [API](https://xterr.github.io/python-xtr/api/xtr_cache_contracts/) |
| [xtr-event-dispatcher-contracts](https://github.com/xterr/python-xtr/tree/main/packages/xtr-event-dispatcher-contracts) | An event, a dispatcher and the list of listeners. | [API](https://xterr.github.io/python-xtr/api/xtr_event_dispatcher_contracts/) |
| [xtr-http-client-contracts](https://github.com/xterr/python-xtr/tree/main/packages/xtr-http-client-contracts) | An async HTTP request, its response, options and errors. | [API](https://xterr.github.io/python-xtr/api/xtr_http_client_contracts/) |
| [xtr-http-message-contracts](https://github.com/xterr/python-xtr/tree/main/packages/xtr-http-message-contracts) | HTTP messages and their factories. | [API](https://xterr.github.io/python-xtr/api/xtr_http_message_contracts/) |
| [xtr-logging-contracts](https://github.com/xterr/python-xtr/tree/main/packages/xtr-logging-contracts) | The logger, eight levels and a logger that discards each record. | [API](https://xterr.github.io/python-xtr/api/xtr_logging_contracts/) |
| [xtr-service-contracts](https://github.com/xterr/python-xtr/tree/main/packages/xtr-service-contracts) | The container, and what a container does with a service. | [API](https://xterr.github.io/python-xtr/api/xtr_service_contracts/) |
