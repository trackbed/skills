# Retry safety

Reference material for Rule 1 of `trackbed:code:api-design`. A caller that times out cannot tell whether its call took effect, so it retries. Proxies, SDKs, and message brokers resend on their own. The contract decides what happens next; if it says nothing, every caller guesses, and Hyrum's Law turns the guesses into the contract.

## State the repeat behavior for every state-changing operation

For each operation that changes state, the contract answers two questions:

1. **Is a repeat safe?** Either the operation is naturally idempotent, it accepts an idempotency key, or the contract says plainly that a repeat is not safe and how a caller checks the outcome instead.
2. **What does the repeat return?** Name the status and body the second call gets, so a caller knows how to read a retry. A keyed replay returns the original status and body, so a retried success looks the same as the first.

| Operation | Repeat safe? | What the contract states |
| --- | --- | --- |
| Full replacement (`PUT /tasks/:id`) | Yes — the same body leaves the same state | The same success status and resource as the first call |
| Partial update that sets fields (`PATCH /tasks/:id`) | Yes, when it only sets values | The same success status and resource |
| Partial update that increments, appends, or toggles | No — each repeat changes state again | Needs an idempotency key when a duplicate is costly, or a set-to-value design instead |
| Removal (`/tasks/:id` with the removal method) | Yes — the resource ends up gone either way | Either the same success status again, or `404` with `TASK_NOT_FOUND`; pick one and state it |
| Create (`POST /tasks`) | No — each call creates another record | Needs an idempotency key when a duplicate record is costly |
| Side effect outside the system (charge, email, SMS) | No | Needs an idempotency key when a duplicate is costly |

When a repeat is unsafe and a key is not worth its cost (a cheap, rare, easily undone duplicate), say so in the contract. "Not safe to retry; check `GET /tasks?externalRef=...` first" is a valid contract.

## The idempotency-key contract

Where a duplicate is costly, the operation accepts an idempotency key, typically an `Idempotency-Key` request header.

- **The caller makes the key once per intent** and sends the same key on every retry of that intent. A key regenerated per attempt protects nothing. A key derived from the payload alone (`userId` plus amount) merges two legitimate, identical requests into one.
- **The server claims the key before starting the side effect**, storing it with a fingerprint of the request body, and makes the claim atomic (a unique constraint or equivalent). A read-then-write check lets two concurrent retries both pass. When the side effect is a write to the same database, claim the key, do the write, and record the outcome in one transaction; a crash then rolls back all three.

A claimed key is in one of four states. One rule moves it between them: release the key only when the server knows the side effect did not and will not happen, and record only a final outcome.

- **Claimed** — the first call is still running. A same-body repeat gets the case 2 response and never starts the side effect.
- **Recorded** — the side effect finished with a final outcome: success, or a definite failure such as an explicit decline. A repeat with the same key and the same body returns the recorded outcome, the original status and body, without repeating the side effect. A recorded error is replayed the same way, unless the contract names errors that are safe to retry under the same key.
- **Released** — the call failed before any request reached the side effect (validation, rate limiting, a refused connection). Nothing is kept, so a same-key repeat runs as a new attempt.
- **Unfinished** — the outcome is unknown: the server crashed, or the side-effect call timed out, lost its connection, returned an ambiguous error such as a `5xx`, or is still pending. A same-body repeat gets the case 2 response until a reconciliation step, not a retry, observes a final outcome and moves the key to recorded or released. A call that merely seems stuck is never released. The contract states how long reconciliation can take.

In every state except released, a repeat with a different body gets the case 1 response first. The case 1 and case 2 rejections never claim the key, so they leave its state unchanged.

The contract then covers these five cases explicitly. The codes below are the canonical `UPPER_SNAKE` shapes. On an existing API, use the error shape and casing found during convention detection, and check its state-changing endpoints for an existing idempotency header and the statuses they return for a reused or in-flight key; match those instead of adding a second convention.

### 1. Key reused with a different body

The caller has a bug: one key, two different intents. Serving the first response would hide the second request. Reject it as a validation failure:

```
→ 422
{ "code": "IDEMPOTENCY_KEY_REUSED", "message": "This idempotency key was already used with a different request." }
```

### 2. Duplicate arrives while the first call runs

A client whose first call is slow often retries before that call finishes. Choose one behavior and state it:

- **Reject** — the default. The state conflicts with an in-progress request:

  ```
  → 409
  { "code": "REQUEST_IN_PROGRESS", "message": "A request with this idempotency key is still being processed." }
  ```

- **Wait** — hold the duplicate for a bounded time, then answer as the key's state then allows, or with the `409` if the bound expires.
- **Accept as pending** — for long-running work, return `202` with a status URL that both calls share.

A slow first call has not failed. While its key is claimed or unfinished, every duplicate gets one of the responses above and never starts the side effect itself.

### 3. Unknown outcome after a timeout

After a timeout the caller does not know whether the call took effect. The contract tells callers to retry with the **same** key; the retry gets what the key's state allows, as listed above. A new key turns the retry into a second request. On the server, an unknown outcome is the unfinished state: the key stays held until reconciliation observes a final outcome.

If the operation also exposes a lookup (by key, client reference, or returned ID), name it as the way to check the outcome without retrying.

### 4. How long keys are kept

State the retention window in the contract, for example "keys are kept for 7 days". Size it to the slowest route by which the same intent can arrive again: the client retry policy, queue redelivery, or replay from a dead-letter queue. A key that expires before such a replay lets the replay run as a new request.

Only recorded keys expire, and the window starts when the outcome is recorded. Say what happens after expiry: a request with an expired key is treated as new. Callers must not retry an intent past the window without first checking its outcome.

### 5. At-least-once delivery to webhook and queue consumers

Webhook senders and message queues redeliver when an acknowledgement goes missing, and a consumer can finish its work and then crash before acknowledging. When the API emits events, the contract:

- States that delivery is at-least-once, and whether order is guaranteed.
- Gives every event a stable, unique `eventId` that stays the same across redeliveries.
- Tells consumers to deduplicate on `eventId`, to record a processed `eventId` only together with or after the work it guards, and to keep processed IDs at least as long as the sender's redelivery window, which the contract also states.

When the API is itself the consumer, apply the same rule inbound: process each delivery idempotently, keyed on the sender's event ID.
