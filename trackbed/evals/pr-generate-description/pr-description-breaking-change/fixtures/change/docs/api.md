# Reports API

## GET /v1/reports

Lists one account's reports, newest first.

| Parameter | Required | Description |
| --- | --- | --- |
| `accountId` | Yes | Return reports for this account. |
| `createdAfter` | No | Only return reports created after this ISO 8601 time. |

Responses:

- `200` with `{ "reports": [...] }`
- `400` with `{ "error": "accountId is required" }` when `accountId` is left out
- `401` when the token is missing or expired
