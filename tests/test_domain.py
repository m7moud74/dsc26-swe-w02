
import pytest

from app.domain import (
    MAX_ATTEMPTS,
    EventType,
    InvalidTransition,
    Parcel,
    ParcelState,
    apply_event,
)


@pytest.fixture
def parcel():
    return Parcel(
        id="pcl_1",
        merchant_ref="ORDER-001",
        cod_amount_piastres=5000,
        address_text="Cairo, Egypt",
    )


def test_new_parcel_starts_as_created(parcel):
    assert parcel.state == ParcelState.CREATED
    assert parcel.attempts == 0


def test_dispatch_moves_parcel_out_for_delivery(parcel):
    updated = apply_event(parcel, EventType.DISPATCH)

    assert updated.state == ParcelState.OUT_FOR_DELIVERY
    assert updated.attempts == 1


def test_dispatch_does_not_mutate_original_parcel(parcel):
    updated = apply_event(parcel, EventType.DISPATCH)

    assert parcel.state == ParcelState.CREATED
    assert parcel.attempts == 0
    assert updated is not parcel


def test_deliver_completes_delivery(parcel):
    dispatched = apply_event(parcel, EventType.DISPATCH)
    delivered = apply_event(dispatched, EventType.DELIVER)

    assert delivered.state == ParcelState.DELIVERED
    assert delivered.attempts == 1


def test_fail_marks_delivery_attempt_as_failed(parcel):
    dispatched = apply_event(parcel, EventType.DISPATCH)
    failed = apply_event(dispatched, EventType.FAIL)

    assert failed.state == ParcelState.FAILED_ATTEMPT
    assert failed.attempts == 1


def test_failed_attempt_can_be_dispatched_again(parcel):
    dispatched = apply_event(parcel, EventType.DISPATCH)
    failed = apply_event(dispatched, EventType.FAIL)
    retried = apply_event(failed, EventType.DISPATCH)

    assert retried.state == ParcelState.OUT_FOR_DELIVERY
    assert retried.attempts == 2


def test_failed_attempt_can_be_returned(parcel):
    dispatched = apply_event(parcel, EventType.DISPATCH)
    failed = apply_event(dispatched, EventType.FAIL)
    returned = apply_event(failed, EventType.RETURN)

    assert returned.state == ParcelState.RETURNED
    assert returned.attempts == 1


def test_fourth_dispatch_is_rejected(parcel):
    current = parcel

    for _ in range(MAX_ATTEMPTS):
        current = apply_event(current, EventType.DISPATCH)
        current = apply_event(current, EventType.FAIL)

    with pytest.raises(InvalidTransition):
        apply_event(current, EventType.DISPATCH)

    assert current.state == ParcelState.FAILED_ATTEMPT
    assert current.attempts == MAX_ATTEMPTS


@pytest.mark.parametrize(
    ("state", "event"),
    [
        (ParcelState.CREATED, EventType.DELIVER),
        (ParcelState.CREATED, EventType.FAIL),
        (ParcelState.CREATED, EventType.RETURN),
        (ParcelState.OUT_FOR_DELIVERY, EventType.DISPATCH),
        (ParcelState.OUT_FOR_DELIVERY, EventType.RETURN),
        (ParcelState.DELIVERED, EventType.DISPATCH),
        (ParcelState.DELIVERED, EventType.DELIVER),
        (ParcelState.DELIVERED, EventType.FAIL),
        (ParcelState.DELIVERED, EventType.RETURN),
        (ParcelState.RETURNED, EventType.DISPATCH),
        (ParcelState.RETURNED, EventType.DELIVER),
        (ParcelState.RETURNED, EventType.FAIL),
        (ParcelState.RETURNED, EventType.RETURN),
    ],
)
def test_invalid_transitions_are_rejected(parcel, state, event):
    current = Parcel(
        id=parcel.id,
        merchant_ref=parcel.merchant_ref,
        cod_amount_piastres=parcel.cod_amount_piastres,
        address_text=parcel.address_text,
        state=state,
        attempts=1,
    )

    with pytest.raises(InvalidTransition):
        apply_event(current, event)
