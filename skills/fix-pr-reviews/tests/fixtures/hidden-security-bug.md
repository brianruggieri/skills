# PR Context
Title: Add admin endpoint for bulk user export
Description: |
  Adds a new `/admin/export-users` endpoint that returns a CSV of all users
  for compliance reporting. Requires admin role.

  ## Test Plan
  - [x] Unit tests for CSV formatting
  - [x] Integration test for endpoint auth
  - [ ] Manual test with 10k+ users
Files changed:
  - src/routes/admin.ts
  - src/services/export-service.ts (new)
  - tests/routes/admin.test.ts

# Review Comments

## Comment 1
Reviewer: copilot-pull-request-reviewer
File: src/services/export-service.ts
Line: 15
Body: "Consider adding input validation for the `fields` parameter to ensure only expected column names are used."
In reply to: null

## Comment 2
Reviewer: dave
File: src/routes/admin.ts
Line: 34
Body: "Looks good overall! Nice work on the streaming approach for large datasets."
In reply to: null

## Comment 3
Reviewer: copilot-pull-request-reviewer
File: src/services/export-service.ts
Line: 42
Body: "The `orderBy` parameter is concatenated directly into the SQL query string. Consider using parameterized queries or a whitelist to prevent potential SQL injection."
In reply to: null

## Comment 4
Reviewer: dave
File: src/routes/admin.ts
Line: 12
Body: "Nit: the route comment says 'GET /admin/users' but the actual route is '/admin/export-users'. Could you update the comment?"
In reply to: null

## Comment 5
Reviewer: eve
File: src/services/export-service.ts
Line: 8
Body: "Should we add rate limiting to this endpoint? Exporting all users could be expensive."
In reply to: null

## Comment 6
Reviewer: eve
File: src/routes/admin.ts
Line: 28
Body: "The auth middleware checks for 'admin' role, but our RBAC system uses 'admin:read' and 'admin:write' granular permissions now. This would let any admin export, including admin:write-only roles that shouldn't have read access."
In reply to: null

# Source Context

## src/services/export-service.ts:1-55
```typescript
import { Database } from '../db/connection';

interface ExportOptions {
  fields?: string[];
  orderBy?: string;
  format?: 'csv' | 'json';
}

export class ExportService {
  constructor(private db: Database) {}

  async exportUsers(options: ExportOptions = {}): Promise<string> {
    const fields = options.fields?.join(', ') || '*';
    const orderBy = options.orderBy || 'created_at DESC';
    const format = options.format || 'csv';

    const query = `SELECT ${fields} FROM users ORDER BY ${orderBy}`;
    const result = await this.db.query(query);

    if (format === 'csv') {
      return this.toCSV(result.rows);
    }
    return JSON.stringify(result.rows);
  }

  private toCSV(rows: Record<string, unknown>[]): string {
    if (rows.length === 0) return '';
    const headers = Object.keys(rows[0]);
    const lines = rows.map(row =>
      headers.map(h => {
        const val = String(row[h] ?? '');
        return val.includes(',') ? `"${val}"` : val;
      }).join(',')
    );
    return [headers.join(','), ...lines].join('\n');
  }

  async exportUserById(id: string): Promise<Record<string, unknown> | null> {
    const result = await this.db.query(
      'SELECT * FROM users WHERE id = $1',
      [id]
    );
    return result.rows[0] ?? null;
  }

  async countUsers(): Promise<number> {
    const result = await this.db.query('SELECT COUNT(*) FROM users');
    return parseInt(result.rows[0].count, 10);
  }
}
```

## src/routes/admin.ts:1-45
```typescript
import { Router, Request, Response } from 'express';
import { ExportService } from '../services/export-service';
import { requireRole } from '../middleware/auth';
import { Database } from '../db/connection';

const router = Router();
const db = new Database();
const exportService = new ExportService(db);

// GET /admin/users — export all users for compliance
router.get(
  '/admin/export-users',
  requireRole('admin'),
  async (req: Request, res: Response) => {
    try {
      const fields = req.query.fields
        ? (req.query.fields as string).split(',')
        : undefined;
      const orderBy = req.query.orderBy as string | undefined;
      const format = (req.query.format as 'csv' | 'json') || 'csv';

      const data = await exportService.exportUsers({
        fields,
        orderBy,
        format,
      });

      if (format === 'csv') {
        res.setHeader('Content-Type', 'text/csv');
        res.setHeader('Content-Disposition', 'attachment; filename=users.csv');
      }

      res.send(data);
    } catch (error) {
      console.error('Export failed:', error);
      res.status(500).json({ error: 'Export failed' });
    }
  }
);

export default router;
```
