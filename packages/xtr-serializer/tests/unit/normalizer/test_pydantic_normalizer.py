"""Values to plain data and back through pydantic, exactly, with errors that never quote data."""

from __future__ import annotations

import math
import random
import re
import sys
import threading
import traceback
from collections import Counter, OrderedDict, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Address,
    IPv6Interface,
    IPv6Network,
)
from types import SimpleNamespace
from typing import TYPE_CHECKING, Annotated, cast
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from pydantic import (
    VERSION,
    BaseModel,
    EmailStr,
    Field,
    ImportString,
    NameEmail,
    TypeAdapter,
    field_validator,
)
from pydantic_core import to_json
from typing_extensions import override
from xtr_clock import DatePoint

from tests.fixtures.colliding_key import CollidingKey
from tests.fixtures.containers import (
    Cabinet,
    Counts,
    Envelope,
    Folder,
    Grouped,
    Levelled,
    Ordered,
    Paired,
    Queued,
    Signed,
    Tallied,
)
from tests.fixtures.exact_values import (
    Amount,
    Appointment,
    Booking,
    Color,
    Count,
    Either,
    Extended,
    ExtendedParcel,
    Filed,
    Ledger,
    Level,
    Local,
    Loose,
    Measured,
    Meeting,
    Note,
    Proportion,
    Ratio,
    Refusing,
    Scoped,
    Series,
    Shape,
    Stamp,
    Tally,
    Visit,
)
from tests.fixtures.nameless import NamelessCount, NamelessThing, names_refused
from tests.fixtures.orders import (
    Cart,
    CartItem,
    CheckedSlot,
    ClosedParcel,
    Customer,
    Dispatch,
    Handover,
    Invoice,
    Item,
    LaxItem,
    Letter,
    Node,
    Order,
    Packet,
    Parcel,
    Receipt,
    Shipment,
    Slot,
    Status,
    StrictCart,
    TaggedSlot,
    Ticket,
)
from tests.fixtures.refused_types import (
    REFUSED_TYPES,
    TYPE_CODE_RAISED,
    Clash,
    Disguised,
    OtherClash,
    Refused,
    Sealed,
    Unhashable,
    Unhashed,
    Unprintable,
    Unshown,
    optionals,
)
from xtr_serializer import _type_cache as type_cache
from xtr_serializer.encoder.json_encoder import JsonEncoder
from xtr_serializer.exception import (
    CircularReferenceError,
    ExtraAttributesError,
    InvalidArgumentError,
    LogicError,
    NotNormalizableValueError,
    PartialDenormalizationError,
    UnexpectedValueError,
)
from xtr_serializer.normalizer import (
    ALLOW_EXTRA_ATTRIBUTES,
    ATTRIBUTES,
    BY_ALIAS,
    COLLECT_DENORMALIZATION_ERRORS,
    FROM_ATTRIBUTES,
    IGNORED_ATTRIBUTES,
    POPULATE_BY_NAME,
    SKIP_DEFAULT_VALUES,
    SKIP_NULL_VALUES,
    SKIP_UNSET_VALUES,
    STRICT,
    DenormalizerInterface,
    NormalizerInterface,
)
from xtr_serializer.normalizer import _adapter_cache as adapter_cache
from xtr_serializer.normalizer.pydantic_normalizer import PydanticNormalizer

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from xtr_serializer.context.context import Context

PLANTED_VALUE = "s3cr3t-t0ken-4f9a"
CYCLE = "Circular reference detected (id repeated)"
TOO_DEEP = "Circular reference detected (depth exceeded)"


class Opaque:
    """A class pydantic has no schema for."""


class Trap(dict[str, object]):
    """A dict whose lookups raise, as code the data carries may."""

    @override
    def __contains__(self, key: object) -> bool:
        raise RuntimeError(PLANTED_VALUE)

    @override
    def __getitem__(self, key: str) -> object:
        raise RuntimeError(PLANTED_VALUE)


class Row:
    """An object whose ``method`` can be read once, as a stream or a lazy load may."""

    def __init__(self) -> None:
        self.reads: int = 0

    @property
    def method(self) -> object:
        self.reads += 1
        if self.reads > 1:
            raise RuntimeError(PLANTED_VALUE)
        return SimpleNamespace(kind="pickup", store=1)


class Values(list[object]):
    """A list subclass, which reading from attributes takes as the list it is."""


def chain_of_nodes(depth: int) -> Node:
    root = node = Node()
    for _ in range(depth):
        node.children.append(child := Node())
        node = child
    return root


def nested_lists(depth: int) -> list[object]:
    root: list[object] = []
    inner = root
    for _ in range(depth):
        deeper: list[object] = []
        inner.append(deeper)
        inner = deeper
    return root


def looped_node() -> Node:
    node = Node()
    node.children.append(node)
    return node


def looped_list() -> list[object]:
    looped: list[object] = []
    looped.append(looped)
    return looped


ORDER = Order(
    id=UUID("6f1c2b8e-3d4a-4e5f-9a0b-1c2d3e4f5a6b"),
    placed_at=datetime(2026, 3, 29, 1, 30, 15, 123456, tzinfo=timezone(timedelta(hours=3))),
    total=Decimal("1234.50"),
    status=Status.SHIPPED,
    signature=b"\x00\xff\x10binary",
    dimensions=(30, 20, 10),
    tags=frozenset({"fragile", "gift"}),
    items=[Item(sku="A-1", price=100), Item(sku="B-2", price=250)],
)

SHIPMENT = Shipment(
    id=UUID("0b9c8d7e-6f5a-4b3c-8d2e-1f0a9b8c7d6e"),
    sent_on=date(2026, 2, 28),
    sent_at=datetime(2026, 2, 28, 23, 59, 59, tzinfo=UTC),
    transit=timedelta(days=2, hours=3, microseconds=7),
    weight=Decimal("0.010"),
    status=Status.OPEN,
    label=b"\xfe\xed",
    route=("IAS", "OTP", "BUD"),
    zones=frozenset({1, 7}),
)

RECEIPT = Receipt(number=42, issued_at=datetime(2026, 1, 1, tzinfo=UTC), seal=b"\x80\x81")


def round_trip(
    value: object, type_: object, normalizer: PydanticNormalizer | None = None
) -> object:
    normalizer = normalizer or PydanticNormalizer()
    encoder = JsonEncoder()
    data = encoder.decode(encoder.encode(normalizer.normalize(value), "json"), "json")
    return normalizer.denormalize(data, type_)


def test_it_is_a_normalizer_and_a_denormalizer() -> None:
    normalizer = PydanticNormalizer()

    assert isinstance(normalizer, NormalizerInterface)
    assert isinstance(normalizer, DenormalizerInterface)


