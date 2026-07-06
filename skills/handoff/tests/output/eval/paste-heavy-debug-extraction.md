## Summary
Fixed three issues in the Stripe webhook processor: refactored `WebhookValidator` to accept a Stripe instance via dependency injection (eliminating the undefined `STRIPE_SECRET_KEY` crash in tests), fixed a Stripe event type mismatch where the test sent `payment_intent.failed` but the processor handled `invoice.payment_failed`, and added a `payment_intent.failed` handler for one-off charges. Added a `withRetry` utility for Redis writes with exponential backoff, integration test infrastructure using docker-compose Redis, and a `.env.test` file. All 7 integration tests pass; changes committed to `feat/webhook-processor` in 3 commits.

## Decisions
- **Dependency injection for WebhookValidator:** Pass the Stripe instance into the validator constructor rather than letting it create its own — enables testing without a real API key since `constructEvent` only does local signature verification.
- **Real Redis over mocks for integration tests:** Use `docker-compose up -d redis` in a `pretest:integration` script — mocking Redis burned the team on a previous project.
- **Custom retry wrapper over p-retry or BullMQ:** Hand-rolled 15-line `withRetry` with exponential backoff — avoids a new dependency for a simple need.
- **Handle both `invoice.payment_failed` and `payment_intent.failed`:** Route both to the dead letter queue with different metadata — covers subscriptions and one-off charges.

## Do Not Retry
- Do not import from `stripe/lib/crypto` or other Stripe internal paths — they are not public and the paths changed between v11 and v12.
- Do not use `payment_intent.failed` interchangeably with `invoice.payment_failed` — they are distinct Stripe event types for different payment flows.
- Do not use ioredis `retryStrategy` alone for operation-level retry — it only handles connection-level reconnection, not individual command failures.

## Constraints
- Do not add BullMQ until the system needs multiple consumers, priority queues, or more than the current 3 event types.
- Do not mock Redis in integration tests — use real Redis via docker-compose.

## Next Steps
1. Implement subscription provisioning logic in `handleCheckoutComplete` — the TODO in that method is the only remaining unimplemented handler.
2. Consider adding a consumer/worker for the `provisioning:queue` Redis list — currently entries are pushed but nothing reads them.

## Key Files
- `src/webhooks/processor.ts` — main webhook dispatch and event handlers
- `src/webhooks/validator.ts` — refactored to accept Stripe instance via DI
- `src/webhooks/types.ts` — ProcessorConfig type definitions
- `src/queue/retry.ts` — withRetry exponential backoff utility (new)
- `src/queue/redis-client.ts` — Redis client wrapper
- `tests/webhooks/integration.test.ts` — 7 passing integration tests
- `docker-compose.yml` — Redis and Postgres service definitions
- `.env.test` — test environment config for Redis URL and webhook secret
