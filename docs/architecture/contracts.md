# Contracts

A contracts package contains only interfaces. It has no implementation and no
bundle. Its name ends with `-contracts`, for example `xtr-logging-contracts`.

## Why contracts exist

A contracts package lets a library use a feature without a dependency on one
implementation of that feature.

For example, `xtr-messenger` writes log records. It does not depend on
`xtr-logging`. It depends on `xtr-logging-contracts`, which contains only
`LoggerInterface`. The application selects the logger:

- If the application installs `xtr-logging`, the messenger uses that logger.
- If the application installs a different implementation, the messenger uses
  that implementation.
- If the application installs no logger, the messenger writes no log records.

## The contracts packages

| Package | Its interfaces | The xtr implementation |
|---|---|---|
| `xtr-cache-contracts` | Fetch or compute a value, cache pools, tags and namespaces. | `xtr-cache` |
| `xtr-event-dispatcher-contracts` | Events and the dispatcher that sends them. | `xtr-event-dispatcher` |
| `xtr-http-client-contracts` | An async HTTP request, its response, options and errors. It also has a test suite for implementations. | `xtr-http-client` |
| `xtr-http-message-contracts` | HTTP requests, responses, streams, URIs, uploaded files and their factories. | `xtr-http-message` |
| `xtr-logging-contracts` | The logger. | `xtr-logging` |
| `xtr-service-contracts` | The container, and what a container does with a service, for example a reset between two messages. | `xtr-dependency-injection` |

## Interfaces are protocols

Each interface is a `Protocol` with the `@runtime_checkable` decorator. Its name
ends with `Interface`, for example `LoggerInterface`. Thus, a class implements
the interface when it has the methods. The class does not need to inherit from
the interface.
