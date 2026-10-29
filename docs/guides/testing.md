# Test an application

`uvx xtr-cli new shop --webapp` writes two tests. One builds the kernel, the
other drives the web application through an ASGI transport. This page grows
that suite. It replaces a service with a fake, it freezes the clock, and it
drains a message with no broker.

## Before you start

1. Create the application with `uvx xtr-cli new shop --webapp`. The
   [new application page](../setup/new-application.md) describes each answer.
2. Run `uv run pytest`. The two generated tests pass.
3. Read `tests/test_kernel.py` and `tests/test_web.py`. Each new test follows
   the shape of one of them.

The suite runs on `pytest` with `anyio`. Mark each async test with
`pytest.mark.anyio` and give it an `anyio_backend` fixture. The strict mode of
`pytest-asyncio` does not work here.

## Build the kernel in a test

The cheapest test asks the kernel to build. The build compiles the container,
so a service the container cannot fill fails the test.

1. Open `tests/test_kernel.py`.
2. Read the generated test:

   ```python
   """The application's kernel builds, with every listed bundle."""

   from __future__ import annotations

   from shop.kernel import kernel


   def test_the_kernel_builds_in_the_test_environment() -> None:
       _ = kernel.with_env("test").build()
   ```

3. Call `kernel.with_env("test")` in every test. The `test` environment keeps
   the dev values of the application out of the suite.

## Ask the booted container for a service

`boot_for_test` builds for the `test` environment, applies the overrides, and
then boots. Each boot hook and each service reads the replacements.

1. Create `tests/test_catalogue.py`.
   The examples below replace `Catalogue`, a service of the application in
   `src/shop/catalogue.py`. Use a service of your own in its place.
2. Write the test around `boot_for_test`:

   ```python
   from __future__ import annotations

   import pytest
   from xtr_dependency_injection.testing import boot_for_test

   from shop.catalogue import Catalogue
   from shop.kernel import kernel

   pytestmark = pytest.mark.anyio


   @pytest.fixture
   def anyio_backend() -> str:
       return "asyncio"


   class FakeCatalogue(Catalogue):
       def titles(self) -> list[str]:
           return ["a fake title"]


   async def test_the_container_answers_with_the_fake() -> None:
       async with await boot_for_test(kernel, overrides={Catalogue: FakeCatalogue()}) as booted:
           catalogue = await booted.container.get(Catalogue)

       assert catalogue.titles() == ["a fake title"]
   ```

3. Await `booted.container.get(...)`, because the container answers with an
   awaitable.
4. Write a key as a type, or as a `(type, qualifier)` pair for a qualified
   service.

> [!NOTE]
> The pytest plugin of the container offers `booted_kernel` and `container`
> fixtures. Add `pytest_plugins = ["xtr_dependency_injection.testing.pytest_plugin"]`
> to `tests/conftest.py` and return the kernel from an `xtr_kernel` fixture.

## Drive the web application

The lifespan of the application builds and boots the kernel that serves each
request. Open it around the client, so the requests reach a booted kernel.

1. Open `tests/test_web.py`.
2. Read the generated test:

   ```python
   """The web application answers, served from its kernel."""

   from __future__ import annotations

   from http import HTTPStatus

   import httpx
   import pytest

   from shop.web.app import app

   pytestmark = pytest.mark.anyio


   @pytest.fixture
   def anyio_backend() -> str:
       return "asyncio"


   async def test_the_home_page_answers() -> None:
       async with app.router.lifespan_context(app):
           transport = httpx.ASGITransport(app=app)
           async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
               response = await client.get("/")

       assert response.status_code == HTTPStatus.OK
       assert response.json() == {"status": "ok"}
   ```

3. Park the fakes on the application with `override_services` before you enter
   the lifespan:

   ```python
   from xtr_http_kernel.testing import override_services

   from shop.catalogue import Catalogue


   async def test_the_route_reads_the_fake_catalogue() -> None:
       with override_services(app, {Catalogue: FakeCatalogue()}):
           async with app.router.lifespan_context(app):
               transport = httpx.ASGITransport(app)
               async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                   response = await client.get("/")

       assert response.status_code == HTTPStatus.OK
   ```

4. Run two tests of one application one after the other. The overrides live on
   the application itself, so a parallel run restores the wrong services.

> [!CAUTION]
> Do not reach for the `TestClient` of FastAPI. It uses a deprecated path of
> the framework. A suite that turns a warning into an error fails on it.

