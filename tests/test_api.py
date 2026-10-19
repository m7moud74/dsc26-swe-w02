
import pytest
from fastapi.testclient import TestClient

from app.api import create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def create_parcel(client, merchant_ref="ORDER-001"):
    response = client.post(
        "/v1/parcels",
        json={
            "merchant_ref": merchant_ref,
            "cod_amount_piastres": 5000,
            "address_text": "Cairo, Egypt",
        },
    )
    return response


def test_create_parcel_returns_201_and_location(client):
    response = create_parcel(client)

    assert response.status_code == 201

    parcel = response.json()
    assert parcel["id"].startswith("pcl_")
    assert parcel["merchant_ref"] == "ORDER-001"
    assert parcel["cod_amount_piastres"] == 5000
    assert parcel["address_text"] == "Cairo, Egypt"
    assert parcel["state"] == "created"
    assert parcel["attempts"] == 0

    assert response.headers["location"] == (
        f"/v1/parcels/{parcel['id']}"
    )


def test_duplicate_merchant_ref_returns_problem_409(client):
    create_parcel(client)

    response = create_parcel(client)

    assert response.status_code == 409
    assert response.headers["content-type"].startswith(
        "application/problem+json"
    )
    assert response.json()["status"] == 409


def test_invalid_create_body_returns_problem_422(client):
    response = client.post(
        "/v1/parcels",
        json={
            "merchant_ref": "",
            "cod_amount_piastres": -1,
            "address_text": "",
        },
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(
        "application/problem+json"
    )

    errors = response.json()["errors"]
    invalid_fields = {
        error["loc"][-1]
        for error in errors
    }

    assert invalid_fields == {
        "merchant_ref",
        "cod_amount_piastres",
        "address_text",
    }


def test_get_existing_parcel(client):
    created = create_parcel(client).json()

    response = client.get(f"/v1/parcels/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_missing_parcel_returns_problem_404(client):
    response = client.get("/v1/parcels/pcl_missing")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith(
        "application/problem+json"
    )
    assert response.json()["status"] == 404


def test_dispatch_updates_parcel(client):
    created = create_parcel(client).json()

    response = client.post(
        f"/v1/parcels/{created['id']}/events",
        json={"type": "dispatch"},
    )

    assert response.status_code == 200
    assert response.json()["state"] == "out_for_delivery"
    assert response.json()["attempts"] == 1


def test_invalid_transition_returns_problem_409(client):
    created = create_parcel(client).json()

    response = client.post(
        f"/v1/parcels/{created['id']}/events",
        json={"type": "deliver"},
    )

    assert response.status_code == 409
    assert response.headers["content-type"].startswith(
        "application/problem+json"
    )

    # The failed operation must not modify the parcel.
    current = client.get(
        f"/v1/parcels/{created['id']}"
    ).json()

    assert current["state"] == "created"
    assert current["attempts"] == 0


@pytest.mark.parametrize(
    "body",
    [
        {"type": "teleport"},
        {},
    ],
)
def test_invalid_event_body_returns_problem_422(client, body):
    created = create_parcel(client).json()

    response = client.post(
        f"/v1/parcels/{created['id']}/events",
        json=body,
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(
        "application/problem+json"
    )
    assert response.json()["status"] == 422


def test_event_for_missing_parcel_returns_404(client):
    response = client.post(
        "/v1/parcels/pcl_missing/events",
        json={"type": "dispatch"},
    )

    assert response.status_code == 404


def test_list_parcels_returns_creation_order(client):
    create_parcel(client, "ORDER-001")
    create_parcel(client, "ORDER-002")
    create_parcel(client, "ORDER-003")

    response = client.get("/v1/parcels")

    assert response.status_code == 200
    assert [
        item["merchant_ref"]
        for item in response.json()["items"]
    ] == ["ORDER-001", "ORDER-002", "ORDER-003"]
    assert response.json()["next_cursor"] is None


def test_cursor_pagination_returns_next_page(client):
    create_parcel(client, "ORDER-001")
    create_parcel(client, "ORDER-002")
    create_parcel(client, "ORDER-003")

    first = client.get("/v1/parcels?limit=2").json()

    assert len(first["items"]) == 2
    assert first["next_cursor"] is not None

    second = client.get(
        "/v1/parcels",
        params={
            "limit": 2,
            "cursor": first["next_cursor"],
        },
    ).json()

    assert [
        item["merchant_ref"]
        for item in second["items"]
    ] == ["ORDER-003"]
    assert second["next_cursor"] is None


def test_unknown_cursor_returns_problem_400(client):
    response = client.get(
        "/v1/parcels",
        params={"cursor": "not-a-real-cursor"},
    )

    assert response.status_code == 400
    assert response.headers["content-type"].startswith(
        "application/problem+json"
    )


def test_invalid_limit_returns_problem_422(client):
    response = client.get("/v1/parcels?limit=101")

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(
        "application/problem+json"
    )


def test_each_app_has_its_own_store():
    first_client = TestClient(create_app())
    second_client = TestClient(create_app())

    try:
        created = create_parcel(first_client).json()

        response = second_client.get(
            f"/v1/parcels/{created['id']}"
        )

        assert response.status_code == 404
    finally:
        first_client.close()
        second_client.close()
