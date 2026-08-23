import { getChatGPTUser } from "./chatgpt-auth";

export type DirectAlpacaConfig = {
  configured: boolean;
  missing: string[];
  executionEnv: "paper" | "invalid";
  marketDataFeed: "iex" | "invalid";
  realtimeEnabled: boolean;
  executionEnabled: boolean;
  paperEnabled: boolean;
  liveEnabled: boolean;
  killSwitch: boolean;
  maxOrderNotionalUsd: number;
  maxOrderQuantity: number;
  allowedSymbols: string[];
};

export type DirectQuote = {
  symbol: string;
  bid_price: number | null;
  bid_size: number | null;
  ask_price: number | null;
  ask_size: number | null;
  last_price: number | null;
  last_size: number | null;
  event_time: string | null;
  receive_time_utc: string;
};

export type RealtimeQuote = {
  quote: DirectQuote;
  transport: "websocket" | "rest";
  realtime_active: boolean;
  latency_ms: number | null;
  data_age_seconds: number | null;
  observed_at: string;
  message: string;
};

export class AlpacaDirectError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(code: string, message: string, status = 503) {
    super(message);
    this.name = "AlpacaDirectError";
    this.code = code;
    this.status = status;
  }
}

const PAPER_TRADING_URL = "https://paper-api.alpaca.markets";
const MARKET_DATA_URL = "https://data.alpaca.markets";
const IEX_STREAM_URL = "wss://stream.data.alpaca.markets/v2/iex";
const DEFAULT_SYMBOLS = ["SPY", "IWM", "EFA", "TLT", "GLD"];

function env(name: string): string | null {
  const value = process.env[name]?.trim();
  return value || null;
}

function booleanEnv(name: string, fallback: boolean): boolean {
  const value = env(name)?.toLowerCase();
  if (!value) return fallback;
  return ["1", "true", "yes", "on"].includes(value);
}

function numberEnv(name: string, fallback: number): number {
  const value = Number(env(name) ?? "");
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function parseSymbols(): string[] {
  const configured = (env("TRADINGLAB_ALLOWED_SYMBOLS") ?? DEFAULT_SYMBOLS.join(","))
    .split(",")
    .map((symbol) => symbol.trim().toUpperCase())
    .filter((symbol) => /^[A-Z0-9.-]{1,15}$/.test(symbol));
  return configured.length ? [...new Set(configured)] : DEFAULT_SYMBOLS;
}

export function getDirectAlpacaConfig(): DirectAlpacaConfig {
  const required = ["ALPACA_API_KEY", "ALPACA_API_SECRET"];
  const missing = required.filter((name) => !env(name));
  const executionEnv = env("TRADINGLAB_EXECUTION_ENV") === "paper" ? "paper" : "invalid";
  const marketDataFeed = env("TRADINGLAB_MARKET_DATA_FEED") === "iex" ? "iex" : "invalid";
  const liveEnabled = booleanEnv("TRADINGLAB_LIVE_ENABLED", false);
  const killSwitch = booleanEnv("TRADINGLAB_KILL_SWITCH", true);

  return {
    configured: missing.length === 0 && executionEnv === "paper" && marketDataFeed === "iex" && !liveEnabled,
    missing,
    executionEnv,
    marketDataFeed,
    realtimeEnabled: booleanEnv("TRADINGLAB_REALTIME_ENABLED", false),
    executionEnabled: booleanEnv("TRADINGLAB_EXECUTION_ENABLED", false),
    paperEnabled: booleanEnv("TRADINGLAB_PAPER_ENABLED", false),
    liveEnabled,
    killSwitch,
    maxOrderNotionalUsd: numberEnv("TRADINGLAB_MAX_ORDER_NOTIONAL_USD", 500),
    maxOrderQuantity: Math.floor(numberEnv("TRADINGLAB_MAX_ORDER_QUANTITY", 10)),
    allowedSymbols: parseSymbols(),
  };
}

export function publicDirectConfig(): Omit<DirectAlpacaConfig, "missing"> & { missing: string[] } {
  return getDirectAlpacaConfig();
}

export async function isOwnerRequest(request: Request): Promise<boolean> {
  const user = await getChatGPTUser();
  const configuredId = env("TRADINGLAB_OWNER_USER_ID");
  const configuredEmail = env("TRADINGLAB_OWNER_EMAIL")?.toLowerCase();
  if (
    user &&
    ((configuredId && user.userId === configuredId) ||
      (configuredEmail && user.email.toLowerCase() === configuredEmail))
  ) {
    return true;
  }

  if (!user) {
    const hostname = new URL(request.url).hostname;
    return hostname === "localhost" || hostname === "127.0.0.1";
  }
  return false;
}

export function requireConfiguredPaper(): DirectAlpacaConfig {
  const config = getDirectAlpacaConfig();
  if (!config.configured) {
    throw new AlpacaDirectError(
      "alpaca_paper_not_configured",
      "A conexão direta Paper está incompleta ou não está em modo seguro.",
    );
  }
  return config;
}

export function requireOrderCapability(): DirectAlpacaConfig {
  const config = requireConfiguredPaper();
  if (config.killSwitch) {
    throw new AlpacaDirectError("kill_switch_active", "Kill switch ativo: novas ordens estão bloqueadas.", 423);
  }
  if (!config.executionEnabled || !config.paperEnabled) {
    throw new AlpacaDirectError(
      "paper_execution_disabled",
      "A execução Paper está desativada nas configurações do backend.",
      423,
    );
  }
  return config;
}

function apiHeaders(): HeadersInit {
  const key = env("ALPACA_API_KEY");
  const secret = env("ALPACA_API_SECRET");
  if (!key || !secret) throw new AlpacaDirectError("alpaca_credentials_missing", "Credenciais Paper ausentes.");
  return {
    Accept: "application/json",
    "APCA-API-KEY-ID": key,
    "APCA-API-SECRET-KEY": secret,
  };
}

async function fetchWithTimeout(input: string, init: RequestInit, timeoutMs = 9000): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new AlpacaDirectError("alpaca_timeout", "A Alpaca não respondeu dentro do tempo limite.", 504);
    }
    throw new AlpacaDirectError("alpaca_network_error", "Não foi possível alcançar a Alpaca.", 502);
  } finally {
    clearTimeout(timeout);
  }
}

