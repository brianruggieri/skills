# PR Context
Title: Add WebSocket support for real-time notifications
Description: |
  Implements WebSocket server for pushing real-time notifications to connected
  clients. Uses ws library with per-user connection tracking.

  ## Test Plan
  - [x] Unit tests for connection manager
  - [x] Unit tests for message serialization
  - [ ] Load test with 1000 concurrent connections
Files changed:
  - src/ws/server.ts (new)
  - src/ws/connection-manager.ts (new)
  - src/ws/handlers.ts (new)
  - tests/ws/server.test.ts (new)

# Review Comments

## Comment 1
Reviewer: henry
File: src/ws/connection-manager.ts
Line: 15
Body: "You're storing connections in a plain `Map<string, WebSocket>`. This won't scale past a single process. When we add a second server instance behind the load balancer, users connected to server A won't get messages sent from server B."
In reply to: null

## Comment 2
Reviewer: iris
File: src/ws/connection-manager.ts
Line: 15
Body: "Henry's right about multi-process. The standard fix is Redis pub/sub for cross-instance messaging. But is that in scope for this PR? We're single-instance right now."
In reply to: 1

## Comment 3
Reviewer: henry
File: src/ws/connection-manager.ts
Line: 15
Body: "Fair point. Single-instance for now is fine, but can we at least add a TODO and abstract behind an interface so swapping in Redis later isn't a rewrite?"
In reply to: 2

## Comment 4
Reviewer: iris
File: src/ws/connection-manager.ts
Line: 15
Body: "Yeah, an interface makes sense. `ConnectionBroadcaster` with `send(userId, message)` and `broadcast(message)`. The Map implementation is the default, Redis can be added later."
In reply to: 3

## Comment 5
Reviewer: henry
File: src/ws/connection-manager.ts
Line: 15
Body: "Agreed. Let's go with that. @author — extract an interface and rename this class to `LocalConnectionManager`."
In reply to: 4

## Comment 6
Reviewer: henry
File: src/ws/server.ts
Line: 8
Body: "The heartbeat interval is set to 30 seconds but you're not checking for pong responses. A client that disconnects without closing the connection will stay in the map forever. You need to track `isAlive` and terminate dead connections."
In reply to: null

## Comment 7
Reviewer: iris
File: src/ws/handlers.ts
Line: 22
Body: "The `onMessage` handler parses JSON but doesn't validate the schema. A malformed message will crash the handler with an unhandled exception, which could kill the connection for that user."
In reply to: null

## Comment 8
Reviewer: henry
File: src/ws/handlers.ts
Line: 22
Body: "To add to Iris's point — the error from JSON.parse is caught, but the shape validation happens after, and that's not wrapped in a try/catch. So `message.type` on a valid JSON that isn't an object will throw."
In reply to: 7

## Comment 9
Reviewer: iris
File: src/ws/handlers.ts
Line: 22
Body: "Yep. Wrap the whole handler in try/catch + send an error frame back to the client instead of crashing."
In reply to: 8

## Comment 10
Reviewer: henry
File: src/ws/server.ts
Line: 45
Body: "Nice job on the graceful shutdown — iterating all connections and sending close frames before process.exit. Haven't seen that done correctly in a while."
In reply to: null

# Source Context

## src/ws/connection-manager.ts:1-45
```typescript
import { WebSocket } from 'ws';

interface Connection {
  ws: WebSocket;
  userId: string;
  connectedAt: Date;
}

export class ConnectionManager {
  private connections = new Map<string, Connection>();

  add(userId: string, ws: WebSocket): void {
    // Close existing connection for this user (single-tab policy)
    const existing = this.connections.get(userId);
    if (existing) {
      existing.ws.close(1000, 'New connection opened');
    }
    this.connections.set(userId, { ws, userId, connectedAt: new Date() });
  }

  remove(userId: string): void {
    this.connections.delete(userId);
  }

  send(userId: string, message: unknown): boolean {
    const conn = this.connections.get(userId);
    if (!conn || conn.ws.readyState !== WebSocket.OPEN) return false;
    conn.ws.send(JSON.stringify(message));
    return true;
  }

  broadcast(message: unknown): void {
    const payload = JSON.stringify(message);
    for (const conn of this.connections.values()) {
      if (conn.ws.readyState === WebSocket.OPEN) {
        conn.ws.send(payload);
      }
    }
  }

  get count(): number {
    return this.connections.size;
  }
}
```

## src/ws/server.ts:1-50
```typescript
import { WebSocketServer, WebSocket } from 'ws';
import { ConnectionManager } from './connection-manager';
import { handleMessage } from './handlers';
import { Logger } from '../utils/logger';

const HEARTBEAT_INTERVAL = 30_000;

export function createWSServer(port: number, logger: Logger) {
  const wss = new WebSocketServer({ port });
  const manager = new ConnectionManager();

  const heartbeat = setInterval(() => {
    wss.clients.forEach((ws: WebSocket) => {
      ws.ping();
    });
  }, HEARTBEAT_INTERVAL);

  wss.on('connection', (ws: WebSocket, req) => {
    const userId = req.headers['x-user-id'] as string;
    if (!userId) {
      ws.close(1008, 'Missing user ID');
      return;
    }

    manager.add(userId, ws);
    logger.info('WebSocket connected', { userId });

    ws.on('message', (data) => {
      handleMessage(manager, userId, data.toString(), logger);
    });

    ws.on('close', () => {
      manager.remove(userId);
      logger.info('WebSocket disconnected', { userId });
    });
  });

  process.on('SIGTERM', () => {
    clearInterval(heartbeat);
    wss.clients.forEach((ws) => {
      ws.close(1001, 'Server shutting down');
    });
    wss.close(() => {
      logger.info('WebSocket server closed');
      process.exit(0);
    });
  });

  return { wss, manager };
}
```

## src/ws/handlers.ts:1-40
```typescript
import { ConnectionManager } from './connection-manager';
import { Logger } from '../utils/logger';

interface WSMessage {
  type: string;
  payload?: unknown;
}

export function handleMessage(
  manager: ConnectionManager,
  userId: string,
  raw: string,
  logger: Logger
): void {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    logger.warn('Invalid JSON from client', { userId });
    return;
  }

  const message = parsed as WSMessage;

  switch (message.type) {
    case 'ping':
      manager.send(userId, { type: 'pong' });
      break;
    case 'subscribe':
      logger.info('User subscribed to channel', {
        userId,
        channel: message.payload,
      });
      break;
    default:
      logger.warn('Unknown message type', { userId, type: message.type });
  }
}
```