@pytest.mark.parametrize(
    ("value", "type_"),
    [
        (ORDER, Order),
        (SHIPMENT, Shipment),
        (Filed(RECEIPT), Filed),
        (Status.SHIPPED, Status),
        ([1, "two", None], list[object]),
    ],
    ids=["model", "dataclass", "typed-dict", "enum", "list-of-plain-values"],
)
def test_a_value_reads_back_equal_through_json(value: object, type_: object) -> None:
    assert round_trip(value, type_) == value


def test_a_value_reads_back_with_the_exact_types_of_its_parts() -> None:
    read = round_trip(SHIPMENT, Shipment)

    assert isinstance(read, Shipment)
    assert type(read.route) is tuple
    assert type(read.zones) is frozenset
    assert type(read.weight) is Decimal
    assert read.status is Status.OPEN


def test_an_enum_of_dict_members_reads_back_as_the_member() -> None:
    normalizer = PydanticNormalizer()

    assert normalizer.supports_normalization(Shape.SQUARE)
    assert round_trip(Shape.SQUARE, Shape, normalizer) is Shape.SQUARE


def test_an_enum_of_tuple_members_is_refused_as_pydantic_reads_none_back_from_a_list() -> None:
    normalizer = PydanticNormalizer()

    assert normalizer.supports_normalization(Color.RED)
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = normalizer.normalize(Color.RED)

    assert (raised.value.error_type, raised.value.path) == ("enum", None)


def test_it_writes_plain_data() -> None:
    assert PydanticNormalizer().normalize(Item(sku="A-1", price=100)) == {
        "sku": "A-1",
        "price": 100,
    }


def test_it_writes_bytes_as_base64_and_durations_in_iso_8601() -> None:
    data = PydanticNormalizer().normalize(SHIPMENT)

    assert isinstance(data, dict)
    assert data["label"] == "_u0="
    assert data["transit"] == "P2DT3H0.000007S"


def test_it_supports_what_pydantic_can_build_a_schema_for() -> None:
    normalizer = PydanticNormalizer()

    assert normalizer.supports_normalization(ORDER)
    assert normalizer.supports_denormalization({}, list[Item])
    assert not normalizer.supports_normalization(Opaque())
    assert not normalizer.supports_denormalization({}, Opaque)


