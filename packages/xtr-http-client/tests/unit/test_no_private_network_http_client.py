from __future__ import annotations

import re
import sys
from typing import TYPE_CHECKING, NoReturn

import pytest
from xtr_http_message import Request

from xtr_http_client import MockHttpClient, MockResponse, NoPrivateNetworkHttpClient
from xtr_http_client.exception import InvalidArgumentError, LogicError, TransportError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

    from xtr_http_client_contracts import HttpResponseInterface, RequestOptions

pytestmark = pytest.mark.anyio


def test_the_guard_is_refused_without_the_package_holding_the_networks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "xtr_http_foundation", None)

    with pytest.raises(LogicError, match="uv add xtr-http-foundation"):
        _ = NoPrivateNetworkHttpClient(MockHttpClient())


def _resolving_to(*addresses: str) -> Callable[[str, int], Awaitable[Sequence[str]]]:
    async def resolve(host: str, port: int) -> Sequence[str]:
        del host, port

        return list(addresses)

    return resolve


async def _never_resolves(host: str, port: int) -> NoReturn:
    del host, port

    raise AssertionError("an address written out must be checked without resolving it")


def _redirect(location: str, status: int = 302) -> MockResponse:
    return MockResponse(b"", {"http_code": status, "response_headers": {"Location": location}})


def _blocked(what: str) -> str:
    """The refusal naming ``what``, as a pattern matching it literally."""
    return re.escape(f"{what} is blocked")


def _written(address: str) -> str:
    """How an address is written inside a URL."""
    return f"[{address}]" if ":" in address else address


def _scripted(response: HttpResponseInterface) -> MockResponse:
    """The scripted answer behind the interface, which knows what was asked of it."""
    assert isinstance(response, MockResponse)

    return response


# Every case of the reference suite that this client's configuration can
# express: an address, the networks refused, and whether reaching it is.
_REFUSALS = [
    ("0.0.0.1", None, True),
    ("169.254.0.1", None, True),
    ("127.0.0.1", None, True),
    ("240.0.0.1", None, True),
    ("10.0.0.1", None, True),
    ("172.16.0.1", None, True),
    ("192.168.0.1", None, True),
    ("::1", None, True),
    ("::ffff:0.0.0.1", None, True),
    ("fe80::1", None, True),
    ("fc00::1", None, True),
    ("fd00::1", None, True),
    ("10.0.0.1", "10.0.0.0/24", True),
    ("10.0.0.1", "10.0.0.1", True),
    ("fc00::1", "fc00::1/120", True),
    ("fc00::1", "fc00::1", True),
    ("172.16.0.1", ["10.0.0.0/8", "192.168.0.0/16"], False),
    ("fc00::1", ["fe80::/10", "::ffff:0:0/96"], False),
    ("104.26.14.6", None, False),
    ("104.26.14.6", "104.26.14.0/24", True),
    ("2606:4700:20::681a:e06", None, False),
    ("2606:4700:20::681a:e06", "2606:4700:20::/43", True),
    ("2606:4700:20::681a:e06", "::/0", True),
    ("104.26.14.6", "0.0.0.0/0", True),
]

_ALLOW_LIST = [
    ("10.0.0.1", None, "10.0.0.1", False),
    ("10.0.0.42", None, "10.0.0.0/24", False),
    ("10.0.0.1", None, ["10.0.0.1"], False),
    ("fc00::1", None, "fc00::1", False),
    ("fc00::1", None, "fc00::/7", False),
    ("10.0.0.1", None, "192.168.0.0/24", True),
    ("fc00::1", None, "fd00::/8", True),
    ("10.0.0.1", "10.0.0.0/8", "10.0.0.1", False),
    ("104.26.14.6", None, "10.0.0.0/8", False),
]


@pytest.mark.parametrize(("address", "subnets", "refused"), _REFUSALS)
async def test_an_address_written_out_is_checked_as_it_stands(
    address: str,
    subnets: str | Sequence[str] | None,
    refused: bool,
) -> None:
    url = f"http://{_written(address)}/"
    client = NoPrivateNetworkHttpClient(
        MockHttpClient(MockResponse(b"foo")),
        subnets,
        resolver=_never_resolves,
    )

    if refused:
        expected = re.escape(f'IP "{address}" is blocked for "{url}".')
        with pytest.raises(TransportError, match=f"^{expected}$"):
            _ = await client.request("GET", url)

        return

    async with _scripted(await client.request("GET", url)) as response:
        assert response.get_status_code() == 200
        assert await response.get_content() == b"foo"


