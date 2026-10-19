from dataclasses import asdict
from secrets import token_urlsafe
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain import (
    EventType,
    InvalidTransition,
    Parcel,
    ParcelState,
    apply_event,
)


# Request models

class ParcelCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    merchant_ref: str = Field(min_length=1, max_length=64)
    cod_amount_piastres: int = Field(ge=0, le=5_000_000)
    address_text: str = Field(min_length=1, max_length=500)


class ParcelEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: EventType


# Response models

class ParcelResponse(BaseModel):
    id: str
    merchant_ref: str
    cod_amount_piastres: int
    address_text: str
    state: ParcelState
    attempts: int


class ParcelPage(BaseModel):
    items: list[ParcelResponse]
    next_cursor: str | None


class ValidationErrorItem(BaseModel):
    loc: list[str | int]
    msg: str


class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    errors: list[ValidationErrorItem] | None = None


# Application errors

class ProblemError(Exception):
    def __init__(
        self,
        status: int,
        title: str,
        detail: str | None = None,
    ):
        self.status = status
        self.title = title
        self.detail = detail


# Helpers

def parcel_dict(parcel: Parcel) -> dict[str, Any]:
    data = asdict(parcel)
    data["state"] = parcel.state.value
    return data


def problem_response(
    status: int,
    title: str,
    detail: str | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
    }

    if detail is not None:
        body["detail"] = detail

    if errors is not None:
        body["errors"] = errors

    return JSONResponse(
        status_code=status,
        content=body,
        media_type="application/problem+json",
    )


ERROR_RESPONSES = {
    400: {
        "model": ProblemDetails,
        "description": "Invalid cursor",
        "content": {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/ProblemDetails"}
            }
        },
    },
    404: {
        "model": ProblemDetails,
        "description": "Parcel not found",
        "content": {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/ProblemDetails"}
            }
        },
    },
    409: {
        "model": ProblemDetails,
        "description": "Conflict",
        "content": {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/ProblemDetails"}
            }
        },
    },
    422: {
        "model": ProblemDetails,
        "description": "Invalid request",
        "content": {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/ProblemDetails"}
            }
        },
    },
}


# Application factory