@pytest.fixture
def built(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Record every type an adapter is built for."""
    types: list[object] = []
    build = adapter_cache.build_adapter

    def counting_build(type_: object) -> adapter_cache.Adapter | str:
        types.append(type_)
        return build(type_)

    monkeypatch.setattr(adapter_cache, "build_adapter", counting_build)
    return types


def test_it_builds_the_adapter_of_a_type_once(built: list[object]) -> None:
    normalizer = PydanticNormalizer()

    for _ in range(3):
        _ = normalizer.normalize(Item(sku="A-1", price=1))
        _ = normalizer.denormalize({"sku": "A-1", "price": 1}, Item)

    assert built == [Item]


def test_it_remembers_a_type_it_cannot_build(built: list[object]) -> None:
    normalizer = PydanticNormalizer()

    assert not normalizer.supports_normalization(Opaque())
    assert not normalizer.supports_normalization(Opaque())
    assert built == [Opaque]


def test_it_reads_a_type_expression_that_cannot_be_hashed(built: list[object]) -> None:
    unhashable = Annotated[list[int], {"unhashable": True}]
    normalizer = PydanticNormalizer()

    assert normalizer.denormalize([1, 2], unhashable) == [1, 2]
    assert normalizer.denormalize([3], unhashable) == [3]
    assert len(built) == 2


def test_it_takes_the_members_of_a_union_in_the_order_written() -> None:
    normalizer = PydanticNormalizer()

    assert type(normalizer.denormalize({"weight": 1}, Letter | Packet)) is Letter
    assert type(normalizer.denormalize({"weight": 1}, Packet | Letter)) is Packet
    assert normalizer.denormalize([{"weight": 1}], list[Packet | Letter]) == [Packet(weight=1)]


def test_it_forgets_the_adapter_used_least_recently(
    built: list[object], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(type_cache, "_CACHE_SIZE", 2)
    normalizer = PydanticNormalizer()

    for type_ in (int, str, int, float, int, str):
        assert normalizer.supports_denormalization(None, type_)

    assert built == [int, str, float, str]


@pytest.fixture
def switching_often() -> Iterator[None]:
    """Have the interpreter switch threads as often as it can, so that a race shows at once."""
    interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    yield
    sys.setswitchinterval(interval)


THREADS = 16


@pytest.mark.usefixtures("switching_often")
def test_one_normalizer_reads_in_many_threads_at_once() -> None:
    # More types than the normalizer keeps the adapters of, so the threads keep evicting one
    # another's; each type reads one number only, so an adapter of another type would refuse it.
    types = [Annotated[int, Field(ge=number, le=number)] for number in range(600)]
    normalizer = PydanticNormalizer()
    start = threading.Barrier(THREADS)

    def read_numbers(seed: int) -> tuple[list[int], list[object]]:
        chooser = random.Random(seed)  # noqa: S311 - picks the types to read, guards nothing
        numbers = [chooser.randrange(len(types)) for _ in range(100)]
        _ = start.wait()
        return numbers, [normalizer.denormalize(number, types[number]) for number in numbers]

    with ThreadPoolExecutor(THREADS) as pool:
        results = list(pool.map(read_numbers, range(THREADS)))

    assert all(read == numbers for numbers, read in results)


def test_it_refuses_to_normalize_what_it_cannot_build() -> None:
    with pytest.raises(InvalidArgumentError, match="'Opaque'"):
        _ = PydanticNormalizer().normalize(Opaque())


def test_it_refuses_to_denormalize_into_what_it_cannot_build() -> None:
    with pytest.raises(InvalidArgumentError, match="'Opaque'"):
        _ = PydanticNormalizer().denormalize({}, Opaque)


MISDECLARED = Annotated[int, Field(discriminator="kind")]


def test_it_does_not_support_a_type_pydantic_cannot_build_a_schema_for() -> None:
    normalizer = PydanticNormalizer()

    assert not normalizer.supports_denormalization({}, MISDECLARED)
    with pytest.raises(InvalidArgumentError, match="cannot build a schema"):
        _ = normalizer.denormalize({}, MISDECLARED)


@pytest.mark.parametrize("type_", REFUSED_TYPES.values(), ids=REFUSED_TYPES.keys())
def test_it_refuses_to_denormalize_into_any_type_pydantic_refuses_to_build(type_: object) -> None:
    normalizer = PydanticNormalizer()

    assert not normalizer.supports_denormalization({}, type_)
    with pytest.raises(InvalidArgumentError, match="cannot build a schema for"):
        _ = normalizer.denormalize({}, type_)


def test_it_names_the_type_it_refuses_to_normalize_when_pydantic_refuses_to_build_it() -> None:
    normalizer = PydanticNormalizer()

    assert not normalizer.supports_normalization(Refused())
    with pytest.raises(InvalidArgumentError, match="cannot build a schema for 'Refused'"):
        _ = normalizer.normalize(Refused())


def test_it_refuses_to_normalize_a_value_whose_class_raises_as_it_is_built() -> None:
    normalizer = PydanticNormalizer()

    assert not normalizer.supports_normalization(Unshown())
    with pytest.raises(InvalidArgumentError, match=r"'Unshown': building it raised LookupError$"):
        _ = normalizer.normalize(Unshown())


def test_it_refuses_to_denormalize_into_what_raises_as_it_is_built() -> None:
    normalizer = PydanticNormalizer()

    assert not normalizer.supports_denormalization({}, Unprintable())
    with pytest.raises(InvalidArgumentError, match=r"building it raised LookupError$"):
        _ = normalizer.denormalize({}, Unprintable())


def test_it_refuses_a_type_equal_to_a_kept_one_too_deep_to_compare_every_time() -> None:
    normalizer = PydanticNormalizer()

    assert not normalizer.supports_denormalization(None, optionals(202))
    assert not normalizer.supports_denormalization(None, optionals(202))


def assert_refused_quietly(refusal: InvalidArgumentError) -> None:
    """Check a refusal neither quotes what the type's own code raised nor chains it."""
    assert TYPE_CODE_RAISED not in "".join(traceback.format_exception(refusal))
    assert refusal.__cause__ is None
    assert refusal.__context__ is None


# Each wrapped in a parameter set: pytest asks a bare value whether it is one, which runs its code.
HOSTILE_TYPES = [
    pytest.param(Sealed, id="sealed"),
    pytest.param(Unhashed, id="unhashed-class"),
    pytest.param(list[Unhashed], id="unhashed-class-in-a-list"),
    pytest.param(Unhashable(), id="unhashable"),
    pytest.param(list.__class_getitem__(Unhashable()), id="unhashable-in-a-list"),
    pytest.param(Disguised(), id="disguised"),
]


@pytest.mark.parametrize("type_", HOSTILE_TYPES)
def test_it_does_not_support_a_type_whose_own_code_raises_as_it_is_keyed(type_: object) -> None:
    assert not PydanticNormalizer().supports_denormalization({}, type_)


@pytest.mark.parametrize("type_", HOSTILE_TYPES)
def test_it_refuses_to_denormalize_into_a_type_whose_own_code_raises_as_it_is_keyed(
    type_: object,
) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = PydanticNormalizer().denormalize({}, type_)

    assert_refused_quietly(raised.value)


HOSTILE_VALUES = [
    pytest.param(Sealed(), id="sealed"),
    pytest.param(Unhashed(), id="unhashed"),
    pytest.param(Disguised(), id="disguised"),
]


@pytest.mark.parametrize("value", HOSTILE_VALUES)
def test_it_does_not_support_a_value_whose_class_raises_as_it_is_keyed(value: object) -> None:
    assert not PydanticNormalizer().supports_normalization(value)


@pytest.mark.parametrize("value", HOSTILE_VALUES)
def test_it_refuses_to_normalize_a_value_whose_class_raises_as_it_is_keyed(value: object) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = PydanticNormalizer().normalize(value)

    assert_refused_quietly(raised.value)


def test_it_does_not_support_a_type_refusing_to_compare_with_a_kept_one_hashed_alike() -> None:
    normalizer = PydanticNormalizer()
    _ = normalizer.supports_denormalization({}, Clash)

    assert not normalizer.supports_denormalization({}, OtherClash)


def test_it_refuses_to_denormalize_into_a_type_refusing_to_compare_with_a_kept_one() -> None:
    normalizer = PydanticNormalizer()
    _ = normalizer.supports_denormalization({}, Clash)

    with pytest.raises(InvalidArgumentError) as raised:
        _ = normalizer.denormalize({}, OtherClash)

    assert_refused_quietly(raised.value)


def test_it_refuses_to_normalize_a_value_whose_class_refuses_to_compare_with_a_kept_one() -> None:
    normalizer = PydanticNormalizer()
    _ = normalizer.supports_normalization(Clash())

    with pytest.raises(InvalidArgumentError) as raised:
        _ = normalizer.normalize(OtherClash())

    assert_refused_quietly(raised.value)


def test_it_names_a_value_it_cannot_write_without_running_its_metaclass() -> None:
    normalizer = PydanticNormalizer()
    value = NamelessCount(cast("int", cast("object", "one")))
    assert normalizer.supports_normalization(value)

    with names_refused(), pytest.raises(NotNormalizableValueError) as raised:
        _ = normalizer.normalize(value)

    assert raised.value.current_type == "NamelessCount"


def test_it_names_data_it_cannot_read_without_running_its_metaclass() -> None:
    with names_refused(), pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().denormalize(NamelessThing(), int)

    assert raised.value.current_type == "NamelessThing"


def test_it_refuses_to_read_into_a_type_it_cannot_resolve_naming_what_is_undefined() -> None:
    with pytest.raises(InvalidArgumentError, match=r"'Invoice'.*'Mapping' is not defined"):
        _ = PydanticNormalizer().denormalize({"lines": {}}, Invoice)


def test_it_refuses_to_write_a_value_whose_type_it_cannot_resolve() -> None:
    with pytest.raises(InvalidArgumentError, match="'Mapping' is not defined"):
        _ = PydanticNormalizer().normalize(Invoice.model_construct(lines={}))


def test_it_does_not_support_a_type_it_cannot_resolve(built: list[object]) -> None:
    normalizer = PydanticNormalizer()

    assert not normalizer.supports_denormalization({}, Invoice)
    assert not normalizer.supports_normalization(Invoice.model_construct(lines={}))
    assert built == [Invoice]


def test_it_handles_every_type_and_its_answer_rests_on_the_type_alone() -> None:
    assert PydanticNormalizer().get_supported_types("json") == {"*": True}
    assert PydanticNormalizer().get_supported_types(None) == {"*": True}


# Writing options.


def test_it_writes_only_the_attributes_asked_for() -> None:
    data = PydanticNormalizer().normalize(Item(sku="A-1", price=1), context={ATTRIBUTES: {"sku"}})

    assert data == {"sku": "A-1"}


def test_it_leaves_out_the_ignored_attributes() -> None:
    context: Context = {IGNORED_ATTRIBUTES: frozenset({"price"})}

    assert PydanticNormalizer().normalize(Item(sku="A-1", price=1), context=context) == {
        "sku": "A-1"
    }


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (SKIP_NULL_VALUES, {"fullName": "Ada", "country": "RO"}),
        (SKIP_UNSET_VALUES, {"fullName": "Ada", "nickname": None}),
        (SKIP_DEFAULT_VALUES, {"fullName": "Ada"}),
    ],
)
def test_it_leaves_out_the_values_it_is_asked_to_skip(key: str, expected: object) -> None:
    customer = Customer(fullName="Ada", nickname=None)

    assert PydanticNormalizer().normalize(customer, context={key: True}) == expected