@pytest.mark.parametrize(("address", "subnets", "refused"), _REFUSALS)
async def test_a_host_is_checked_by_what_it_resolves_to(
    address: str,
    subnets: str | Sequence[str] | None,
    refused: bool,
) -> None:
    url = "http://receiver.test/"
    client = NoPrivateNetworkHttpClient(
        MockHttpClient(MockResponse(b"foo")),
        subnets,
        resolver=_resolving_to(address),
    )

    if refused:
        expected = re.escape(f'Host "receiver.test" is blocked for "{url}".')
        with pytest.raises(TransportError, match=f"^{expected}$"):
            _ = await client.request("GET", url)

        return

    async with _scripted(await client.request("GET", url)) as response:
        assert response.get_status_code() == 200


@pytest.mark.parametrize(("address", "subnets", "allow_list", "refused"), _ALLOW_LIST)
async def test_the_allow_list_exempts_what_it_names(
    address: str,
    subnets: str | Sequence[str] | None,
    allow_list: str | Sequence[str],
    refused: bool,
) -> None:
    client = NoPrivateNetworkHttpClient(
        MockHttpClient(MockResponse(b"foo")),
        subnets,
        allow_list,
        resolver=_resolving_to(address),
    )

    if refused:
        with pytest.raises(TransportError, match=_blocked('Host "receiver.test"')):
            _ = await client.request("GET", "http://receiver.test/")

        return

    async with _scripted(await client.request("GET", "http://receiver.test/")) as response:
        assert response.get_status_code() == 200


async def test_one_refused_address_refuses_the_whole_request() -> None:
    client = NoPrivateNetworkHttpClient(
        MockHttpClient(MockResponse(b"foo")),
        resolver=_resolving_to("93.184.216.34", "10.0.0.5"),
    )

    with pytest.raises(TransportError, match=_blocked('Host "receiver.test"')):
        _ = await client.request("GET", "http://receiver.test/")


async def test_a_vetted_host_is_pinned_to_its_first_address() -> None:
    client = NoPrivateNetworkHttpClient(
        MockHttpClient(MockResponse(b"foo")),
        resolver=_resolving_to("93.184.216.34", "8.8.8.8"),
    )

    async with _scripted(await client.request("GET", "https://receiver.test/avatar")) as response:
        assert response.get_request_options()["resolve"] == {"receiver.test": "93.184.216.34"}


async def test_an_address_in_brackets_is_pinned_unbracketed() -> None:
    client = NoPrivateNetworkHttpClient(
        MockHttpClient(MockResponse(b"foo")),
        resolver=_resolving_to("2001:4860:4860::8888"),
    )

    async with _scripted(await client.request("GET", "https://receiver.test/")) as response:
        assert response.get_request_options()["resolve"] == {
            "receiver.test": "2001:4860:4860::8888"
        }


async def test_an_address_written_out_is_pinned_to_itself() -> None:
    client = NoPrivateNetworkHttpClient(
        MockHttpClient(MockResponse(b"foo")),
        resolver=_never_resolves,
    )

    answer = await client.request("GET", "http://[2001:4860:4860::8888]/")
    async with _scripted(answer) as response:
        assert response.get_request_options()["resolve"] == {
            "[2001:4860:4860::8888]": "2001:4860:4860::8888"
        }


async def test_an_address_is_named_in_the_refusal_in_the_form_it_was_checked_in() -> None:
    """An address has many spellings and one canonical form; the refusal names
    the address that was refused, not the spelling that reached it."""
    client = NoPrivateNetworkHttpClient(MockHttpClient(), resolver=_never_resolves)

    with pytest.raises(TransportError, match=_blocked('IP "::ffff:0.0.0.1"')):
        _ = await client.request("GET", "http://[::ffff:0:1]/")


async def test_a_resolve_option_the_caller_set_is_what_is_checked() -> None:
    client = NoPrivateNetworkHttpClient(
        MockHttpClient(MockResponse(b"foo")),
        resolver=_never_resolves,
    )

    with pytest.raises(TransportError, match=_blocked('Host "receiver.test"')):
        _ = await client.request(
            "GET",
            "http://receiver.test/",
            resolve={"receiver.test": "10.0.0.5"},
        )


