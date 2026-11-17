# Parcel Desk

Invented parcel dispatch service. Orders with destination `island` and mass
above 20 kg cannot use next-day delivery, regardless of entry channel.
The API, CSV import, and dispatch preview must enforce the same rule.

`src/routing` calculates shipping quotes; `src/units` formats measurements.
Run `node tests/run.mjs` for the project's checks.
