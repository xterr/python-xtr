# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false
# The local object-store stand-in and the serving layer around it ship no type
# information; the directives above are confined to this one test-support module.
"""A local object-store stand-in for the integration tests: an in-process server.

The server binds an ephemeral port on the loopback interface, so the whole test
suite reaches a real object store over real HTTP without a network, a container
or an environment variable, and two checkouts running the suite at once cannot
collide on a port. Credentials are never set in the environment — a test hands
them to the adapter as arguments — and each test works in a bucket of its own.

The serving layer and the stand-in each emit a ``Server`` header, and that one
header is a singleton the async client refuses to see twice; the wrapper below
drops the application's copy so the serving layer's stands alone, which keeps
every test deterministic in development mode as well as the default one.
"""

from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING

import pytest
from moto.moto_server.werkzeug_app import DomainDispatcherApplication, create_backend_app
from werkzeug.serving import make_server

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

    from _typeshed import OptExcInfo
    from _typeshed.wsgi import StartResponse, WSGIApplication, WSGIEnvironment

    from xtr_storage.adapter.s3_adapter import S3Adapter

__all__ = ["create_bucket", "make_bucket_public", "moto_endpoint"]


def _strip_server_header(application: WSGIApplication) -> WSGIApplication:
    """Wrap a WSGI application so it never emits its own ``Server`` header.

    The serving layer emits one already, and the async client rejects a response
    that carries two, so the application's copy is filtered out on the way past.
    """

    def wrapped(
        environ: WSGIEnvironment,
        start_response: StartResponse,
    ) -> Iterable[bytes]:
        def patched(
            status: str,
            headers: list[tuple[str, str]],
            exc_info: OptExcInfo | None = None,
        ) -> Callable[[bytes], object]:
            kept = [(name, value) for name, value in headers if name.lower() != "server"]
            return start_response(status, kept, exc_info)

        return application(environ, patched)

    return wrapped


@pytest.fixture(scope="session")
def moto_endpoint() -> Iterator[str]:
    """Start the stand-in for the test session and yield its endpoint url."""
    application = _strip_server_header(DomainDispatcherApplication(create_backend_app))
    server = make_server("127.0.0.1", 0, application, threaded=True)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join()


async def create_bucket(adapter: S3Adapter, bucket: str) -> None:
    """Create ``bucket`` through the adapter's own client, no location constraint.

    Naming a location constraint is what a bucket creation in the default region
    must not do, so the creation goes straight through the backend call that adds
    none, rather than the directory-making path that would.
    """
    _ = await adapter._get_bridge().call("call_s3", "create_bucket", Bucket=bucket)


async def make_bucket_public(adapter: S3Adapter, bucket: str) -> None:
    """Grant anyone read of every object in ``bucket``, as a published bucket has.

    A composed public url is unsigned, so the object it names must be readable
    without credentials for the fetch to resolve; this sets the bucket policy
    that allows it, leaving each object's own access list untouched.
    """
    policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket}/*",
                }
            ],
        }
    )
    _ = await adapter._get_bridge().call(
        "call_s3", "put_bucket_policy", Bucket=bucket, Policy=policy
    )
