CREATE TABLE `alpaca_connections` (
	`id` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`user_email` text NOT NULL,
	`environment` text NOT NULL,
	`encrypted_token` text NOT NULL,
	`scope` text DEFAULT 'data' NOT NULL,
	`connected_at` text NOT NULL,
	`updated_at` text NOT NULL,
	`revoked_at` text
);
--> statement-breakpoint
CREATE UNIQUE INDEX `uq_alpaca_connections_user_environment` ON `alpaca_connections` (`user_id`,`environment`);--> statement-breakpoint
CREATE INDEX `idx_alpaca_connections_user_id` ON `alpaca_connections` (`user_id`);--> statement-breakpoint
CREATE TABLE `execution_events` (
	`id` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`order_intent_id` text,
	`event_type` text NOT NULL,
	`status` text NOT NULL,
	`broker_order_id` text,
	`payload_json` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_execution_events_user_created_at` ON `execution_events` (`user_id`,`created_at`);--> statement-breakpoint
CREATE INDEX `idx_execution_events_order_intent_id` ON `execution_events` (`order_intent_id`);--> statement-breakpoint
CREATE TABLE `order_intents` (
	`id` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`environment` text NOT NULL,
	`client_order_id` text NOT NULL,
	`broker_order_id` text,
	`symbol` text NOT NULL,
	`side` text NOT NULL,
	`quantity` integer NOT NULL,
	`order_type` text NOT NULL,
	`time_in_force` text NOT NULL,
	`limit_price` text,
	`reference_price` text,
	`notional` text,
	`status` text NOT NULL,
	`error_code` text,
	`error_message` text,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `uq_order_intents_client_order_id` ON `order_intents` (`client_order_id`);--> statement-breakpoint
CREATE INDEX `idx_order_intents_user_status` ON `order_intents` (`user_id`,`status`);--> statement-breakpoint
CREATE INDEX `idx_order_intents_user_created_at` ON `order_intents` (`user_id`,`created_at`);--> statement-breakpoint
CREATE TABLE `user_risk_controls` (
	`user_id` text PRIMARY KEY NOT NULL,
	`paper_execution_enabled` integer DEFAULT 0 NOT NULL,
	`paper_kill_switch` integer DEFAULT 1 NOT NULL,
	`max_order_notional_usd` text DEFAULT '250' NOT NULL,
	`max_order_quantity` integer DEFAULT 5 NOT NULL,
	`allowed_symbols_json` text DEFAULT '[]' NOT NULL,
	`updated_at` text NOT NULL
);