async function readJson(response: Response): Promise<Record<string, unknown>> {
  try {
    const payload: unknown = await response.json();
    return payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

export async function alpacaJson(
  path: string,
  init: RequestInit = {},
  baseUrl: string = PAPER_TRADING_URL,
): Promise<Record<string, unknown>> {
  requireConfiguredPaper();
  const response = await fetchWithTimeout(`${baseUrl}${path}`, {
    ...init,
    headers: { ...apiHeaders(), ...(init.headers ?? {}) },
  });
  const payload = await readJson(response);
  if (!response.ok) {
    const providerMessage = typeof payload.message === "string" ? payload.message : "resposta recusada";
    throw new AlpacaDirectError("alpaca_provider_error", `Alpaca recusou a solicitação: ${providerMessage}.`, response.status >= 500 ? 502 : 400);
  }
  return payload;
}

function asNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value ? value : null;
}

export function normalizeQuote(symbol: string, payload: Record<string, unknown>, receivedAt = new Date()): DirectQuote {
  const quote = (payload.quote && typeof payload.quote === "object" ? payload.quote : payload) as Record<string, unknown>;
  const trade = (payload.trade && typeof payload.trade === "object" ? payload.trade : {}) as Record<string, unknown>;
  return {
    symbol,
    bid_price: asNumber(quote.bp),
    bid_size: asNumber(quote.bs),
    ask_price: asNumber(quote.ap),
    ask_size: asNumber(quote.as),
    last_price: asNumber(trade.p),
    last_size: asNumber(trade.s),
    event_time: asString(quote.t) ?? asString(trade.t),
    receive_time_utc: receivedAt.toISOString(),
  };
}

export function quoteLatency(quote: DirectQuote): number | null {
  if (!quote.event_time) return null;
  const eventTime = Date.parse(quote.event_time);
  const receivedTime = Date.parse(quote.receive_time_utc);
  if (!Number.isFinite(eventTime) || !Number.isFinite(receivedTime)) return null;
  return Math.max(0, receivedTime - eventTime);
}

function quoteAgeSeconds(quote: DirectQuote): number | null {
  if (!quote.event_time) return null;
  const eventTime = Date.parse(quote.event_time);
  const receivedTime = Date.parse(quote.receive_time_utc);
  if (!Number.isFinite(eventTime) || !Number.isFinite(receivedTime)) return null;
  return Math.max(0, (receivedTime - eventTime) / 1000);
}

export async function restQuote(symbol: string): Promise<RealtimeQuote> {
  const normalized = normalizeSymbol(symbol);
  const receivedAt = new Date();
  const payload = await alpacaJson(
    `/v2/stocks/${encodeURIComponent(normalized)}/quotes/latest?feed=iex`,
    {},
    MARKET_DATA_URL,
  );
  const quote = normalizeQuote(normalized, payload, receivedAt);
  return {
    quote,
    transport: "rest",
    realtime_active: Boolean(quote.event_time),
    latency_ms: quoteAgeSeconds(quote) != null && quoteAgeSeconds(quote)! <= 60 ? quoteLatency(quote) : null,
    data_age_seconds: quoteAgeSeconds(quote),
    observed_at: receivedAt.toISOString(),
    message: "Cotação recebida pela Market Data API da Alpaca no feed IEX.",
  };
}

type AlpacaSocketMessage = {
  T?: string;
  msg?: string;
  code?: number;
  S?: string;
  bp?: number;
  bs?: number;
  ap?: number;
  as?: number;
  t?: string;
};

export async function websocketQuote(symbol: string): Promise<RealtimeQuote> {
  const config = requireConfiguredPaper();
  if (!config.realtimeEnabled) {
    throw new AlpacaDirectError("realtime_disabled", "O realtime está desativado nas configurações.", 423);
  }
  const normalized = normalizeSymbol(symbol);
  return new Promise((resolve, reject) => {
    let socket: WebSocket | null = null;
    let settled = false;
    const finish = (callback: () => void) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      try {
        socket?.close();
      } catch {
        // Closing an already closed provider socket is harmless.
      }
      callback();
    };
    const timeout = setTimeout(() => finish(() => reject(new AlpacaDirectError("alpaca_websocket_timeout", "O WebSocket da Alpaca não entregou uma cotação a tempo.", 504))), 10000);

    try {
      socket = new WebSocket(IEX_STREAM_URL);
      socket.addEventListener("open", () => {
        socket?.send(JSON.stringify({ action: "auth", key: env("ALPACA_API_KEY"), secret: env("ALPACA_API_SECRET") }));
      });
      socket.addEventListener("message", (event) => {
        let messages: AlpacaSocketMessage[];
        try {
          const parsed: unknown = JSON.parse(String(event.data));
          messages = Array.isArray(parsed) ? (parsed as AlpacaSocketMessage[]) : [parsed as AlpacaSocketMessage];
        } catch {
          return;
        }
        for (const message of messages) {
          if (message.T === "error") {
            finish(() => reject(new AlpacaDirectError("alpaca_websocket_provider_error", "O WebSocket da Alpaca recusou a conexão.", 502)));
            return;
          }
          if (message.T === "success" && message.msg === "authenticated") {
            socket?.send(JSON.stringify({ action: "subscribe", quotes: [normalized] }));
          }
          if (message.T === "q" && message.S === normalized) {
            const receivedAt = new Date();
            const quote = normalizeQuote(normalized, { quote: message }, receivedAt);
            finish(() => resolve({
              quote,
              transport: "websocket",
              realtime_active: true,
              latency_ms: quoteLatency(quote),
              data_age_seconds: quoteAgeSeconds(quote),
              observed_at: receivedAt.toISOString(),
              message: "Cotação recebida pelo WebSocket da Alpaca no feed IEX.",
            }));
            return;
          }
        }
      });
      socket.addEventListener("error", () => finish(() => reject(new AlpacaDirectError("alpaca_websocket_error", "Não foi possível abrir o WebSocket da Alpaca.", 502))));
      socket.addEventListener("close", () => {
        if (!settled) finish(() => reject(new AlpacaDirectError("alpaca_websocket_closed", "O WebSocket da Alpaca foi encerrado antes da primeira cotação.", 502)));
      });
    } catch {
      finish(() => reject(new AlpacaDirectError("alpaca_websocket_unavailable", "O runtime não conseguiu abrir o WebSocket da Alpaca.", 502)));
    }
  });
}

