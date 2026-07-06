# PR Context
Title: Add caching layer for product catalog queries
Description: |
  Adds Redis-backed caching for product catalog reads. Cache invalidation
  on writes via pub/sub. TTL configurable per query type.

  ## Test Plan
  - [x] Unit tests for cache key generation
  - [x] Unit tests for invalidation logic
  - [x] Integration tests with Redis test container
Files changed:
  - src/cache/product-cache.ts (new)
  - src/cache/invalidation.ts (new)
  - src/services/product-service.ts
  - src/config/cache-config.ts (new)
  - tests/cache/product-cache.test.ts (new)

# Review Comments

## Comment 1
Reviewer: copilot-pull-request-reviewer
File: src/cache/product-cache.ts
Line: 1
Body: "Consider adding a file-level JSDoc comment to describe the purpose of this module."
In reply to: null

## Comment 2
Reviewer: copilot-pull-request-reviewer
File: src/cache/product-cache.ts
Line: 23
Body: "The `get` method doesn't handle the case where Redis returns `null` vs `undefined`. `JSON.parse(null)` returns `null` which is valid, but `JSON.parse(undefined)` throws. If the Redis client returns `undefined` for missing keys, this will crash."
In reply to: null

## Comment 3
Reviewer: copilot-pull-request-reviewer
File: src/cache/product-cache.ts
Line: 45
Body: "Consider using `Promise.all` instead of sequential `await` calls for batch invalidation to improve performance."
In reply to: null

## Comment 4
Reviewer: copilot-pull-request-reviewer
File: src/config/cache-config.ts
Line: 8
Body: "The default TTL of 3600 seconds (1 hour) is hardcoded. Consider making this configurable via environment variables."
In reply to: null

## Comment 5
Reviewer: kate
File: src/cache/product-cache.ts
Line: 35
Body: "The cache key includes the full query object serialized via JSON.stringify. That's not deterministic — `{a:1, b:2}` and `{b:2, a:1}` produce different keys but represent the same query. You need to sort the keys first or use a stable serialization."
In reply to: null

## Comment 6
Reviewer: kate
File: src/cache/invalidation.ts
Line: 18
Body: "The pub/sub listener reconnect logic has a bug. When Redis disconnects, you're re-subscribing in the `error` event handler. But the `error` event can fire for non-disconnect reasons (like a command error). You should only re-subscribe on the `end` or `close` event."
In reply to: null

## Comment 7
Reviewer: copilot-pull-request-reviewer
File: src/services/product-service.ts
Line: 52
Body: "The method `getProductById` has a cache-aside pattern where it reads from cache, then falls back to DB. Consider extracting this pattern into a generic `cacheAside` utility function."
In reply to: null

## Comment 8
Reviewer: kate
File: src/services/product-service.ts
Line: 58
Body: "There's a race condition in the cache-aside pattern: two concurrent requests for the same uncached product will both miss the cache, both query the DB, and both write to the cache. The second write is wasted work but harmless. However, if the product is being updated between the two DB reads, the cache could end up with stale data from the first read while the second (newer) read gets discarded. Consider using a cache lock or at least `SET NX` semantics."
In reply to: null

## Comment 9
Reviewer: copilot-pull-request-reviewer
File: src/cache/invalidation.ts
Line: 1
Body: "Consider adding error handling for the Redis `publish` call in the `invalidate` method."
In reply to: null

## Comment 10
Reviewer: kate
File: src/cache/product-cache.ts
Line: 12
Body: "Love the approach of separating cache config by query type. Makes it easy to tune hot paths independently."
In reply to: null

# Source Context

## src/cache/product-cache.ts:1-55
```typescript
import { Redis } from 'ioredis';
import { CacheConfig, QueryType } from '../config/cache-config';

export class ProductCache {
  constructor(
    private redis: Redis,
    private config: CacheConfig
  ) {}

  private getKey(queryType: QueryType, params: Record<string, unknown>): string {
    return `product:${queryType}:${JSON.stringify(params)}`;
  }

  async get<T>(queryType: QueryType, params: Record<string, unknown>): Promise<T | null> {
    const key = this.getKey(queryType, params);
    const cached = await this.redis.get(key);
    if (cached === null) return null;
    return JSON.parse(cached) as T;
  }

  async set<T>(
    queryType: QueryType,
    params: Record<string, unknown>,
    value: T
  ): Promise<void> {
    const key = this.getKey(queryType, params);
    const ttl = this.config.ttl[queryType];
    await this.redis.set(key, JSON.stringify(value), 'EX', ttl);
  }

  async invalidate(queryType: QueryType, params?: Record<string, unknown>): Promise<void> {
    if (params) {
      const key = this.getKey(queryType, params);
      await this.redis.del(key);
    } else {
      // Invalidate all keys for this query type
      const pattern = `product:${queryType}:*`;
      const keys = await this.redis.keys(pattern);
      if (keys.length > 0) {
        for (const key of keys) {
          await this.redis.del(key);
        }
      }
    }
  }
}
```

## src/cache/invalidation.ts:1-40
```typescript
import { Redis } from 'ioredis';
import { ProductCache } from './product-cache';
import { QueryType } from '../config/cache-config';
import { Logger } from '../utils/logger';

const INVALIDATION_CHANNEL = 'product:invalidation';

interface InvalidationMessage {
  queryType: QueryType;
  productId?: string;
}

export class CacheInvalidator {
  private subscriber: Redis;

  constructor(
    private cache: ProductCache,
    private redis: Redis,
    private logger: Logger
  ) {
    this.subscriber = redis.duplicate();
    this.setupListener();
  }

  private setupListener(): void {
    this.subscriber.subscribe(INVALIDATION_CHANNEL);
    this.subscriber.on('message', async (channel, message) => {
      const { queryType, productId } = JSON.parse(message) as InvalidationMessage;
      await this.cache.invalidate(queryType, productId ? { id: productId } : undefined);
      this.logger.debug('Cache invalidated', { queryType, productId });
    });
    this.subscriber.on('error', (err) => {
      this.logger.error('Redis subscriber error', { error: err.message });
      this.subscriber.subscribe(INVALIDATION_CHANNEL);
    });
  }

  async publish(queryType: QueryType, productId?: string): Promise<void> {
    await this.redis.publish(
      INVALIDATION_CHANNEL,
      JSON.stringify({ queryType, productId })
    );
  }
}
```

## src/services/product-service.ts:45-70
```typescript
  async getProductById(id: string): Promise<Product | null> {
    // Try cache first
    const cached = await this.cache.get<Product>('byId', { id });
    if (cached) {
      this.logger.debug('Cache hit', { productId: id });
      return cached;
    }

    // Fallback to DB
    this.logger.debug('Cache miss', { productId: id });
    const product = await this.repo.findById(id);
    if (product) {
      await this.cache.set('byId', { id }, product);
    }
    return product;
  }

  async updateProduct(id: string, data: Partial<Product>): Promise<Product> {
    const updated = await this.repo.update(id, data);
    await this.invalidator.publish('byId', id);
    await this.invalidator.publish('list');
    return updated;
  }
```

## src/config/cache-config.ts:1-15
```typescript
export type QueryType = 'byId' | 'list' | 'search' | 'category';

export interface CacheConfig {
  ttl: Record<QueryType, number>;
}

export const defaultCacheConfig: CacheConfig = {
  ttl: {
    byId: 3600,
    list: 300,
    search: 600,
    category: 1800,
  },
};
```
