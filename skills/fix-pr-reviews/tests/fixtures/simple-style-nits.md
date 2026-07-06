# PR Context
Title: Refactor user service to use repository pattern
Description: |
  Extracts database queries from UserService into UserRepository.
  No behavior changes — pure refactor.

  ## Test Plan
  - [x] All existing tests pass
  - [x] No new queries added
Files changed:
  - src/services/user-service.ts
  - src/repositories/user-repository.ts (new)
  - src/types/user.ts

# Review Comments

## Comment 1
Reviewer: alice
File: src/repositories/user-repository.ts
Line: 12
Body: "Nit: we use `camelCase` for method names in this repo, not `snake_case`. `find_by_id` should be `findById`."
In reply to: null

## Comment 2
Reviewer: alice
File: src/repositories/user-repository.ts
Line: 28
Body: "Unused import — `Logger` isn't referenced anywhere in this file."
In reply to: null

## Comment 3
Reviewer: bob
File: src/services/user-service.ts
Line: 5
Body: "Could you reorder these imports? We typically put third-party imports first, then internal modules."
In reply to: null

## Comment 4
Reviewer: alice
File: src/types/user.ts
Line: 1
Body: "Minor: the `User` type already exists in `@shared/types`. Consider re-exporting from there instead of redefining."
In reply to: null

## Comment 5
Reviewer: bob
File: src/repositories/user-repository.ts
Line: 45
Body: "Missing trailing comma after the last property. Our prettier config enforces this."
In reply to: null

# Source Context

## src/repositories/user-repository.ts:1-50
```typescript
import { Database } from '../db/connection';
import { Logger } from '../utils/logger';
import { User } from '../types/user';

export class UserRepository {
  constructor(private db: Database) {}

  async find_by_id(id: string): Promise<User | null> {
    const result = await this.db.query(
      'SELECT * FROM users WHERE id = $1',
      [id]
    );
    return result.rows[0] ?? null;
  }

  async findByEmail(email: string): Promise<User | null> {
    const result = await this.db.query(
      'SELECT * FROM users WHERE email = $1',
      [email]
    );
    return result.rows[0] ?? null;
  }

  async create(user: Omit<User, 'id'>): Promise<User> {
    const result = await this.db.query(
      'INSERT INTO users (name, email) VALUES ($1, $2) RETURNING *',
      [user.name, user.email]
    );
    return result.rows[0];
  }

  async update(id: string, data: Partial<User>): Promise<User | null> {
    const fields = Object.entries(data)
      .map(([key, _], i) => `${key} = $${i + 2}`)
      .join(', ');
    const values = Object.values(data);
    const result = await this.db.query(
      `UPDATE users SET ${fields} WHERE id = $1 RETURNING *`,
      [id, ...values]
    );
    return result.rows[0] ?? null;
  }
}
```

## src/services/user-service.ts:1-15
```typescript
import { UserRepository } from '../repositories/user-repository';
import { Logger } from '../utils/logger';
import { EventEmitter } from 'events';
import { z } from 'zod';
import { Config } from '../config';

export class UserService {
  private repo: UserRepository;
  private logger: Logger;

  constructor(repo: UserRepository, logger: Logger) {
    this.repo = repo;
    this.logger = logger;
  }
}
```

## src/types/user.ts:1-8
```typescript
export interface User {
  id: string;
  name: string;
  email: string;
  createdAt: Date;
  updatedAt: Date;
}
```