async def test_a_resolve_entry_for_another_host_is_kept() -> None:
    client = NoPrivateNetworkHttpClient(
        MockHttpClient(MockResponse(b"foo")),
        resolver=_resolving_to("93.184.216.34"),
    )

    answer = await client.request(
        "GET",
        "http://receiver.test/",
        resolve={"other.test": "8.8.8.8"},
    )
    async with _scripted(answer) as response:
        assert response.get_request_options()["resolve"] == {
            "other.test": "8.8.8.8",
            "receiver.test": "93.184.216.34",
        }


async def test_a_host_with_no_address_at_all_is_refused() -> None:
    client = NoPrivateNetworkHttpClient(
        MockHttpClient(MockResponse(b"foo")),
        resolver=_resolving_to(),
    )

    with pytest.raises(TransportError, match="could not be resolved"):
        _ = await client.request("GET", "http://receiver.test/")


async def test_the_wrapped_client_is_never_asked_to_follow_a_redirect() -> None:
    client = NoPrivateNetworkHttpClient(
        MockHttpClient(MockResponse(b"foo")),
        resolver=_never_resolves,
    )

    answer = await client.request("GET", "http://104.26.14.6/", max_redirects=7)
    async with _scripted(answer) as response:
        assert response.get_request_options()["max_redirects"] == 0


async def test_each_hop_of_a_chain_is_checked() -> None:
    inner = MockHttpClient([_redirect("http://10.0.0.5/inside"), MockResponse(b"foo")])
    client = NoPrivateNetworkHttpClient(inner, resolver=_never_resolves)

    with pytest.raises(
        TransportError,
        match=re.escape('IP "10.0.0.5" is blocked for "http://10.0.0.5/inside".'),
    ):
        _ = await client.request("GET", "http://104.26.14.6/")


async def test_a_relative_location_is_resolved_against_the_hop_it_came_from() -> None:
    inner = MockHttpClient([_redirect("/moved"), MockResponse(b"foo")])
    client = NoPrivateNetworkHttpClient(inner, resolver=_never_resolves)

    async with _scripted(await client.request("GET", "http://104.26.14.6/start")) as response:
        assert response.get_request_url() == "http://104.26.14.6/moved"
        assert await response.get_content() == b"foo"


async def test_a_post_answered_with_a_found_goes_on_as_a_get_with_no_body() -> None:
    seen: list[tuple[str, Mapping[str, object]]] = []

    def answer(method: str, url: str, options: RequestOptions) -> MockResponse:
        del url
        seen.append((method, options))

        return MockResponse(b"foo")

    inner = MockHttpClient([_redirect("http://104.26.14.7/"), answer])
    client = NoPrivateNetworkHttpClient(inner, resolver=_never_resolves)

    last = await client.request(
        "POST",
        "http://104.26.14.6/",
        body=b"sent once",
        headers={"foo": "bar"},
    )
    async with _scripted(last) as response:
        assert await response.get_content() == b"foo"

    method, options = seen[0]

    assert method == "GET"
    assert options["body"] == b""
    assert options["headers"] == {"foo": "bar"}


async def test_a_see_other_turns_even_a_put_into_a_get() -> None:
    inner = MockHttpClient([_redirect("http://104.26.14.7/", 303), MockResponse(b"foo")])
    client = NoPrivateNetworkHttpClient(inner, resolver=_never_resolves)

    answer = await client.request("PUT", "http://104.26.14.6/", body=b"sent")
    async with _scripted(answer) as response:
        assert response.get_request_method() == "GET"


async def test_a_temporary_redirect_keeps_the_method_and_the_body() -> None:
    inner = MockHttpClient([_redirect("http://104.26.14.7/", 307), MockResponse(b"foo")])
    client = NoPrivateNetworkHttpClient(inner, resolver=_never_resolves)

    answer = await client.request("POST", "http://104.26.14.6/", body=b"sent")
    async with _scripted(answer) as response:
        assert response.get_request_method() == "POST"
        assert response.get_request_options()["body"] == b"sent"


async def test_a_chain_longer_than_asked_for_ends_on_the_redirect() -> None:
    inner = MockHttpClient([_redirect("http://104.26.14.7/"), MockResponse(b"foo")])
    client = NoPrivateNetworkHttpClient(inner, resolver=_never_resolves)

    answer = await client.request("GET", "http://104.26.14.6/", max_redirects=0)
    async with _scripted(answer) as response:
        assert response.get_status_code() == 302
        assert inner.get_requests_count() == 1