export async function liveQuote(symbol: string): Promise<RealtimeQuote> {
  try {
    return await websocketQuote(symbol);
  } catch (error) {
    if (!(error instanceof AlpacaDirectError)) throw error;
    const fallback = await restQuote(symbol);
    return {
      ...fallback,
      message: `${error.message} Fallback REST entregue; realtime_active=false para não mascarar a falha do WebSocket.`,
      realtime_active: false,
      latency_ms: null,
    };
  }
}

export function normalizeSymbol(value: string): string {
  const symbol = value.trim().toUpperCase();
  if (!/^[A-Z0-9.-]{1,15}$/.test(symbol)) {
    throw new AlpacaDirectError("invalid_symbol", "Ativo inválido.", 400);
  }
  const config = getDirectAlpacaConfig();
  if (!config.allowedSymbols.includes(symbol)) {
    throw new AlpacaDirectError("symbol_not_allowed", "Este ativo não está na allowlist Paper.", 400);
  }
  return symbol;
}

export function errorResponse(error: unknown): Response {
  if (error instanceof AlpacaDirectError) {
    return Response.json({ error: error.code, message: error.message }, { status: error.status });
  }
  return Response.json({ error: "internal_error", message: "Não foi possível concluir a operação Paper." }, { status: 500 });
}

export function safeOrderId(value: string): string {
  if (!/^[A-Za-z0-9._-]{1,64}$/.test(value)) {
    throw new AlpacaDirectError("invalid_order_id", "Identificador de ordem inválido.", 400);
  }
  return value;
}
