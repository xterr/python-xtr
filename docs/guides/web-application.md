# Build a web application

A web application serves a FastAPI application from the kernel. The routes, the
request bodies and the generated schema stay FastAPI's own. The kernel adds the
container and the request lifecycle around them.

## Before you start

- Make a web application with the steps in
  [Create an application](../setup/new-application.md).
- Read [the application layout](../setup/application-layout.md) to find the
  files of the `web/` directory.

## Procedure

### Serve the application from the kernel

The `shop --webapp` template writes this file for you. Read it to find how the
two parts connect.

1. Open `src/shop/web/app.py`:

   ```python
   from fastapi import FastAPI
   from xtr_http_kernel import setup

   from shop.kernel import kernel

   from .routes import router

   app = FastAPI(title="shop")
   app.include_router(router)

   setup(app, kernel)
   ```

2. Call `setup(app, kernel)` after the routes and after your own middleware.
   `setup` adds the routes that the bundles contribute, wraps the lifespan of
   the application, and adds the middleware of the lifecycle.

> [!NOTE]
> Every life of the application builds and boots its own kernel. A test can
> start the application many times.

### Add a route

1. Open `src/shop/web/routes.py`.
2. Add a route with the decorator of the router:

   ```python
   @router.get("/books", name="books_list")
   async def books_list() -> list[str]:
       """Answer with every title."""
       return ["Dune", "Solaris"]
   ```

3. Start the server:

   ```sh
   uv run shop-web
   ```

4. Ask for the new path:

   ```sh
   curl -s localhost:8000/books
   ```

   The answer is `["Dune","Solaris"]`.
5. Push `Ctrl-C` to stop the server.

### Use a service in a route

A route asks for a service with the `Injected` marker. The container builds the
service and gives it to the route.

1. Write the service in `src/shop/catalogue.py`:

   ```python
   from xtr_dependency_injection import as_service


   @as_service
   class Catalogue:
       """Answer the titles that the shop sells."""

       def titles(self) -> list[str]:
           return ["Dune", "Solaris"]
   ```

   The kernel scans the `shop` package, so no other registration is necessary.
2. Ask for the service in the route:

   ```python
   from xtr_dependency_injection import Injected

   from shop.catalogue import Catalogue


   @router.get("/books", name="books_list")
   async def books_list(catalogue: Injected[Catalogue]) -> list[str]:
       """Answer with every title."""
       return catalogue.titles()
   ```

3. Start the server again and ask for `/books`. The answer is the same list.

> [!NOTE]
> A service that reads the request must be `lifetime="scoped"` or transient. The
> container refuses a service for the whole life of the application that asks
> for one request.

### Add a listener to the request lifecycle

Each request goes through five events. A listener is a service, so the
container builds it with everything else that it needs.

| Event | When the lifecycle dispatches it | What a listener can do |
|---|---|---|
| `RequestEvent` | The request arrived. | Read it, or answer with `set_response(...)`. |
| `ResponseEvent` | A response is about to start. | Change `status_code` and `headers`. |
| `ExceptionEvent` | Handling raised, and the server sent nothing yet. | Read `exception`, or answer with `set_response(...)`. |
| `FinishRequestEvent` | Handling finished, on every path. | Close what the request opened. |
| `TerminateEvent` | The server sent everything. | Do the work that can wait. |

1. Add the listener to `src/shop/web/routes.py`:

   ```python
   from xtr_event_dispatcher import as_event_listener
   from xtr_http_kernel import ResponseEvent


   @as_event_listener()
   def name_the_shop(event: ResponseEvent) -> None:
       """Put the name of the shop on every response."""
       event.headers["x-shop"] = "shop"
   ```

2. Start the server and read the headers of the answer:

   ```sh
   curl -si localhost:8000/books
   ```

   The answer carries `x-shop: shop` and `x-request-id`. The bundle adds the
   request id to every response.

### Report on the routes

Two commands read the application and serve no request. Both find the
application in `app` of `HttpKernelConfig`, which
`src/shop/config/packages/http_kernel.py` sets to `shop.web.app:app`.

1. List every route in the order that routing tries them:

   ```sh
   uv run shop debug:router
   ```

   The table has the methods, the path, the name and the endpoint of each route.
2. Find the route that answers one path:

   ```sh
   uv run shop router:match /books
   ```

   The command shows `[OK] "/books" is answered by shop.web.routes:books_list`.
3. To ask for another method, add the `--method` option:

   ```sh
   uv run shop router:match /books --method POST
   ```

   The command reports a route that answers the path but refuses the method as
   a near miss.

## Next step

- [Protect a web application](security.md) adds a firewall and access rules.
- [Test an application](testing.md) drives the application in a test.
- [Configure a bundle](configuration.md) changes the request id header and the
  other values of `HttpKernelConfig`.
- The
  [xtr-http-kernel README](https://github.com/xterr/python-xtr/tree/main/packages/xtr-http-kernel)
  describes the routes that a package contributes and the middleware of a
  bundle. It also describes the rate limits and the request as a message.
- The [API reference](https://xterr.github.io/python-xtr/api/xtr_http_kernel/)
  lists every class of the package.
