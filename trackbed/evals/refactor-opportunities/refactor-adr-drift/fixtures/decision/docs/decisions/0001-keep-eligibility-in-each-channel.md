# ADR-0001: Keep next-day eligibility in each channel

- Status: ACCEPTED
- Deciders: dispatch team

## Context

The API, the CSV import, and the dispatch preview each decide whether an order can use next-day delivery. Different teams release the three channels.

## Decision

Each channel module in `src/channels/` keeps its own next-day eligibility check. No module in `src/channels/` imports a shared eligibility rule.

## Rejected

- A shared eligibility module that every channel imports. It would force a coordinated release whenever one channel changes its rule.

## Consequences

A rule change must be copied into each channel by hand.
