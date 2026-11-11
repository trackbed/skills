# Changelog

## 3.0.0

### Breaking

- `GET /v1/reports` requires `accountId`. A request without it gets `400`.

## 2.7.0

- Add `createdAfter` filter to `GET /v1/reports`.

## 2.6.0

- Add `GET /v1/reports/:id/export`.
