# AGENTS.md

Tawseel Parcel API: FastAPI service for parcel lifecycle and cursor pagination.

## Commands

- Install: `uv pip install -r requirements.txt`
- Run: `uvicorn app.api:app`
- Test: `pytest`

## Project layout

- API and routes: `app/api.py` (`create_app()` factory)
- Domain logic: `app/domain.py`
- ADRs: `docs/adr/0001-parcel-lifecycle-in-domain.md`, `docs/adr/0002-use-cursors-for-parcel-pagination.md`
- API contract: Pydantic models and FastAPI route definitions in `app/api.py`; runtime OpenAPI at `/openapi.json`

## Versions

- Python 3.12; FastAPI 0.141.1

## Architecture constraints

- `app/domain.py` must stay independent of FastAPI, Starlette, Pydantic, and databases.
- `Parcel` is an immutable frozen dataclass; transitions live in `apply_event`.
- Invalid transitions raise `InvalidTransition`; the API maps them to HTTP 409.
- Each `create_app()` instance owns isolated in-memory stores.
- Request models use Pydantic v2 with `extra="forbid"`.
- Errors use `application/problem+json` with RFC 9457-style Problem Details.

## Conventions

- snake_case functions/variables; PascalCase models; camelCase operation IDs.
- Immutable domain updates via `dataclasses.replace`.
- Opaque cursor pagination: snapshot IDs on first request; validate cursor state and limit match.

## Traps

1. Use `httpx2`, not `httpx`.
2. Preserve opaque cursor pagination, snapshots, and cursor validation.
3. Keep `Parcel` immutable and transition rules in `app/domain.py`; do not use global stores.