
# AI Usage

## Tools

- ChatGPT: Used to discuss the task requirements, plan the implementation steps, draft domain and API code, and identify testing scenarios.
- VS Code: Used to edit and organize the project files.
- pytest: Used to run the automated tests and inspect failures.

## What AI got wrong

- The initial testing setup suggested installing `httpx`, but the installed Starlette TestClient explicitly required `httpx2`. The dependency instructions needed to be corrected based on the actual runtime error.
- The initial implementation needs further verification against the full API contract, especially pagination behavior, validation error formatting, and OpenAPI response documentation.

## In my own words

1. Why does listParcels need cursor pagination instead of offset pagination?

Cursor pagination provides a more stable way to navigate parcels when data changes between requests. Offset pagination can skip or repeat items when new records are added or existing records change.

2. Which operation would break the courier app if a field were renamed, and who must approve that contract change?

The getParcel operation could break if a field such as state were renamed because the courier app depends on the API response contract. The change should be reviewed and approved by the backend and courier app teams before implementation