def test_it_writes_every_value_by_default() -> None:
    data = PydanticNormalizer().normalize(Customer(fullName="Ada"))

    assert data == {"fullName": "Ada", "nickname": None, "country": "RO"}


def test_it_writes_under_the_name_when_aliases_are_off() -> None:
    data = PydanticNormalizer().normalize(Customer(fullName="Ada"), context={BY_ALIAS: False})

    assert data == {"full_name": "Ada", "nickname": None, "country": "RO"}


def test_the_call_context_wins_over_the_default_context() -> None:
    normalizer = PydanticNormalizer({ATTRIBUTES: {"sku"}, BY_ALIAS: False})

    assert normalizer.normalize(Customer(fullName="Ada"), context={ATTRIBUTES: {"full_name"}}) == {
        "full_name": "Ada"
    }


def test_a_default_context_changed_afterwards_does_not_reach_it() -> None:
    default: dict[str, object] = {}
    normalizer = PydanticNormalizer(default)
    default[ATTRIBUTES] = {"sku"}

    assert normalizer.normalize(Item(sku="A-1", price=1)) == {"sku": "A-1", "price": 1}


def test_it_hands_the_context_to_the_type_validators() -> None:
    ticket = PydanticNormalizer().denormalize({"code": "7"}, Ticket, context={"prefix": "T-"})

    assert ticket == Ticket(code="T-7")


# Reading options.


def test_it_reads_under_the_alias() -> None:
    assert PydanticNormalizer().denormalize({"fullName": "Ada"}, Customer) == Customer(
        fullName="Ada"
    )


def test_it_refuses_the_name_of_an_aliased_field_by_default() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().denormalize({"full_name": "Ada"}, Customer)

    assert raised.value.path == "fullName"
    assert raised.value.error_type == "missing"
    assert raised.value.current_type is None


def test_it_reads_under_the_name_when_aliases_are_off() -> None:
    customer = PydanticNormalizer().denormalize(
        {"full_name": "Ada"}, Customer, context={BY_ALIAS: False}
    )

    assert customer == Customer(fullName="Ada")


def test_it_reads_under_the_name_as_well_when_asked() -> None:
    normalizer = PydanticNormalizer({POPULATE_BY_NAME: True})

    assert normalizer.denormalize({"full_name": "Ada"}, Customer) == Customer(fullName="Ada")
    assert normalizer.denormalize({"fullName": "Ada"}, Customer) == Customer(fullName="Ada")


def test_a_model_configuration_governs_its_strictness_when_the_context_is_silent() -> None:
    assert PydanticNormalizer().denormalize({"sku": "A", "price": "1"}, LaxItem) == LaxItem(
        sku="A", price=1
    )


def test_strict_reading_refuses_data_that_only_converts() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().denormalize(
            {"sku": "A", "price": "1"}, LaxItem, context={STRICT: True}
        )

    assert raised.value.path == "price"


def test_strict_off_converts_for_a_type_with_no_configuration_of_its_own() -> None:
    data = {"number": "42", "issued_at": "2026-01-01T00:00:00Z", "seal": "gIE="}

    assert PydanticNormalizer().denormalize(data, Receipt, context={STRICT: False}) == RECEIPT


def test_a_type_with_no_configuration_of_its_own_is_read_strictly() -> None:
    data = {"number": "42", "issued_at": "2026-01-01T00:00:00Z", "seal": "gIE="}

    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().denormalize(data, Receipt)

    assert raised.value.path == "number"
    assert raised.value.error_type == "int_type"


def test_it_refuses_a_float_json_has_no_form_for() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().denormalize(math.nan, float)

    assert raised.value.error_type == "finite_number"


def test_it_drops_extra_attributes_when_allowed() -> None:
    cart = PydanticNormalizer().denormalize(
        {"owner": "Ada", "coupon": "X"}, StrictCart, context={ALLOW_EXTRA_ATTRIBUTES: True}
    )

    assert cart == StrictCart(owner="Ada")


def test_a_model_configuration_governs_extra_attributes_when_the_context_is_silent() -> None:
    assert PydanticNormalizer().denormalize({"sku": "A", "price": 1, "x": 0}, CartItem) == CartItem(
        sku="A", price=1
    )


def test_it_refuses_extra_attributes_when_asked_naming_them() -> None:
    with pytest.raises(ExtraAttributesError) as raised:
        _ = PydanticNormalizer().denormalize(
            {"sku": "A", "price": 1, "coupon": PLANTED_VALUE, "note": PLANTED_VALUE},
            CartItem,
            context={ALLOW_EXTRA_ATTRIBUTES: False},
        )

    assert raised.value.extra_attributes == ("coupon", "note")
    assert raised.value.path is None
    assert raised.value.error_type == "extra_forbidden"
    assert PLANTED_VALUE not in str(raised.value)


def test_it_locates_extra_attributes_inside_the_data() -> None:
    with pytest.raises(ExtraAttributesError) as raised:
        _ = PydanticNormalizer().denormalize(
            {"items": [{"sku": "A", "price": 1, "coupon": "X"}]}, Cart
        )

    assert raised.value.path == "items[0]"
    assert raised.value.extra_attributes == ("coupon",)


@pytest.mark.parametrize(
    ("type_", "context"),
    [(Parcel, {ALLOW_EXTRA_ATTRIBUTES: False}), (ClosedParcel, {})],
    ids=["refused-by-the-context", "refused-by-its-configuration"],
)
def test_it_refuses_the_extra_attributes_of_a_dataclass_as_one_error(
    type_: object, context: Context
) -> None:
    data = {"weight": 1, "a": PLANTED_VALUE, "b": PLANTED_VALUE}

    with pytest.raises(PartialDenormalizationError) as raised:
        _ = PydanticNormalizer().denormalize(
            data, type_, context={**context, COLLECT_DENORMALIZATION_ERRORS: True}
        )

    [error] = raised.value.errors
    assert isinstance(error, ExtraAttributesError)
    assert error.extra_attributes == ("a", "b")
    assert error.path is None


