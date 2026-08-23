export type StoredConnection = {
  id: string;
  user_id: string;
  user_email: string;
  environment: "paper" | "live";
  encrypted_token: string;
  scope: string;
  connected_at: string;
  updated_at: string;
  revoked_at: string | null;
};

export type StoredOrderIntent = {
  id: string;
  user_id: string;
  environment: string;
  client_order_id: string;
  broker_order_id: string | null;
  symbol: string;
  side: string;
  quantity: number;
  order_type: string;
  time_in_force: string;
  limit_price: string | null;
  reference_price: string | null;
  notional: string | null;
  status: string;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

type D1Statement = {
  bind: (...values: unknown[]) => D1Statement;
  run: () => Promise<unknown>;
  first: <T>() => Promise<T | null>;
  all: <T>() => Promise<{ results: T[] }>;
};

type D1DatabaseLike = {
  prepare: (query: string) => D1Statement;
  batch: (statements: D1Statement[]) => Promise<unknown>;
};

type RuntimeEnv = { DB?: D1DatabaseLike };

/**
 * Cloudflare exposes the D1 binding through `cloudflare:workers`. The local
 * Node server does not implement that module, so the import must stay lazy:
 * local routes remain usable for UI/auth testing while deployed Workers use
 * the real persistent database.
 */
async function getDatabase(): Promise<D1DatabaseLike | null> {
  try {
    const workerModule = await import("cloudflare:workers");
    return (workerModule.env as unknown as RuntimeEnv).DB ?? null;
  } catch {
    return null;
  }
}

export async function hasTradingDatabase(): Promise<boolean> {
  return Boolean(await getDatabase());
}

let schemaPromise: Promise<void> | null = null;

export async function ensureTradingSchema(): Promise<boolean> {
  const db = await getDatabase();
  if (!db) return false;
  schemaPromise ??= db
    .batch([
      db.prepare(`CREATE TABLE IF NOT EXISTS alpaca_connections (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        user_email TEXT NOT NULL,
        environment TEXT NOT NULL CHECK (environment IN ('paper', 'live')),
        encrypted_token TEXT NOT NULL,
        scope TEXT NOT NULL DEFAULT 'data',
        connected_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        revoked_at TEXT
      )`),
      db.prepare("CREATE UNIQUE INDEX IF NOT EXISTS uq_alpaca_connections_user_environment ON alpaca_connections(user_id, environment)"),
      db.prepare("CREATE INDEX IF NOT EXISTS idx_alpaca_connections_user_id ON alpaca_connections(user_id)"),
      db.prepare(`CREATE TABLE IF NOT EXISTS order_intents (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        environment TEXT NOT NULL,
        client_order_id TEXT NOT NULL UNIQUE,
        broker_order_id TEXT,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        order_type TEXT NOT NULL,
        time_in_force TEXT NOT NULL,
        limit_price TEXT,
        reference_price TEXT,
        notional TEXT,
        status TEXT NOT NULL,
        error_code TEXT,
        error_message TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      )`),
      db.prepare("CREATE INDEX IF NOT EXISTS idx_order_intents_user_status ON order_intents(user_id, status)"),
      db.prepare("CREATE INDEX IF NOT EXISTS idx_order_intents_user_created_at ON order_intents(user_id, created_at)"),
      db.prepare(`CREATE TABLE IF NOT EXISTS execution_events (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        order_intent_id TEXT,
        event_type TEXT NOT NULL,
        status TEXT NOT NULL,
        broker_order_id TEXT,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL
      )`),
      db.prepare("CREATE INDEX IF NOT EXISTS idx_execution_events_user_created_at ON execution_events(user_id, created_at)"),
      db.prepare("CREATE INDEX IF NOT EXISTS idx_execution_events_order_intent_id ON execution_events(order_intent_id)"),
      db.prepare(`CREATE TABLE IF NOT EXISTS user_risk_controls (
        user_id TEXT PRIMARY KEY,
        paper_execution_enabled INTEGER NOT NULL DEFAULT 0,
        paper_kill_switch INTEGER NOT NULL DEFAULT 1,
        max_order_notional_usd TEXT NOT NULL DEFAULT '250',
        max_order_quantity INTEGER NOT NULL DEFAULT 5,
        allowed_symbols_json TEXT NOT NULL DEFAULT '[]',
        updated_at TEXT NOT NULL
      )`),
    ])
    .then(() => undefined);
  try {
    await schemaPromise;
    return true;
  } catch {
    schemaPromise = null;
    return false;
  }
}

export async function upsertAlpacaConnection(input: {
  userId: string;
  userEmail: string;
  environment: "paper" | "live";
  encryptedToken: string;
  scope: string;
  connectedAt: string;
}): Promise<boolean> {
  const db = await getDatabase();
  if (!db || !(await ensureTradingSchema())) return false;
  const id = crypto.randomUUID();
  const now = new Date().toISOString();
  await db
    .prepare(`INSERT INTO alpaca_connections
      (id, user_id, user_email, environment, encrypted_token, scope, connected_at, updated_at, revoked_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
      ON CONFLICT(user_id, environment) DO UPDATE SET
        user_email = excluded.user_email,
        encrypted_token = excluded.encrypted_token,
        scope = excluded.scope,
        connected_at = excluded.connected_at,
        updated_at = excluded.updated_at,
        revoked_at = NULL`)
    .bind(id, input.userId, input.userEmail, input.environment, input.encryptedToken, input.scope || "data", input.connectedAt, now)
    .run();
  return true;
}

export async function getAlpacaConnection(userId: string, environment: "paper" | "live"): Promise<StoredConnection | null> {
  const db = await getDatabase();
  if (!db || !(await ensureTradingSchema())) return null;
  const row = await db
    .prepare("SELECT * FROM alpaca_connections WHERE user_id = ? AND environment = ? AND revoked_at IS NULL LIMIT 1")
    .bind(userId, environment)
    .first<StoredConnection>();
  return row ?? null;
}

export async function listAlpacaConnections(userId: string): Promise<Array<Omit<StoredConnection, "encrypted_token">>> {
  const db = await getDatabase();
  if (!db || !(await ensureTradingSchema())) return [];
  const result = await db
    .prepare("SELECT id, user_id, user_email, environment, scope, connected_at, updated_at, revoked_at FROM alpaca_connections WHERE user_id = ? AND revoked_at IS NULL ORDER BY environment")
    .bind(userId)
    .all<Omit<StoredConnection, "encrypted_token">>();
  return result.results ?? [];
}

export async function revokeAlpacaConnection(userId: string, environment: "paper" | "live"): Promise<boolean> {
  const db = await getDatabase();
  if (!db || !(await ensureTradingSchema())) return false;
  await db
    .prepare("UPDATE alpaca_connections SET revoked_at = ?, updated_at = ? WHERE user_id = ? AND environment = ?")
    .bind(new Date().toISOString(), new Date().toISOString(), userId, environment)
    .run();
  return true;
}

export async function createOrderIntent(input: {
  id: string;
  userId: string;
  environment: string;
  clientOrderId: string;
  symbol: string;
  side: string;
  quantity: number;
  orderType: string;
  timeInForce: string;
  limitPrice: number | null;
  referencePrice: number | null;
  notional: number | null;
  status: string;
}): Promise<boolean> {
  const db = await getDatabase();
  if (!db || !(await ensureTradingSchema())) return false;
  const now = new Date().toISOString();
  await db
    .prepare(`INSERT INTO order_intents
      (id, user_id, environment, client_order_id, broker_order_id, symbol, side, quantity, order_type,
       time_in_force, limit_price, reference_price, notional, status, error_code, error_message, created_at, updated_at)
      VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)`)
    .bind(input.id, input.userId, input.environment, input.clientOrderId, input.symbol, input.side, input.quantity, input.orderType, input.timeInForce, input.limitPrice == null ? null : String(input.limitPrice), input.referencePrice == null ? null : String(input.referencePrice), input.notional == null ? null : String(input.notional), input.status, now, now)
    .run();
  await appendExecutionEvent({
    userId: input.userId,
    orderIntentId: input.id,
    eventType: "intent_created",
    status: input.status,
    payload: input,
  });
  return true;
}

export async function findOrderIntent(clientOrderId: string): Promise<StoredOrderIntent | null> {
  const db = await getDatabase();
  if (!db || !(await ensureTradingSchema())) return null;
  return (await db.prepare("SELECT * FROM order_intents WHERE client_order_id = ? LIMIT 1").bind(clientOrderId).first<StoredOrderIntent>()) ?? null;
}

export async function updateOrderIntent(input: {
  clientOrderId: string;
  userId: string;
  status: string;
  brokerOrderId?: string | null;
  errorCode?: string | null;
  errorMessage?: string | null;
  payload?: unknown;
  eventType?: string;
}): Promise<boolean> {
  const db = await getDatabase();
  if (!db || !(await ensureTradingSchema())) return false;
  const current = await findOrderIntent(input.clientOrderId);
  if (!current) return false;
  const now = new Date().toISOString();
  await db
    .prepare(`UPDATE order_intents SET status = ?, broker_order_id = COALESCE(?, broker_order_id),
      error_code = ?, error_message = ?, updated_at = ? WHERE client_order_id = ? AND user_id = ?`)
    .bind(input.status, input.brokerOrderId ?? null, input.errorCode ?? null, input.errorMessage ?? null, now, input.clientOrderId, input.userId)
    .run();
  if (current.status !== input.status || input.eventType) {
    await appendExecutionEvent({
      userId: input.userId,
      orderIntentId: current.id,
      eventType: input.eventType ?? "broker_status_changed",
      status: input.status,
      brokerOrderId: input.brokerOrderId ?? current.broker_order_id,
      payload: input.payload ?? {},
    });
  }
  return true;
}

export async function listOrderIntents(userId: string, limit = 100): Promise<StoredOrderIntent[]> {
  const db = await getDatabase();
  if (!db || !(await ensureTradingSchema())) return [];
  const boundedLimit = Math.min(200, Math.max(1, Math.floor(limit)));
  const result = await db
    .prepare("SELECT * FROM order_intents WHERE user_id = ? ORDER BY created_at DESC LIMIT ?")
    .bind(userId, boundedLimit)
    .all<StoredOrderIntent>();
  return result.results ?? [];
}

export async function appendExecutionEvent(input: {
  userId: string;
  orderIntentId?: string | null;
  eventType: string;
  status: string;
  brokerOrderId?: string | null;
  payload: unknown;
}): Promise<boolean> {
  const db = await getDatabase();
  if (!db || !(await ensureTradingSchema())) return false;
  await db
    .prepare(`INSERT INTO execution_events
      (id, user_id, order_intent_id, event_type, status, broker_order_id, payload_json, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)`)
    .bind(crypto.randomUUID(), input.userId, input.orderIntentId ?? null, input.eventType, input.status, input.brokerOrderId ?? null, JSON.stringify(input.payload ?? {}), new Date().toISOString())
    .run();
  return true;
}

export async function getUserRiskControls(userId: string): Promise<{
  paper_execution_enabled: boolean;
  paper_kill_switch: boolean;
  max_order_notional_usd: number;
  max_order_quantity: number;
  allowed_symbols: string[];
}> {
  const db = await getDatabase();
  if (db && (await ensureTradingSchema())) {
    const row = await db.prepare("SELECT * FROM user_risk_controls WHERE user_id = ? LIMIT 1").bind(userId).first<Record<string, unknown>>();
    if (row) {
      return {
        paper_execution_enabled: Number(row.paper_execution_enabled) === 1,
        paper_kill_switch: Number(row.paper_kill_switch) !== 0,
        max_order_notional_usd: Number(row.max_order_notional_usd) || 250,
        max_order_quantity: Number(row.max_order_quantity) || 5,
        allowed_symbols: parseSymbols(row.allowed_symbols_json),
      };
    }
  }
  return {
    paper_execution_enabled: false,
    paper_kill_switch: true,
    max_order_notional_usd: 250,
    max_order_quantity: 5,
    allowed_symbols: [],
  };
}

function parseSymbols(value: unknown): string[] {
  if (typeof value !== "string") return [];
  try {
    const parsed = JSON.parse(value) as unknown;
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [];
  } catch {
    return [];
  }
}
