import { getChatGPTUser, type ChatGPTUser } from "./chatgpt-auth";
import {
  getStoredTokenForEnvironment,
  type AlpacaOAuthEnvironment,
  type AlpacaToken,
} from "./alpaca-oauth";
import { normalizeQuote, quoteLatency, type DirectQuote } from "./alpaca-direct";

const PAPER_TRADING_URL = "https://paper-api.alpaca.markets";
const LIVE_TRADING_URL = "https://api.alpaca.markets";
const MARKET_DATA_URL = "https://data.alpaca.markets";
const DEFAULT_SYMBOLS = ["SPY", "IWM", "EFA", "TLT", "GLD"];

export type UserAlpacaConfig = {
  paperExecutionEnabled: boolean;
  paperKillSwitch: boolean;
  liveExecutionEnabled: boolean;
  liveKillSwitch: boolean;
  maxOrderNotionalUsd: number;
  maxOrderQuantity: number;
  allowedSymbols: string[];
};

export type UserRealtimeQuote = {
  quote: DirectQuote;
  transport: "rest";
  realtime_active: false;
  latency_ms: null;
  data_age_seconds: number | null;
  observed_at: string;
  message: string;
};

export class UserAlpacaError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status = 503) {
    super(message);
    this.name = "UserAlpacaError";
    this.code = code;
    this.status = status;
  }
}

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
  const parsed = Number(env(name) ?? "");
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function symbolsFromEnv(): string[] {
  const configured = (env("TRADINGLAB_OAUTH_ALLOWED_SYMBOLS") ?? DEFAULT_SYMBOLS.join(","))
    .split(",")
    .map((symbol) => symbol.trim().toUpperCase())
    .filter((symbol) => /^[A-Z0-9.-]{1,15}$/.test(symbol));
  return configured.length ? [...new Set(configured)] : DEFAULT_SYMBOLS;
}

export function getUserAlpacaConfig(): UserAlpacaConfig {
  return {
    paperExecutionEnabled: booleanEnv("TRADINGLAB_OAUTH_PAPER_EXECUTION_ENABLED", false),
    paperKillSwitch: booleanEnv("TRADINGLAB_OAUTH_PAPER_KILL_SWITCH", true),
    liveExecutionEnabled: booleanEnv("TRADINGLAB_OAUTH_LIVE_EXECUTION_ENABLED", false),
    liveKillSwitch: booleanEnv("TRADINGLAB_OAUTH_LIVE_KILL_SWITCH", true),
    maxOrderNotionalUsd: numberEnv("TRADINGLAB_OAUTH_MAX_ORDER_NOTIONAL_USD", 250),
    maxOrderQuantity: Math.floor(numberEnv("TRADINGLAB_OAUTH_MAX_ORDER_QUANTITY", 5)),
    allowedSymbols: symbolsFromEnv(),
  };
}

function configuredAllowlist(name: string): string[] {
  return (env(name) ?? "")
    .split(",")
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);
}

export function isPaperPilotUser(user: ChatGPTUser): boolean {
  const emails = configuredAllowlist("TRADINGLAB_OAUTH_PAPER_ALLOWED_USER_EMAILS");
  const userIds = configuredAllowlist("TRADINGLAB_OAUTH_PAPER_ALLOWED_USER_IDS");
  return emails.includes(user.email.toLowerCase()) || userIds.includes(user.userId.toLowerCase());
}

export function scopeAllows(token: AlpacaToken, scope: "data" | "trading"): boolean {
  const scopes = (token.scope ?? "").split(/\s+/).filter(Boolean);
  return scopes.includes(scope);
}

export function normalizeUserSymbol(value: string): string {
  const symbol = value.trim().toUpperCase();
  if (!/^[A-Z0-9.-]{1,15}$/.test(symbol)) {
    throw new UserAlpacaError("invalid_symbol", "Ativo inválido.", 400);
  }
  if (!getUserAlpacaConfig().allowedSymbols.includes(symbol)) {
    throw new UserAlpacaError("symbol_not_allowed", "Este ativo não está na allowlist do piloto Paper.", 400);
  }
  return symbol;
}

async function getToken(userId: string, environment: AlpacaOAuthEnvironment): Promise<AlpacaToken> {
  const token = await getStoredTokenForEnvironment(userId, environment);
  if (!token) {
    throw new UserAlpacaError(
      "alpaca_not_connected",
      `Nenhuma conta Alpaca ${environment === "paper" ? "Paper" : "Live"} está conectada a este usuário.`,
      409,
    );
  }
  return token;
}

export async function requireUser(user?: ChatGPTUser | null): Promise<ChatGPTUser> {
  const current = user ?? (await getChatGPTUser());
  if (!current) throw new UserAlpacaError("authentication_required", "Faça login com ChatGPT para continuar.", 401);
  return current;
}