def create_app() -> FastAPI:
    api = FastAPI(
        title="Tawseel Parcel API",
        version="1.0.0",
    )

    # Each application instance gets its own store.
    parcels: dict[str, Parcel] = {}
    merchant_refs: set[str] = set()

    next_id = 1
    next_sequence = 1

    # Cursor token -> (snapshot parcel IDs, next index, state filter, limit)
    issued_cursors: dict[
        str,
        tuple[list[str], int, ParcelState | None, int],
    ] = {}

    # Parcel ID -> creation sequence
    sequences: dict[str, int] = {}

    # Handle application-defined errors.
    @api.exception_handler(ProblemError)
    async def handle_problem(
        request: Request,
        exc: ProblemError,
    ) -> JSONResponse:
        return problem_response(
            exc.status,
            exc.title,
            exc.detail,
        )

    # Make FastAPI/Pydantic validation errors follow RFC 9457 format.
    @api.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors = []
        seen_locations = set()

        for error in exc.errors():
            location = list(error["loc"])
            location_key = tuple(location)

            if location_key in seen_locations:
                continue

            seen_locations.add(location_key)

            errors.append(
                {
                    "loc": location,
                    "msg": error["msg"],
                }
            )

        return problem_response(
            status=422,
            title="Validation Error",
            errors=errors,
        )

    # Convert framework HTTP errors to Problem Details too.
    @api.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        titles = {
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            405: "Method Not Allowed",
        }

        title = titles.get(exc.status_code, "HTTP Error")
        detail = exc.detail if isinstance(exc.detail, str) else None

        return problem_response(
            status=exc.status_code,
            title=title,
            detail=detail,
        )

    # Create parcel

    @api.post(
        "/v1/parcels",
        status_code=201,
        operation_id="createParcel",
        response_model=ParcelResponse,
        responses={
            201: {
                "description": "Parcel created",
                "headers": {
                    "Location": {
                        "description": "URL of the created parcel",
                        "schema": {"type": "string"},
                    }
                },
            },
            409: ERROR_RESPONSES[409],
            422: ERROR_RESPONSES[422],
        },
    )
    async def create_parcel(body: ParcelCreate) -> JSONResponse:
        nonlocal next_id, next_sequence

        if body.merchant_ref in merchant_refs:
            raise ProblemError(
                409,
                "Conflict",
                "merchant_ref already exists.",
            )

        parcel_id = f"pcl_{next_id}"

        parcel = Parcel(
            id=parcel_id,
            merchant_ref=body.merchant_ref,
            cod_amount_piastres=body.cod_amount_piastres,
            address_text=body.address_text,
        )

        parcels[parcel_id] = parcel
        merchant_refs.add(body.merchant_ref)

        sequences[parcel_id] = next_sequence

        next_id += 1
        next_sequence += 1

        return JSONResponse(
            status_code=201,
            content=parcel_dict(parcel),
            headers={
                "Location": f"/v1/parcels/{parcel_id}",
            },
        )

    # Get a single parcel

    @api.get(
        "/v1/parcels/{parcel_id}",
        operation_id="getParcel",
        response_model=ParcelResponse,
        responses={
            404: ERROR_RESPONSES[404],
            422: ERROR_RESPONSES[422],
        },
    )
    async def get_parcel(parcel_id: str) -> dict[str, Any]:
        parcel = parcels.get(parcel_id)

        if parcel is None:
            raise ProblemError(
                404,
                "Not Found",
                "Parcel not found.",
            )

        return parcel_dict(parcel)

    # List parcels with cursor pagination

    @api.get(
        "/v1/parcels",
        operation_id="listParcels",
        response_model=ParcelPage,
        responses={
            200: {"description": "Parcel page"},
            400: ERROR_RESPONSES[400],
            422: ERROR_RESPONSES[422],
        },
    )
    async def list_parcels(
        state: ParcelState | None = None,
        limit: int = Query(default=20, ge=1, le=100),
        cursor: str | None = None,
    ) -> dict[str, Any]:

        if cursor is None:
            # Snapshot the matching parcel IDs on the first request.
            # This keeps page membership stable if parcel states change.
            ordered = sorted(
                parcels.values(),
                key=lambda parcel: sequences[parcel.id],
            )

            snapshot_ids = [
                parcel.id
                for parcel in ordered
                if state is None or parcel.state == state
            ]

            start_index = 0

        else:
            cursor_data = issued_cursors.get(cursor)

            if cursor_data is None:
                raise ProblemError(
                    400,
                    "Bad Request",
                    "Invalid cursor.",
                )

            (
                snapshot_ids,
                start_index,
                cursor_state,
                cursor_limit,
            ) = cursor_data

            if cursor_state != state or cursor_limit != limit:
                raise ProblemError(
                    400,
                    "Bad Request",
                    "Cursor does not match the query.",
                )

        page_ids = snapshot_ids[start_index : start_index + limit]

        # Return the current parcel representation for each ID in the snapshot.
        items = [
            parcel_dict(parcels[parcel_id])
            for parcel_id in page_ids
            if parcel_id in parcels
        ]

        next_cursor = None
        next_index = start_index + len(page_ids)

        if next_index < len(snapshot_ids):
            next_cursor = token_urlsafe(24)

            issued_cursors[next_cursor] = (
                snapshot_ids,
                next_index,
                state,
                limit,
            )

        return {
            "items": items,
            "next_cursor": next_cursor,
        }

    # Record a parcel event

    @api.post(
        "/v1/parcels/{parcel_id}/events",
        operation_id="recordParcelEvent",
        response_model=ParcelResponse,
        responses={
            404: ERROR_RESPONSES[404],
            409: ERROR_RESPONSES[409],
            422: ERROR_RESPONSES[422],
        },
    )
    async def record_parcel_event(
        parcel_id: str,
        body: ParcelEvent,
    ) -> dict[str, Any]:

        parcel = parcels.get(parcel_id)

        if parcel is None:
            raise ProblemError(
                404,
                "Not Found",
                "Parcel not found.",
            )

        try:
            updated = apply_event(parcel, body.type)

        except InvalidTransition as exc:
            # Do not change the stored parcel when the transition is invalid.
            raise ProblemError(
                409,
                "Conflict",
                str(exc),
            ) from exc

        parcels[parcel_id] = updated

        return parcel_dict(updated)

    return api


# Default application instance.
app = create_app()