def test_it_reads_from_the_attributes_of_an_object_when_asked() -> None:
    row = CartItem(sku="A", price=1)

    item = PydanticNormalizer().denormalize(row, LaxItem, context={FROM_ATTRIBUTES: True})

    assert item == LaxItem(sku="A", price=1)


@pytest.mark.parametrize(
    "key",
    [
        BY_ALIAS,
        STRICT,
        ALLOW_EXTRA_ATTRIBUTES,
        FROM_ATTRIBUTES,
        POPULATE_BY_NAME,
        COLLECT_DENORMALIZATION_ERRORS,
    ],
)
def test_it_refuses_a_reading_option_that_is_not_a_bool(key: str) -> None:
    with pytest.raises(InvalidArgumentError, match=repr(key)):
        _ = PydanticNormalizer().denormalize({"sku": "A", "price": 1}, Item, context={key: 1})


@pytest.mark.parametrize(
    "key", [BY_ALIAS, SKIP_NULL_VALUES, SKIP_UNSET_VALUES, SKIP_DEFAULT_VALUES]
)
def test_it_refuses_a_writing_option_that_is_not_a_bool(key: str) -> None:
    with pytest.raises(InvalidArgumentError, match=repr(key)):
        _ = PydanticNormalizer().normalize(Item(sku="A", price=1), context={key: "yes"})


@pytest.mark.parametrize("names", ["sku", ["sku"], {1}])
@pytest.mark.parametrize("key", [ATTRIBUTES, IGNORED_ATTRIBUTES])
def test_it_refuses_attribute_names_that_are_not_a_set_of_strings(key: str, names: object) -> None:
    with pytest.raises(InvalidArgumentError, match=repr(key)):
        _ = PydanticNormalizer().normalize(Item(sku="A", price=1), context={key: names})


# Errors.


def test_it_reports_the_first_value_that_does_not_fit_and_where() -> None:
    data = {"items": [{"sku": "A", "price": PLANTED_VALUE}, {"sku": "B", "price": "2"}]}

    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().denormalize(data, Cart)

    assert type(raised.value) is NotNormalizableValueError
    assert raised.value.path == "items[0].price"
    assert raised.value.error_type == "int_type"
    assert raised.value.current_type == "str"
    assert raised.value.message == "Input should be a valid integer"


def test_it_reports_every_value_that_does_not_fit_when_asked() -> None:
    data = {"items": [{"sku": "A", "price": "1"}, {"price": 2, "x": 0}]}

    with pytest.raises(PartialDenormalizationError) as raised:
        _ = PydanticNormalizer().denormalize(
            data, Cart, context={COLLECT_DENORMALIZATION_ERRORS: True}
        )

    assert raised.value.data is data
    # Each in the order pydantic finds them, which differs between its versions.
    assert {(type(error), error.path, error.error_type) for error in raised.value.errors} == {
        (NotNormalizableValueError, "items[0].price", "int_type"),
        (ExtraAttributesError, "items[1]", "extra_forbidden"),
        (NotNormalizableValueError, "items[1].sku", "missing"),
    }
    assert len(raised.value.errors) == 3


def test_it_reports_a_value_that_does_not_fit_as_a_whole_without_a_path() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().denormalize("x", Item)

    assert raised.value.path is None
    assert raised.value.current_type == "str"


def test_it_locates_an_error_inside_a_union_where_the_data_has_it() -> None:
    with pytest.raises(PartialDenormalizationError) as raised:
        _ = PydanticNormalizer().denormalize(
            {"method": {"store": 1}}, Handover, context={COLLECT_DENORMALIZATION_ERRORS: True}
        )

    assert sorted(
        (str(error.path), str(error.error_type), str(error.current_type))
        for error in raised.value.errors
    ) == [
        ("method.address", "missing", "None"),
        ("method.kind", "missing", "None"),
        ("method.store", "string_type", "int"),
    ]


def test_it_locates_an_error_inside_a_tagged_union_without_the_tag() -> None:
    data = {"method": {"kind": "delivery", "address": 1}}

    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().denormalize(data, Dispatch)

    assert raised.value.path == "method.address"


def test_it_locates_an_error_inside_a_union_read_from_attributes() -> None:
    row = SimpleNamespace(method=SimpleNamespace(kind="pickup", store=1))

    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().denormalize(row, Handover, context={FROM_ATTRIBUTES: True})

    assert raised.value.path == "method.store"


def test_it_reports_a_refused_key_at_its_mapping_without_the_key() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().denormalize([{"x": 1}], list[dict[int, int]])

    assert raised.value.path == "[0]"
    assert raised.value.message.startswith("a key: ")


@pytest.mark.parametrize(
    "context", [{}, {FROM_ATTRIBUTES: True}], ids=["read-as-json", "read-from-attributes"]
)
def test_it_locates_an_error_without_running_the_lookups_of_the_data(context: Context) -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().denormalize(Trap(sku="A", price="1"), Item, context=context)

    assert raised.value.path == "price"
    assert raised.value.__context__ is None


def test_it_reads_an_attribute_of_refused_data_once() -> None:
    row = Row()

    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().denormalize(row, Dispatch, context={FROM_ATTRIBUTES: True})

    assert row.reads == 1
    assert raised.value.path == "method"
    assert raised.value.__context__ is None


@pytest.mark.parametrize(
    ("data", "type_", "paths"),
    [
        ((price for price in ("a", "b")), list[int], {"[0]", "[1]"}),
        (frozenset({"a", "b"}), frozenset[int], {"[0]", "[1]"}),
        ({1: "a", 2: "b"}, dict[int, int], {"1", "2"}),
    ],
    ids=["generator", "set", "integer-keys"],
)
def test_it_locates_each_error_where_the_data_read_as_json_has_it(
    data: object, type_: object, paths: set[str]
) -> None:
    with pytest.raises(PartialDenormalizationError) as raised:
        _ = PydanticNormalizer().denormalize(
            data, type_, context={COLLECT_DENORMALIZATION_ERRORS: True}
        )

    assert {error.path for error in raised.value.errors} == paths
    assert len(raised.value.errors) == 2


MANY = 10_000


def _refused_mapping(size: int) -> object:
    return {f"k{index}": "x" for index in range(size)}


def _refused_list(size: int) -> object:
    return Values(["x"] * size)


@pytest.mark.parametrize(
    ("build", "type_", "context"),
    [
        (_refused_mapping, dict[str, int], {}),
        (_refused_mapping, dict[str, int], {FROM_ATTRIBUTES: True}),
        (_refused_list, list[int], {FROM_ATTRIBUTES: True}),
    ],
    ids=["mapping-read-as-json", "mapping-read-from-attributes", "list-read-from-attributes"],
)
def test_it_locates_every_refused_value_of_a_large_container(
    build: Callable[[int], object], type_: object, context: Context
) -> None:
    """Every one is reported; that each mapping is indexed once is tested with the walk."""
    with pytest.raises(PartialDenormalizationError) as raised:
        _ = PydanticNormalizer().denormalize(
            build(MANY), type_, context={**context, COLLECT_DENORMALIZATION_ERRORS: True}
        )
    assert len(raised.value.errors) == MANY


