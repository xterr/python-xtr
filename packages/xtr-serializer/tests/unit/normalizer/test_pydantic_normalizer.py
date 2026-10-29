"""Values to plain data and back through pydantic, exactly, with errors that never quote data."""

from __future__ import annotations

import math
import re
import traceback
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING, Annotated, cast
from uuid import UUID

import pytest
from pydantic import TypeAdapter
from pydantic_core import to_json

from tests.fixtures.orders import (
    Cart,
    CartItem,
    ClosedParcel,
    Coupon,
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
    Status,
    StrictCart,
    Ticket,
)
from xtr_serializer.encoder.json_encoder import JsonEncoder
from xtr_serializer.exception import (
    CircularReferenceError,
    ExtraAttributesError,
    InvalidArgumentError,
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
from xtr_serializer.normalizer import pydantic_normalizer as module
from xtr_serializer.normalizer.pydantic_normalizer import PydanticNormalizer

if TYPE_CHECKING:
    from xtr_serializer.context.context import Context

PLANTED_VALUE = "s3cr3t-t0ken-4f9a"
CYCLE = "Circular reference detected (id repeated)"
TOO_DEEP = "Circular reference detected (depth exceeded)"


class Opaque:
    """A class pydantic has no schema for."""


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
        (RECEIPT, Receipt),
        (Status.SHIPPED, Status),
        ([Item(sku="A-1", price=1), Item(sku="B-2", price=2)], list[Item]),
    ],
    ids=["model", "dataclass", "typed-dict", "enum", "list-of-models"],
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
    build = module._build_adapter

    def counting_build(type_: object) -> TypeAdapter[object] | str:
        types.append(type_)
        return build(type_)

    monkeypatch.setattr(module, "_build_adapter", counting_build)
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
    monkeypatch.setattr(module, "_CACHE_SIZE", 2)
    normalizer = PydanticNormalizer()

    for type_ in (int, str, int, float, int, str):
        assert normalizer.supports_denormalization(None, type_)

    assert built == [int, str, float, str]


def test_it_refuses_to_normalize_what_it_cannot_build() -> None:
    with pytest.raises(InvalidArgumentError, match="'Opaque'"):
        _ = PydanticNormalizer().normalize(Opaque())


def test_it_refuses_to_denormalize_into_what_it_cannot_build() -> None:
    with pytest.raises(InvalidArgumentError, match="'Opaque'"):
        _ = PydanticNormalizer().denormalize({}, Opaque)


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


def test_a_value_quoting_the_words_of_a_cycle_is_not_a_cycle() -> None:
    misfit = Item.model_construct(sku="A", price=CYCLE)

    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PydanticNormalizer().normalize(misfit)

    assert type(raised.value) is NotNormalizableValueError


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


@pytest.mark.parametrize(
    ("data", "type_", "context"),
    [
        ({"sku": "A", "price": PLANTED_VALUE}, Item, {}),
        ({"sku": "A", "price": 1, "coupon": PLANTED_VALUE}, Item, {}),
        ({"items": [{"price": PLANTED_VALUE}]}, Cart, {COLLECT_DENORMALIZATION_ERRORS: True}),
        (PLANTED_VALUE, UUID, {}),
        (f"2026-13-01T{PLANTED_VALUE}", datetime, {}),
        ({"method": {"kind": PLANTED_VALUE, "store": "S"}}, Dispatch, {}),
        ({"code": PLANTED_VALUE}, Coupon, {}),
        ({PLANTED_VALUE: 1}, dict[int, int], {}),
    ],
    ids=["field", "extra-key", "collected", "uuid", "datetime", "union-tag", "validator", "key"],
)
def test_no_error_quotes_the_data_or_chains_what_does(
    data: object, type_: object, context: Context
) -> None:
    with pytest.raises(UnexpectedValueError) as raised:
        _ = PydanticNormalizer().denormalize(data, type_, context=context)

    assert PLANTED_VALUE not in "".join(traceback.format_exception(raised.value))
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