## Freeze the clock

A class that takes a `ClockInterface` parameter needs a `MockClock` and nothing
else. Under a kernel, replace the `Clock` service: both `ClockInterface` and
`Clock.get()` answer with it.

1. Create `tests/test_clock.py`.
2. Override the service with a frozen clock:

   ```python
   from __future__ import annotations

   import pytest
   from xtr_clock import Clock, ClockInterface, MockClock
   from xtr_dependency_injection.testing import boot_for_test

   from shop.kernel import kernel

   pytestmark = pytest.mark.anyio


   @pytest.fixture
   def anyio_backend() -> str:
       return "asyncio"


   async def test_the_clock_stands_still() -> None:
       frozen = Clock(MockClock("2026-01-01 12:00:00"), "UTC")

       async with await boot_for_test(kernel, overrides={Clock: frozen}) as booted:
           clock = await booted.container.get(ClockInterface)

       assert clock.now().isoformat() == "2026-01-01T12:00:00+00:00"
   ```

3. Use `mock_time` for code that calls `xtr_clock.now()` in place of a clock it
   holds:

   ```python
   from xtr_clock import now
   from xtr_clock.testing import mock_time


   def test_a_helper_reads_the_frozen_clock() -> None:
       with mock_time("2026-01-01 12:00:00") as clock:
           assert now().hour == 12
           clock.sleep(3600)
           assert now().hour == 13
   ```

4. Move time with `clock.sleep(seconds)`. A frozen clock returns at once and
   reports the later instant.

> [!NOTE]
> A `MockClock` freezes in UTC, where a real clock reports in the zone of the
> machine. A frozen test gives the same answer on every laptop.

## Drain a message with no broker

The `in-memory://` transport keeps each message in the process. One factory
instance serves the bus and the worker, so both share the same record.

1. Create `tests/test_place_order.py`.
2. Send the message, read the record, and let a worker drain it:

   ```python
   """The message reaches its handler on an in-memory transport."""

   from __future__ import annotations

   from uuid import uuid4

   import pytest
   from xtr_messenger import (
       InMemoryTransport,
       InMemoryTransportFactory,
       MessageBusConfig,
       MessageBusFactory,
       TransportConfig,
       WorkerFactory,
   )

   from shop.message import PlaceOrder

   pytestmark = pytest.mark.anyio


   @pytest.fixture
   def anyio_backend() -> str:
       return "asyncio"


   async def test_the_order_reaches_its_handler() -> None:
       config = MessageBusConfig(
           transports={"jobs": TransportConfig("in-memory://?serialize=true")},
           routing={PlaceOrder: "jobs"},
       )
       factories = [InMemoryTransportFactory()]
       order = PlaceOrder(order_id=uuid4())

       bus = MessageBusFactory(config, factories).bus()
       _ = await bus.dispatch(order)

       jobs = factories[0].create(config.transports)["jobs"]
       assert isinstance(jobs, InMemoryTransport)
       assert jobs.messages == (order,)

       await WorkerFactory(config, factories).worker(["jobs"]).run()
       assert jobs.rejected == ()
   ```

3. Add `?serialize=true` to the DSN. The transport carries each message through
   the serializer, so a field that only a real broker refuses fails here.
4. Call `jobs.clear()` between tests to reset the record.

The worker returns once it drains the queue. The
[message guide](messages.md) describes the message, the handler and the
routing table the test uses.

## Check the whole suite

1. Run `uv run pytest` from the root of the application.
2. If a test fails on a service the container cannot fill, read the name in the
   error. The kernel reports it at build, not on the first request.

> [!NOTE]
> `assert_zero_config` belongs to the author of a bundle, not to an
> application. It proves that a bundle builds and boots with no configuration
> file. The container package describes it under *The zero-config contract*.

## Next step

- [Send and handle messages](messages.md) writes the message and the handler
  that the test above drains.
- [Configure a bundle](configuration.md) names the values the `test`
  environment changes.
- [xtr-dependency-injection](https://github.com/xterr/python-xtr/tree/main/packages/xtr-dependency-injection)
  describes `boot_for_test`, `apply_overrides` and the pytest plugin.
- [xtr-clock](https://github.com/xterr/python-xtr/tree/main/packages/xtr-clock)
  describes every clock and the modifier grammar.
- The [API reference](https://xterr.github.io/python-xtr/api/xtr_dependency_injection/)
  lists every class of the container.