@pytest.mark.parametrize(
    ("type_", "error_type", "message"),
    [
        (Slot, "value_error", "Value error, end must follow start"),
        (CheckedSlot, "assertion_error", "Assertion failed, end must follow start"),
        (TaggedSlot, "slot_order", "end must follow start"),
    ],
    ids=["value-error", "assertion", "custom-error"],
)
def test_the_words_of_a_validator_reach_its_refusal(
    type_: object, error_type: str, message: str
) -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().denormalize({"start": 2, "end": 1}, type_)

    assert (raised.value.error_type, raised.value.message) == (error_type, message)


def test_it_refuses_to_read_data_that_is_not_plain() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().denormalize({"sku": object(), "price": 1}, Item)

    assert raised.value.current_type == "dict"


def test_it_refuses_to_write_a_value_that_does_not_fit_its_declared_type() -> None:
    misfit = Item.model_construct(sku="A", price=PLANTED_VALUE)

    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().normalize(misfit)

    assert raised.value.current_type == "Item"
    assert PLANTED_VALUE not in "".join(traceback.format_exception(raised.value))


def test_it_refuses_to_write_a_value_that_contains_itself() -> None:
    with pytest.raises(CircularReferenceError):
        _ = PydanticNormalizer().normalize(looped_node())


def test_it_refuses_to_read_data_that_contains_itself() -> None:
    with pytest.raises(CircularReferenceError):
        _ = PydanticNormalizer().denormalize(looped_list(), list[object])


def test_it_refuses_to_write_a_value_too_deep_to_write_without_calling_it_circular() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().normalize(chain_of_nodes(1000))

    assert type(raised.value) is NotNormalizableValueError


def test_it_refuses_to_read_data_too_deep_to_read_without_calling_it_circular() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().denormalize(nested_lists(1000), list[object])

    assert type(raised.value) is NotNormalizableValueError


def test_it_refuses_data_too_deep_to_parse_back_as_a_whole() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().denormalize(nested_lists(250), list[object])

    assert (raised.value.error_type, raised.value.path) == ("json_invalid", None)
    assert raised.value.__context__ is None


def test_a_value_quoting_the_words_of_a_cycle_is_not_a_cycle() -> None:
    misfit = Item.model_construct(sku="A", price=CYCLE)

    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().normalize(misfit)

    assert type(raised.value) is NotNormalizableValueError


# Exact values: what would read back changed is refused when written.

BUCHAREST = ZoneInfo("Europe/Bucharest")
REPEATED_HOUR = datetime(2026, 10, 25, 3, 30, fold=1, tzinfo=BUCHAREST)


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("-Infinity"), Decimal("sNaN")])
def test_it_refuses_to_write_what_would_not_read_back_saying_where(value: Decimal) -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().normalize(Amount(value))

    assert raised.value.path == "value"
    assert raised.value.error_type == "finite_number"
    assert raised.value.message.startswith("it would not read back: ")


@pytest.mark.parametrize(
    ("value", "path", "current_type"),
    [
        (Loose(items=[], mapping={1: "one"}), "mapping", "dict"),
        (Loose(items=[{1, 2}], mapping={}), "items[0]", "set"),
        (Loose(items=[(1, 2)], mapping={}), "items[0]", "tuple"),
        (Loose(items=[Item(sku="A", price=1)], mapping={}), "items[0]", "Item"),
        (Series((1, 2)), "value", "tuple"),
        (Stamp(REPEATED_HOUR), "value", "datetime"),
        ([Item(sku="A", price=1)], "[0]", "Item"),
        (RECEIPT, "issued_at", "datetime"),
        (Count(True), "value", "bool"),
        (Count(Level.LOW), "value", "Level"),
        (Either(Level.LOW), "value", "Level"),
        (Paired(Levelled(Level.LOW)), "p.x", "Level"),
        (Queued(deque([Level.LOW])), "q[0]", "Level"),
        (Ordered(OrderedDict(a=Level.LOW)), "d.a", "Level"),
        (Grouped(defaultdict(list, a=[Level.LOW])), "d.a[0]", "Level"),
        (Tallied(Counter({"a": True})), "c.a", "bool"),
        (Counts(Counter({Level.LOW: 1})), "c", "Counter"),
        (
            Filed(Receipt(number=True, issued_at=RECEIPT["issued_at"], seal=RECEIPT["seal"])),
            "receipt.number",
            "bool",
        ),
        (Extended.model_validate({"price": 1, "level": Level.LOW}), "level", "Level"),
        (TypeAdapter(ExtendedParcel).validate_python({"weight": 1, "note": "a"}), "note", "str"),
    ],
    ids=[
        "int-key",
        "set-in-a-list",
        "tuple-in-a-list",
        "model-in-a-list",
        "tuple-as-a-sequence",
        "zone-in-the-repeated-hour",
        "list-of-models",
        "typed-dict-on-its-own",
        "bool-as-an-int",
        "enum-member-as-an-int",
        "enum-member-read-as-an-earlier-union-member",
        "enum-member-in-a-named-tuple",
        "enum-member-in-a-deque",
        "enum-member-in-an-ordered-dict",
        "enum-member-in-a-defaultdict",
        "bool-in-a-counter",
        "enum-member-as-a-counter-key",
        "bool-inside-a-typed-dict",
        "enum-member-as-an-extra-field",
        "extra-field-a-dataclass-does-not-write",
    ],
)
def test_it_refuses_to_write_what_would_read_back_changed_saying_where(
    value: object, path: str, current_type: str
) -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().normalize(value)

    assert raised.value.error_type == "not_exact"
    assert (raised.value.path, raised.value.current_type) == (path, current_type)


def test_a_value_that_does_not_compare_by_value_is_refused_without_a_path() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().normalize(Ledger(1))

    assert (raised.value.error_type, raised.value.path) == ("not_exact", None)


def test_the_extra_fields_of_a_model_read_back_with_it() -> None:
    value = Extended.model_validate({"price": 1, "note": "a", "tags": ["b"]})

    assert round_trip(value, Extended) == value


@pytest.mark.parametrize(
    ("context", "path"),
    [({}, "itemCount"), ({BY_ALIAS: False}, "item_count")],
    ids=["alias", "name"],
)
def test_what_would_read_back_changed_is_located_under_the_name_it_is_written_by(
    context: Context, path: str
) -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().normalize(Tally.model_construct(item_count=True), context=context)

    assert (raised.value.error_type, raised.value.path) == ("not_exact", path)


