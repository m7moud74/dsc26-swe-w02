
# Tawseel Parcel API

A contract-first REST API for managing parcel deliveries, tracking delivery attempts, and recording parcel lifecycle events.

Built with Python and FastAPI as part of the DSC Software Engineering Week 2 task.

## Features

- Create parcels with validated request data.
- Retrieve a parcel by its ID.
- List parcels with state filtering and cursor-based pagination.
- Record delivery events and enforce valid state transitions.
- Track delivery attempts with a maximum of three dispatch attempts.
- Prevent duplicate merchant references.
- Return structured errors using `application/problem+json` following RFC 9457.
- Generate an OpenAPI specification through FastAPI.
- Isolate in-memory data between application instances.

## Tech Stack

- **Language:** Python
- **API Framework:** FastAPI
- **Validation:** Pydantic
- **ASGI Server:** Uvicorn
- **Testing:** pytest and FastAPI TestClient

## Project Structure

```text
dsc26-swe-w02/
├── app/
│   ├── __init__.py
│   ├── api.py
│   └── domain.py
├── tests/
│   ├── __init__.py
│   ├── test_api.py
│   └── test_domain.py
├── docs/
│   └── adr/
├── AI_USAGE.md
├── requirements.txt
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.12
- `uv`

### 1. Clone the repository

```bash
git clone https://github.com/m7moud74/dsc26-swe-w02.git
cd dsc26-swe-w02
```

### 2. Create a virtual environment

```bash
uv venv
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
uv pip install -r requirements.txt
```

### 4. Run the API

```bash
uvicorn app.api:app --reload
```

The API will be available at:

`http://127.0.0.1:8000`

Interactive API documentation:

`http://127.0.0.1:8000/docs`

Alternative API documentation:

`http://127.0.0.1:8000/redoc`

OpenAPI JSON specification:

`http://127.0.0.1:8000/openapi.json`

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/v1/parcels` | Create a parcel |
| GET | `/v1/parcels/{parcel_id}` | Retrieve a parcel |
| GET | `/v1/parcels` | List parcels with optional filtering and pagination |
| POST | `/v1/parcels/{parcel_id}/events` | Record a parcel lifecycle event |

### Create a Parcel

`POST /v1/parcels`

Example request:

```json
{
  "merchant_ref": "ORDER-001",
  "cod_amount_piastres": 150000,
  "address_text": "12 Example Street, Cairo"
}
```

A successful request returns `201 Created`, the created parcel, and a `Location` header pointing to the new resource.

### List Parcels

`GET /v1/parcels?state=created&limit=20`

Supported query parameters:

- `state`: Optional parcel state filter.
- `limit`: Number of items per page, from 1 to 100; defaults to 20.
- `cursor`: Opaque cursor returned by the previous page.

Example response:

```json
{
  "items": [],
  "next_cursor": null
}
```

Use the returned `next_cursor` to request the next page. When no more pages remain, `next_cursor` is `null`.

### Record a Parcel Event

`POST /v1/parcels/{parcel_id}/events`

Example request:

```json
{
  "type": "dispatch"
}
```

Supported event types:

- `dispatch`
- `deliver`
- `fail`
- `return`

## Parcel Lifecycle

| Current State | Event | Resulting State |
|---|---|---|
| `created` | `dispatch` | `out_for_delivery` |
| `out_for_delivery` | `deliver` | `delivered` |
| `out_for_delivery` | `fail` | `failed_attempt` |
| `failed_attempt` | `dispatch` | `out_for_delivery` |
| `failed_attempt` | `return` | `returned` |

Each dispatch increments the delivery attempt counter. A maximum of three dispatch attempts is allowed.

`delivered` and `returned` are terminal states. Invalid transitions return `409 Conflict` without modifying the stored parcel.

## Error Handling

Errors use the `application/problem+json` media type and follow the RFC 9457 Problem Details format.

Depending on the operation, the API may return:

- `400 Bad Request` — Invalid or unissued pagination cursor.
- `404 Not Found` — Parcel does not exist.
- `409 Conflict` — Duplicate merchant reference or invalid state transition.
- `422 Unprocessable Content` — Invalid request data or query parameters.

Validation errors include an `errors` array containing the location and message for each invalid field.

## Running Tests

Run the test suite from the project root:

```bash
python -m pytest -q
```

The test suite covers domain state transitions, request validation, parcel operations, error handling, and pagination behavior.

## Architecture and Design Decisions

- **Domain isolation:** Parcel lifecycle rules are implemented in `app/domain.py` without web framework dependencies.
- **Immutable domain model:** State changes return a new `Parcel` instance instead of modifying the existing object.
- **Application factory:** `create_app()` creates a fresh in-memory store for each application instance.
- **Cursor pagination:** Pagination uses opaque, server-issued cursors instead of client-controlled offsets.
- **Contract-first API:** Endpoints use explicit operation IDs and document their request and response contracts through OpenAPI.
- **Problem Details:** API errors use a consistent machine-readable format.

Architecture Decision Records are maintained in `docs/adr/`.

## Storage Limitations

This implementation uses in-memory storage for the task. Parcel data is not persisted across application restarts, and the API is not intended to provide production-grade persistence.

## AI Usage

AI assistance and reflections on the development process are documented in [`AI_USAGE.md`](AI_USAGE.md).

## License

Created for educational purposes as part of the DSC Software Engineering Week 2 task.