async def test_a_redirect_with_nowhere_to_go_is_the_answer() -> None:
    inner = MockHttpClient(MockResponse(b"", {"http_code": 302}))
    client = NoPrivateNetworkHttpClient(inner, resolver=_never_resolves)

    async with _scripted(await client.request("GET", "http://104.26.14.6/")) as response:
        assert response.get_status_code() == 302


async def test_what_a_host_resolves_to_is_asked_once() -> None:
    asked: list[str] = []

    async def resolve(host: str, port: int) -> Sequence[str]:
        del port
        asked.append(host)

        return ["93.184.216.34"]

    client = NoPrivateNetworkHttpClient(
        MockHttpClient([MockResponse(b"one"), MockResponse(b"two")]),
        resolver=resolve,
    )

    async with await client.request("GET", "http://receiver.test/a"):
        pass
    async with await client.request("GET", "http://receiver.test/b"):
        pass

    assert asked == ["receiver.test"]


async def test_reset_forgets_what_every_host_resolved_to() -> None:
    asked: list[str] = []

    async def resolve(host: str, port: int) -> Sequence[str]:
        del port
        asked.append(host)

        return ["93.184.216.34"]

    inner = MockHttpClient([MockResponse(b"one"), MockResponse(b"two")])
    client = NoPrivateNetworkHttpClient(inner, resolver=resolve)

    async with await client.request("GET", "http://receiver.test/a"):
        pass
    await client.reset()
    async with await client.request("GET", "http://receiver.test/b"):
        pass

    assert asked == ["receiver.test", "receiver.test"]


async def test_reset_resets_the_wrapped_client_too() -> None:
    inner = MockHttpClient(MockResponse(b"foo"))
    client = NoPrivateNetworkHttpClient(inner, resolver=_never_resolves)

    async with await client.request("GET", "http://104.26.14.6/"):
        pass
    await client.reset()

    assert inner.get_requests_count() == 0


async def test_a_url_naming_no_host_is_refused() -> None:
    client = NoPrivateNetworkHttpClient(MockHttpClient(), resolver=_never_resolves)

    with pytest.raises(InvalidArgumentError, match="it names no host"):
        _ = await client.request("GET", "/avatar")


async def test_a_relative_url_resolves_against_the_base_uri() -> None:
    client = NoPrivateNetworkHttpClient(
        MockHttpClient(MockResponse(b"foo")),
        resolver=_never_resolves,
    )

    answer = await client.request("GET", "/avatar", base_uri="http://104.26.14.6/")
    async with _scripted(answer) as response:
        assert response.get_request_url() == "http://104.26.14.6/avatar"


async def test_send_request_takes_the_same_path_as_request() -> None:
    client = NoPrivateNetworkHttpClient(
        MockHttpClient(MockResponse(b"foo")),
        resolver=_resolving_to("10.0.0.5"),
    )

    with pytest.raises(TransportError, match=_blocked('Host "receiver.test"')):
        _ = await client.send_request(Request("GET", "http://receiver.test/"))


async def test_with_options_wraps_a_narrowed_client_and_keeps_the_guard() -> None:
    client = NoPrivateNetworkHttpClient(
        MockHttpClient([MockResponse(b"foo"), MockResponse(b"foo")]),
        "104.26.14.0/24",
        "104.26.14.6",
        _never_resolves,
    )

    narrowed = client.with_options(auth_bearer="t0ken")

    async with _scripted(await narrowed.request("GET", "http://104.26.14.6/")) as response:
        assert response.get_request_options()["auth_bearer"] == "t0ken"

    with pytest.raises(TransportError, match=_blocked('IP "104.26.14.7"')):
        _ = await narrowed.request("GET", "http://104.26.14.7/")


async def test_with_options_shares_the_address_cache_with_the_original() -> None:
    asked: list[str] = []

    async def resolve(host: str, port: int) -> Sequence[str]:
        del port
        asked.append(host)

        return ["93.184.216.34"]

    inner = MockHttpClient([MockResponse(b"one"), MockResponse(b"two")])
    client = NoPrivateNetworkHttpClient(inner, resolver=resolve)
    narrowed = client.with_options(auth_bearer="t0ken")

    async with await client.request("GET", "http://receiver.test/a"):
        pass
    async with await narrowed.request("GET", "http://receiver.test/b"):
        pass

    assert asked == ["receiver.test"]
