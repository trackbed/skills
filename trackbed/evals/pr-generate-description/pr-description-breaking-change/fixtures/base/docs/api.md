# Reports API

## GET /v1/reports

Lists reports, newest first.

| Parameter | Required | Description |
| --- | --- | --- |
| `accountId` | No | Only return reports for this account. When left out, returns reports for every account the token can see. |
| `createdAfter` | No | Only return reports created after this ISO 8601 time. |

Responses:

- `200` with `{ "reports": [...] }`
- `401` when the token is missing or expired
