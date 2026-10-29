# Send and handle messages

A message moves work out of the request that asks for it. The `shop` application
declares a message, a handler takes it, and the bus carries it between the two.
A transport decides where the handler runs: in the same process, or in a worker
behind a broker.

## Before you start

1. Create the application with `uvx xtr-cli new shop --webapp`. The
   [new application page](../setup/new-application.md) describes each answer.
2. Add the package with `uv add xtr-messenger`.
3. Apply the recipe with `uv run xtr-recipes recipes:sync`. The recipe lists
   `MessengerBundle`, writes `src/shop/config/packages/messenger.py` and writes
   `MESSENGER_DSN` in `.env`.
4. Run `uv run shop debug:bundles`. The output names `messenger` as `active`.

## Declare a message

A message is a frozen dataclass that carries identifiers, and nothing else.

1. Create `src/shop/message.py`.
2. Declare the class with `@as_message`:

   ```python
   """The messages of the application."""

   from __future__ import annotations

   from dataclasses import dataclass
   from uuid import UUID

   from xtr_messenger import as_message

   __all__ = ["PlaceOrder"]


   @as_message(name="shop.place_order.v1")
   @dataclass(frozen=True, slots=True)
   class PlaceOrder:
       order_id: UUID
   ```

3. Keep the `name` value stable. The producer and the consumer share that name
   and nothing else.

> [!NOTE]
> The default name is `module:QualName`, which changes when the class moves. An
> explicit, versioned name outlives a deployment.

## Write a handler

A handler imports the message and nothing more of the application.

1. Create `src/shop/handler.py`.
2. Declare the function with `@as_message_handler`:

   ```python
   """The handlers of the application."""

   from __future__ import annotations

   from xtr_messenger import as_message_handler

   from shop.message import PlaceOrder

   __all__ = ["place_order"]


   @as_message_handler(PlaceOrder)
   async def place_order(message: PlaceOrder) -> None:
       """Record the order."""
   ```

3. Annotate every other parameter with `Injected[T]` to ask the container for a
   service. A bare annotation gets nothing.

> [!NOTE]
> Every handler of a message runs, in the order of the declarations. A handler
> that raises an error does not stop the others, and the bus reports each
> failure in one `HandlersFailedError`.

## Send the message

The bus answers to `MessageBusInterface`. A route, a command or a service asks
the container for it.

1. Open `src/shop/web/routes.py`.
2. Add a route that sends the message:

   ```python
   from uuid import UUID

   from fastapi import APIRouter
   from xtr_dependency_injection import Injected
   from xtr_messenger import MessageBusInterface

   from shop.message import PlaceOrder

   router = APIRouter()


   @router.post("/orders/{order_id}")
   async def place(order_id: UUID, bus: Injected[MessageBusInterface]) -> dict[str, str]:
       """Send the order on its way."""
       _ = await bus.dispatch(PlaceOrder(order_id=order_id))
       return {"status": "accepted"}
   ```

3. Serve the application with `uv run shop-web`.
4. Send a request with
   `curl -X POST http://127.0.0.1:8000/orders/3f6c0e9c-0000-4000-8000-000000000001`.
   The answer is `{"status":"accepted"}`.

## Route the message to a transport

With nothing in the routing table, the bus neither sends nor handles the
message. The configuration file names each transport and maps each message
class to one.

1. Open `src/shop/config/packages/messenger.py`.
2. Import the message with `from shop.message import PlaceOrder`.
3. Map the class to the `jobs` transport:

   ```python
   @configure
   def messenger() -> MessageBusConfig:
       """One transport, its broker read from ``MESSENGER_DSN``."""
       return MessageBusConfig(
           transports={"jobs": TransportConfig(env("MESSENGER_DSN"))},
           routing={PlaceOrder: "jobs"},
       )
   ```

4. Choose the scheme of `MESSENGER_DSN` for this machine:

   | DSN | What the transport does |
   |---|---|
   | `sync://` | The handler runs in the calling process, during the send |
   | `in-memory://` | The transport keeps each message for a worker or a test |
   | `amqp://`, `amqps://` | RabbitMQ holds the message until a worker takes it |

5. Put that value in `.env.local`, for example `MESSENGER_DSN=sync://`.
6. Run `uv run shop debug:config messenger`. The output prints the transports
   and the routing table.

A query string carries the settings of a transport: `queue`, `max_attempts`,
`prefetch_count` and `dead_letter_queue` among them. The recipe writes
`MESSENGER_DSN=amqp://guest:guest@127.0.0.1:5672/?queue=messages`. The
`options` argument of `TransportConfig` takes the same names, and wins over the
query string. A name the scheme does not accept raises
`UnknownTransportOptionError` when the bus builds.

> [!WARNING]
> Keep a real password out of `.env`, because git tracks that file. Put the
> broker URL of your machine in `.env.local`, which `.gitignore` excludes.

> [!NOTE]
> An `amqp://` transport expects the `rabbitmq_delayed_message_exchange` plugin
> on the broker. A delay, and the backoff of a retry, both ride that exchange.

## Run the worker

1. Run `uv run shop messenger:consume jobs`. The worker takes each message from
   the `jobs` transport and calls the handlers.
2. Name more than one transport to serve several, for example
   `uv run shop messenger:consume high low`.
3. Add `--time-limit 3600` to stop the worker after an hour.
4. Add `-vv` to read one record for each handler that runs.
5. Send `SIGTERM` to stop the worker once it settles the message in hand. Press
   Ctrl-C to cancel it at once.

The worker tries each message one time, and never again. A transport owns the
redelivery, the backoff and the dead-letter queue, because only a transport
counts the tries. A retry calls every handler again, so keep each handler safe
to repeat.

## Add a recurring message

[xtr-scheduler](https://github.com/xterr/python-xtr/tree/main/packages/xtr-scheduler)
sends a message on a timetable, through the same bus.

1. Add the package with `uv add "xtr-scheduler[cron]"`.
2. Apply the recipe with `uv run xtr-recipes recipes:sync`.
3. Create `src/shop/task.py` and declare the task:

   ```python
   """The recurring work of the application."""

   from __future__ import annotations

   from xtr_scheduler.decorator import as_cron_task

   __all__ = ["purge_baskets"]


   @as_cron_task("0 3 * * *", timezone="Europe/Bucharest")
   async def purge_baskets() -> None:
       """Remove every basket nobody came back to."""
   ```

4. Run `uv run shop debug:scheduler`. The table names each trigger with the
   date of its next run.
5. Run `uv run shop messenger:consume scheduler_default` to serve the
   timetable.

> [!NOTE]
> `@as_periodic_task("10 minutes")` names an interval in place of a cron
> expression. A task that names no schedule joins the `default` one, which
> keeps no state: a restarted worker starts from now.

## Next step

- [Test an application](testing.md) drains a message in a test, with no broker.
- [Configure a bundle](configuration.md) changes a value of the message bus.
- [xtr-messenger](https://github.com/xterr/python-xtr/tree/main/packages/xtr-messenger)
  describes the envelope, the stamps and the middleware chain.
- The [API reference](https://xterr.github.io/python-xtr/api/xtr_messenger/)
  lists every class of the package.