def test_it_refuses_to_write_a_naive_datetime_in_a_plain_datetime_field() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().normalize(Stamp(datetime(2026, 1, 1)))  # noqa: DTZ001 - the point

    assert (raised.value.path, raised.value.error_type) == ("value", "timezone_aware")


def test_it_refuses_to_read_a_naive_datetime_into_a_plain_datetime_field() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().denormalize({"value": "2026-01-01T00:00:00"}, Stamp)

    assert (raised.value.path, raised.value.error_type) == ("value", "timezone_aware")


def test_a_datetime_declared_naive_reads_back_naive() -> None:
    value = Local(datetime(2026, 1, 1))  # noqa: DTZ001 - declared naive

    assert round_trip(value, Local) == value


NAIVE = datetime(2026, 1, 1)  # noqa: DTZ001 - what a model's own rules let through


@pytest.mark.parametrize(
    ("value", "type_"),
    [
        (Appointment(at=NAIVE), Appointment),
        (Visit(at=NAIVE), Visit),
        (Booking(Appointment(at=NAIVE)), Booking),
    ],
    ids=["model", "pydantic-dataclass", "model-in-a-dataclass"],
)
def test_a_model_reads_its_plain_datetime_by_its_own_rules_wherever_it_sits(
    value: object, type_: object
) -> None:
    assert round_trip(value, type_) == value


# Before 2.14, pydantic writes the bytes in a named tuple inside a model by the configuration of
# the whole, as base64, and reads them by the model's.
BEFORE_PYDANTIC_2_14 = tuple(map(int, VERSION.split(".")[:2])) < (2, 14)


@pytest.mark.skipif(not BEFORE_PYDANTIC_2_14, reason="pydantic writes them as the model says")
def test_bytes_in_a_named_tuple_in_a_lax_model_are_refused_before_pydantic_2_14() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().normalize(Envelope(signed=Signed(b"abc")))

    assert (raised.value.error_type, raised.value.path) == ("not_exact", "signed.signature")


@pytest.mark.skipif(BEFORE_PYDANTIC_2_14, reason="pydantic writes them as base64")
def test_bytes_in_a_named_tuple_in_a_lax_model_read_back_from_pydantic_2_14() -> None:
    value = Envelope(signed=Signed(b"abc"))

    assert round_trip(value, Envelope) == value


# In a typed dict with a configuration of its own, pydantic writes and reads them so on 2.14 too.


def test_bytes_in_a_named_tuple_in_a_lax_typed_dict_are_refused() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().normalize(Cabinet(Folder(signed=Signed(b"abc"))))

    assert (raised.value.error_type, raised.value.path) == ("not_exact", "folder.signed.signature")


@pytest.mark.parametrize(
    "value",
    [
        datetime(9999, 12, 31, 23, tzinfo=ZoneInfo("America/New_York")),
        datetime(1, 1, 1, 0, 30, tzinfo=ZoneInfo("Asia/Tokyo")),
    ],
    ids=["last-year", "first-year"],
)
def test_it_refuses_a_zoned_time_whose_instant_no_datetime_holds(value: datetime) -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().normalize(Meeting(value))

    assert (raised.value.path, raised.value.error_type) == ("starts_at", "zoned_datetime")


def test_it_refuses_text_json_cannot_carry_without_quoting_it() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().normalize(Note(f"\ud800{PLANTED_VALUE}"))

    assert PLANTED_VALUE not in "".join(traceback.format_exception(raised.value))
    assert (raised.value.error_type, raised.value.path) == ("not_json", None)
    assert raised.value.__context__ is None


def test_it_says_when_a_validator_fails_only_as_the_value_is_read_back() -> None:
    value = Scoped.model_validate({"value": 1}, context={"tenant": "a"})

    with pytest.raises(NotNormalizableValueError, match=r"read back.*KeyError") as raised:
        _ = PydanticNormalizer().normalize(value)

    assert raised.value.__context__ is None


def test_it_reads_back_under_the_context_of_the_call() -> None:
    value = Scoped.model_validate({"value": 1}, context={"tenant": "a"})

    assert PydanticNormalizer().normalize(value, context={"tenant": "a"}) == {"value": 1}


def test_it_refuses_a_value_that_cannot_be_compared_with_what_it_reads_back_as() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().normalize(Measured(value=Decimal("sNaN")))

    assert (raised.value.path, raised.value.error_type) == ("value", "not_comparable")
    assert raised.value.__context__ is None


def test_a_zoned_datetime_field_reads_back_the_repeated_hour_in_its_zone() -> None:
    read = round_trip(Meeting(REPEATED_HOUR), Meeting)

    assert read == Meeting(REPEATED_HOUR)
    assert isinstance(read, Meeting)
    assert (read.starts_at.tzinfo, read.starts_at.fold) == (BUCHAREST, 1)


def test_a_plain_datetime_field_keeps_the_offset_of_a_zone_but_not_its_name() -> None:
    summer = datetime(2026, 7, 1, 12, tzinfo=BUCHAREST)

    read = round_trip(Stamp(summer), Stamp)

    assert isinstance(read, Stamp)
    assert read == Stamp(summer)
    assert read.value.utcoffset() == timedelta(hours=3)
    assert not isinstance(read.value.tzinfo, ZoneInfo)


@pytest.mark.parametrize(
    ("value", "type_", "declared"),
    [
        (Stamp(DatePoint(2026, 3, 1, 9, tzinfo=UTC)), Stamp, datetime),
        (Stamp(DatePoint(2026, 3, 1, 9, tzinfo=BUCHAREST)), Stamp, datetime),
        (Meeting(DatePoint(2026, 10, 25, 3, 30, tzinfo=BUCHAREST, fold=1)), Meeting, datetime),
    ],
    ids=["date-point", "date-point-in-a-zone", "date-point-zoned"],
)
def test_a_datetime_subclass_reads_back_equal_as_a_datetime(
    value: object, type_: type[object], declared: type[object]
) -> None:
    read = round_trip(value, type_)

    assert read == value
    [field] = cast("dict[str, object]", vars(read)).values()
    assert type(field) is declared


def test_a_partial_write_is_not_read_back() -> None:
    data = PydanticNormalizer().normalize(
        Amount(Decimal("NaN")), context={IGNORED_ATTRIBUTES: {"other"}}
    )

    assert data == {"value": "NaN"}


