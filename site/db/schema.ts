import { index, integer, sqliteTable, text, uniqueIndex } from "drizzle-orm/sqlite-core";

export const alpacaConnections = sqliteTable(
  "alpaca_connections",
  {
    id: text("id").primaryKey(),
    userId: text("user_id").notNull(),
    userEmail: text("user_email").notNull(),
    environment: text("environment").notNull(),
    encryptedToken: text("encrypted_token").notNull(),
    scope: text("scope").notNull().default("data"),
    connectedAt: text("connected_at").notNull(),
    updatedAt: text("updated_at").notNull(),
    revokedAt: text("revoked_at"),
  },
  (table) => ({
    userEnvironmentUnique: uniqueIndex("uq_alpaca_connections_user_environment").on(
      table.userId,
      table.environment,
    ),
    userIndex: index("idx_alpaca_connections_user_id").on(table.userId),
  }),
);

export const orderIntents = sqliteTable(
  "order_intents",
  {
    id: text("id").primaryKey(),
    userId: text("user_id").notNull(),
    environment: text("environment").notNull(),
    clientOrderId: text("client_order_id").notNull(),
    brokerOrderId: text("broker_order_id"),
    symbol: text("symbol").notNull(),
    side: text("side").notNull(),
    quantity: integer("quantity").notNull(),
    orderType: text("order_type").notNull(),
    timeInForce: text("time_in_force").notNull(),
    limitPrice: text("limit_price"),
    referencePrice: text("reference_price"),
    notional: text("notional"),
    status: text("status").notNull(),
    errorCode: text("error_code"),
    errorMessage: text("error_message"),
    createdAt: text("created_at").notNull(),
    updatedAt: text("updated_at").notNull(),
  },
  (table) => ({
    clientOrderUnique: uniqueIndex("uq_order_intents_client_order_id").on(table.clientOrderId),
    userStatusIndex: index("idx_order_intents_user_status").on(table.userId, table.status),
    userCreatedIndex: index("idx_order_intents_user_created_at").on(table.userId, table.createdAt),
  }),
);

export const executionEvents = sqliteTable(
  "execution_events",
  {
    id: text("id").primaryKey(),
    userId: text("user_id").notNull(),
    orderIntentId: text("order_intent_id"),
    eventType: text("event_type").notNull(),
    status: text("status").notNull(),
    brokerOrderId: text("broker_order_id"),
    payloadJson: text("payload_json").notNull(),
    createdAt: text("created_at").notNull(),
  },
  (table) => ({
    userCreatedIndex: index("idx_execution_events_user_created_at").on(table.userId, table.createdAt),
    orderIndex: index("idx_execution_events_order_intent_id").on(table.orderIntentId),
  }),
);

export const userRiskControls = sqliteTable("user_risk_controls", {
  userId: text("user_id").primaryKey(),
  paperExecutionEnabled: integer("paper_execution_enabled").notNull().default(0),
  paperKillSwitch: integer("paper_kill_switch").notNull().default(1),
  maxOrderNotionalUsd: text("max_order_notional_usd").notNull().default("250"),
  maxOrderQuantity: integer("max_order_quantity").notNull().default(5),
  allowedSymbolsJson: text("allowed_symbols_json").notNull().default("[]"),
  updatedAt: text("updated_at").notNull(),
});
