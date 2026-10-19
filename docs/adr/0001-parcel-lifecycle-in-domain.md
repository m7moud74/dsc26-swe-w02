
# ADR 0001: Keep Parcel Lifecycle Rules in the Domain

## Status

Accepted

## Context

The parcel API must enforce valid state transitions and delivery-attempt limits. These rules should remain consistent regardless of the HTTP framework or storage implementation.

## Decision

Implement parcel states, event types, the Parcel data model, and the apply_event function in app/domain.py. Keep this module independent of FastAPI, Starlette, Pydantic, and database libraries. Represent Parcel as an immutable dataclass and raise InvalidTransition when an event is not allowed.

## Consequences

- Business rules can be tested without starting an HTTP server.
- Invalid transitions cannot mutate the original Parcel instance.
- The API layer must translate InvalidTransition into an HTTP 409 response.
- Adding new states or events requires updating the domain rules and their tests.