function tradingBaseUrl(environment: AlpacaOAuthEnvironment): string {
  return environment === "paper" ? PAPER_TRADING_URL : LIVE_TRADING_URL;
}

async function requestJson<T>(
  token: AlpacaToken,
  environment: AlpacaOAuthEnvironment,
  path: string,
  init: RequestInit = {},
  baseUrl = tradingBaseUrl(environment),
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 9000);
  try {
    const response = await fetch(`${baseUrl}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token.access_token}`,
        ...(init.headers ?? {}),
      },
    });
    let payload: unknown = {};
    try {
      payload = await response.json();
    } catch {
      payload = {};
    }
    if (!response.ok) {
      const record = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};
      const message = typeof record.message === "string" ? record.message : "resposta recusada pela Alpaca";
      throw new UserAlpacaError("alpaca_provider_error", `A Alpaca recusou a solicitação: ${message}.`, response.status >= 500 ? 502 : response.status);
    }
    return payload as T;
  } catch (error) {
    if (error instanceof UserAlpacaError) throw error;
    if (error instanceof Error && error.name === "AbortError") {
      throw new UserAlpacaError("alpaca_timeout", "A Alpaca não respondeu dentro do tempo limite.", 504);
    }
    throw new UserAlpacaError("alpaca_network_error", "Não foi possível alcançar a Alpaca.", 502);
  } finally {
    clearTimeout(timeout);
  }
}

export async function userTradingJson<T>(
  userId: string,
  environment: AlpacaOAuthEnvironment,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = await getToken(userId, environment);
  return requestJson<T>(token, environment, path, init);
}

export async function userMarketJson<T>(
  userId: string,
  environment: AlpacaOAuthEnvironment,
  path: string,
): Promise<T> {
  const token = await getToken(userId, environment);
  if (!scopeAllows(token, "data")) {
    throw new UserAlpacaError("market_data_scope_required", "A conexão não possui autorização de dados de mercado.", 403);
  }
  return requestJson<T>(token, environment, path, {}, MARKET_DATA_URL);
}

export async function userQuote(userId: string, environment: AlpacaOAuthEnvironment, symbol: string): Promise<UserRealtimeQuote> {
  const normalized = normalizeUserSymbol(symbol);
  const receivedAt = new Date();
  const payload = await userMarketJson<Record<string, unknown>>(
    userId,
    environment,
    `/v2/stocks/${encodeURIComponent(normalized)}/quotes/latest?feed=iex`,
  );
  const quote = normalizeQuote(normalized, payload, receivedAt);
  const latency = quoteLatency(quote);
  return {
    quote,
    transport: "rest",
    realtime_active: false,
    latency_ms: null,
    data_age_seconds: latency == null ? null : latency / 1000,
    observed_at: receivedAt.toISOString(),
    message: "Cotação da Alpaca IEX recebida por REST. O stream contínuo do usuário permanece na próxima etapa de infraestrutura.",
  };
}

export async function requireUserPaperOrderCapability(user: ChatGPTUser): Promise<{
  token: AlpacaToken;
  config: UserAlpacaConfig;
}> {
  const config = getUserAlpacaConfig();
  const token = await getToken(user.userId, "paper");
  if (!scopeAllows(token, "trading")) {
    throw new UserAlpacaError("trading_scope_required", "A conta está conectada em modo leitura; autorização de trading ainda não foi concedida.", 423);
  }
  if (!isPaperPilotUser(user)) {
    throw new UserAlpacaError("paper_pilot_allowlist_required", "Este usuário ainda não foi incluído no piloto Paper.", 423);
  }
  if (config.paperKillSwitch) {
    throw new UserAlpacaError("paper_kill_switch_active", "Kill switch do piloto Paper está ativo.", 423);
  }
  if (!config.paperExecutionEnabled) {
    throw new UserAlpacaError("paper_execution_disabled", "A execução Paper multiusuário está desativada no backend.", 423);
  }
  return { token, config };
}

export async function requireUserPaperTradingToken(user: ChatGPTUser): Promise<AlpacaToken> {
  const token = await getToken(user.userId, "paper");
  if (!scopeAllows(token, "trading")) {
    throw new UserAlpacaError("trading_scope_required", "A conta não autorizou operações de trading.", 423);
  }
  return token;
}

export function errorResponse(error: unknown): Response {
  if (error instanceof UserAlpacaError) {
    return Response.json({ error: error.code, message: error.message }, { status: error.status });
  }
  return Response.json({ error: "internal_error", message: "Não foi possível concluir a operação Alpaca." }, { status: 500 });
}

export function numeric(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function orderRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

export async function currentUser(): Promise<ChatGPTUser> {
  return requireUser();
}
