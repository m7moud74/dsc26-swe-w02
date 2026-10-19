
# ADR 0002: Use Cursors for Parcel Pagination

## Status

Accepted

## Context

The parcel list is ordered by creation sequence and may be filtered by its current state. Parcel states can change between consecutive list requests. Offset-based pagination depends on the current result positions, which can shift when records enter or leave the filtered result set.

## Decision

Use opaque cursors issued by the API. Each cursor records the last returned creation sequence together with the state filter and page limit. The API accepts only cursors issued by the same application instance and rejects unknown cursors or cursors used with different query parameters.

## Consequences

- Creation-order keyset pagination avoids relying on shifting result offsets.
- Previously returned records are not repeated just because their state changes.
- The in-memory implementation must retain cursor metadata for issued cursors.
- Cursor tokens are application-specific and are not intended to be permanent bookmarks.
- Cursor storage and token lifecycle would need reconsideration if the API moved to distributed instances or persistent storage.
