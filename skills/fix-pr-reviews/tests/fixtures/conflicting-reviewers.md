# PR Context
Title: Add retry logic to payment processing
Description: |
  Wraps payment gateway calls with retry logic to handle transient failures.
  Uses exponential backoff with jitter. Max 3 retries.

  ## Test Plan
  - [x] Unit tests for retry logic
  - [x] Unit tests for backoff calculation
  - [ ] Integration test with payment gateway sandbox
Files changed:
  - src/services/payment-service.ts
  - src/utils/retry.ts (new)
  - tests/services/payment-service.test.ts

# Review Comments

## Comment 1
Reviewer: frank
File: src/utils/retry.ts
Line: 18
Body: "I think we should use a circuit breaker pattern here instead of simple retries. With retries alone, if the payment gateway is down, we'll just hammer it with 3x the traffic. A circuit breaker would stop trying after N consecutive failures and back off entirely."
In reply to: null

## Comment 2
Reviewer: grace
File: src/utils/retry.ts
Line: 18
Body: "Simple retries with exponential backoff is the right call for this use case. The payment gateway has a 99.99% SLA — we're handling transient blips, not prolonged outages. Adding a circuit breaker is over-engineering for the failure mode we're actually seeing (occasional 503s that resolve in <1s)."
In reply to: null

## Comment 3
Reviewer: frank
File: src/services/payment-service.ts
Line: 42
Body: "You're retrying on ALL errors. That's dangerous for payment processing — a 400 (bad request) should NOT be retried because the charge might have actually gone through. You should only retry on 502, 503, and 504."
In reply to: null

## Comment 4
Reviewer: grace
File: src/services/payment-service.ts
Line: 42
Body: "Good point from Frank about retrying on all errors. But I'd expand the list slightly — also retry on ECONNRESET and ETIMEDOUT network errors, not just HTTP status codes."
In reply to: 3

## Comment 5
Reviewer: frank
File: src/services/payment-service.ts
Line: 55
Body: "The idempotency key generation uses `Date.now()`. That's not unique enough — two requests in the same millisecond get the same key. Use `crypto.randomUUID()` instead."
In reply to: null

## Comment 6
Reviewer: grace
File: src/utils/retry.ts
Line: 8
Body: "The jitter implementation looks off. You're adding jitter to the base delay before the exponential multiplier, which means jitter has less effect on later retries. The standard approach is: `delay = min(cap, base * 2^attempt) + random(0, jitter)`."
In reply to: null

## Comment 7
Reviewer: frank
File: src/services/payment-service.ts
Line: 30
Body: "Nice — I like that you're logging each retry attempt with the attempt number and delay. Good for debugging."
In reply to: null

# Source Context

## src/utils/retry.ts:1-35
```typescript
interface RetryOptions {
  maxRetries: number;
  baseDelay: number;
  maxDelay: number;
  jitter: number;
}

const DEFAULT_OPTIONS: RetryOptions = {
  maxRetries: 3,
  baseDelay: 100,
  maxDelay: 5000,
  jitter: 50,
};

export async function withRetry<T>(
  fn: () => Promise<T>,
  options: Partial<RetryOptions> = {}
): Promise<T> {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  let lastError: Error | undefined;

  for (let attempt = 0; attempt <= opts.maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      if (attempt === opts.maxRetries) break;

      const delay = Math.min(
        opts.maxDelay,
        (opts.baseDelay + Math.random() * opts.jitter) * Math.pow(2, attempt)
      );
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }

  throw lastError;
}
```

## src/services/payment-service.ts:1-65
```typescript
import { withRetry } from '../utils/retry';
import { PaymentGateway, ChargeRequest, ChargeResult } from '../gateways/payment';
import { Logger } from '../utils/logger';

export class PaymentService {
  constructor(
    private gateway: PaymentGateway,
    private logger: Logger
  ) {}

  async processPayment(request: ChargeRequest): Promise<ChargeResult> {
    const idempotencyKey = `pay_${Date.now()}_${request.userId}`;

    this.logger.info('Processing payment', {
      userId: request.userId,
      amount: request.amount,
      idempotencyKey,
    });

    try {
      const result = await withRetry(
        async () => {
          this.logger.debug('Attempting payment gateway call', {
            attempt: 'unknown', // TODO: expose attempt number
            idempotencyKey,
          });

          return this.gateway.charge({
            ...request,
            idempotencyKey,
          });
        },
        {
          maxRetries: 3,
          baseDelay: 200,
        }
      );

      this.logger.info('Payment succeeded', {
        userId: request.userId,
        chargeId: result.chargeId,
      });

      return result;
    } catch (error) {
      this.logger.error('Payment failed after retries', {
        userId: request.userId,
        error: (error as Error).message,
      });
      throw error;
    }
  }
}
```