@pytest.mark.parametrize(
    ("value", "context"),
    [
        (Ratio(value=math.inf), {}),
        (Ratio(value=-math.inf), {}),
        (Ratio(value=math.nan), {}),
        (Proportion(math.inf), {}),
        (Ratio(value=math.inf), {IGNORED_ATTRIBUTES: {"other"}}),
    ],
    ids=["infinity", "minus-infinity", "nan", "pydantic-dataclass", "partial-write"],
)
def test_it_refuses_to_write_what_json_has_no_form_for_whatever_a_model_reads(
    value: object, context: Context
) -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().normalize(value, context=context)

    assert (raised.value.path, raised.value.error_type) == ("value", "finite_number")
    assert raised.value.message == "it has no JSON form: Input should be a finite number"


def test_a_refusal_a_serializer_raises_in_this_package_words_is_passed_on() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().normalize(Refusing(1))

    assert (raised.value.path, raised.value.error_type) == ("value", "refused")
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__


def test_a_zoned_datetime_without_a_named_zone_is_refused_in_words_saying_why() -> None:
    with pytest.raises(NotNormalizableValueError, match="naive"):
        _ = PydanticNormalizer().normalize(Meeting(datetime(2026, 1, 1)))  # noqa: DTZ001 - the point


# pydantic's words for a value that contains itself and for one too deep: the only way to tell
# them apart, so a pydantic release that rewords them fails here first.


@pytest.mark.parametrize(
    ("node", "words"),
    [(looped_node(), CYCLE), (chain_of_nodes(1000), TOO_DEEP)],
    ids=["cycle", "too-deep"],
)
def test_pydantic_words_a_value_it_cannot_write(node: Node, words: str) -> None:
    with pytest.raises(ValueError, match=rf"^{re.escape(words)}$"):
        _ = cast("object", TypeAdapter(Node).dump_python(node, mode="json"))


@pytest.mark.parametrize(
    ("data", "words"),
    [(looped_list(), CYCLE), (nested_lists(1000), TOO_DEEP)],
    ids=["cycle", "too-deep"],
)
def test_pydantic_words_data_it_cannot_write_as_json(data: object, words: str) -> None:
    with pytest.raises(
        ValueError, match=rf"^Error serializing to JSON: ValueError: {re.escape(words)}$"
    ):
        _ = to_json(data)


class Host(BaseModel):
    """A model reading an address, and a port its own validator words the refusal of."""

    address: IPv4Address
    port: int = 0

    @field_validator("port")
    @classmethod
    def check(cls, port: int) -> int:
        if port > 65535:
            msg = f"port {port} is past the last one"
            raise ValueError(msg)
        return port


def test_the_words_of_an_application_validator_reach_its_refusal_beside_a_built_in_one() -> None:
    data = {"address": f"10.0.0.{PLANTED_VALUE}", "port": 70000}

    with pytest.raises(PartialDenormalizationError) as raised:
        _ = PydanticNormalizer().denormalize(
            data, Host, context={STRICT: True, COLLECT_DENORMALIZATION_ERRORS: True}
        )

    assert [(error.path, error.message) for error in raised.value.errors] == [
        ("address", "Input is not a valid IPv4 address"),
        ("port", "Value error, port 70000 is past the last one"),
    ]


@pytest.mark.parametrize(
    ("data", "type_", "context"),
    [
        ({"sku": "A", "price": PLANTED_VALUE}, Item, {}),
        ({"sku": "A", "price": 1, "coupon": PLANTED_VALUE}, Item, {}),
        ({"items": [{"price": PLANTED_VALUE}]}, Cart, {COLLECT_DENORMALIZATION_ERRORS: True}),
        (PLANTED_VALUE, UUID, {}),
        (f"2026-13-01T{PLANTED_VALUE}", datetime, {}),
        ({"method": {"kind": PLANTED_VALUE, "store": "S"}}, Dispatch, {}),
        (f"Mars/{PLANTED_VALUE}", ZoneInfo, {}),
        (PLANTED_VALUE, ImportString, {}),
        ({PLANTED_VALUE: 1}, dict[int, int], {}),
        (f"10.0.0.{PLANTED_VALUE}", IPv4Address, {}),
        (f"::{PLANTED_VALUE}", IPv6Address, {}),
        (f"10.0.0.0/{PLANTED_VALUE}", IPv4Network, {}),
        (f"::/{PLANTED_VALUE}", IPv6Network, {}),
        (f"10.0.0.{PLANTED_VALUE}/24", IPv4Interface, {}),
        (f"::{PLANTED_VALUE}/64", IPv6Interface, {}),
        (f"user@[IPv6:{PLANTED_VALUE}]", EmailStr, {}),
        (f"{PLANTED_VALUE} <user@[IPv6:{PLANTED_VALUE}]>", NameEmail, {}),
        ({"address": f"10.0.0.{PLANTED_VALUE}"}, Host, {STRICT: True}),
        (
            {"address": f"10.0.0.{PLANTED_VALUE}"},
            Host,
            {STRICT: True, COLLECT_DENORMALIZATION_ERRORS: True},
        ),
    ],
    ids=[
        "field",
        "extra-key",
        "collected",
        "uuid",
        "datetime",
        "union-tag",
        "time-zone",
        "import-path",
        "key",
        "ipv4-address",
        "ipv6-address",
        "ipv4-network",
        "ipv6-network",
        "ipv4-interface",
        "ipv6-interface",
        "email",
        "name-email",
        "strict-model-address",
        "collected-strict-model-address",
    ],
)
def test_no_error_quotes_the_data_or_chains_what_does(
    data: object, type_: object, context: Context
) -> None:
    with pytest.raises(UnexpectedValueError) as raised:
        _ = PydanticNormalizer().denormalize(data, type_, context=context)

    assert PLANTED_VALUE not in "".join(traceback.format_exception(raised.value))
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


class Checking(BaseModel):
    """A model whose validator fails in this package's words, as one using a serializer may."""

    count: int

    @field_validator("count")
    @classmethod
    def check(cls, count: int) -> int:
        msg = f"the validator's own words about {count}"
        raise LogicError(msg)


def test_this_package_s_error_raised_as_the_data_is_read_is_passed_on() -> None:
    with pytest.raises(LogicError, match="the validator's own words"):
        _ = PydanticNormalizer().denormalize({"count": 1}, Checking)


def test_code_the_data_runs_as_it_is_read_is_refused_without_its_words() -> None:
    key = CollidingKey("sku", PLANTED_VALUE)
    data = {key: 1, "sku": "A", "price": 1}
    key.armed = True

    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().denormalize(data, Item, context={FROM_ATTRIBUTES: True})

    assert (raised.value.error_type, raised.value.current_type) == ("not_readable", "dict")
    assert "RuntimeError" in str(raised.value)
    assert PLANTED_VALUE not in "".join(traceback.format_exception(raised.value))
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
