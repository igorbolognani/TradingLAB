import { cookies } from "next/headers";
import {
  getAlpacaConnection,
  hasTradingDatabase,
  listAlpacaConnections,
  revokeAlpacaConnection,
  upsertAlpacaConnection,
} from "../db/trading-store";

const STATE_COOKIE = "tradinglab_alpaca_oauth_state";
const VERIFIER_COOKIE = "tradinglab_alpaca_oauth_verifier";
const TOKEN_COOKIE = "tradinglab_alpaca_oauth_token";
const OAUTH_TTL_SECONDS = 600;
const TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30;

type OAuthState = {
  userId: string;
  issuedAt: number;
  nonce: string;
  environment: "paper" | "live";
  mode: "read" | "trade";
};

export type AlpacaOAuthEnvironment = "paper" | "live";
export type AlpacaOAuthMode = "read" | "trade";

export type AlpacaToken = {
  user_id: string;
  access_token: string;
  token_type: string;
  expires_in?: number;
  refresh_token?: string;
  scope?: string;
  environment: "paper" | "live";
  connected_at: string;
};

export class AlpacaOAuthError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status = 503) {
    super(message);
    this.name = "AlpacaOAuthError";
    this.code = code;
    this.status = status;
  }
}

const encoder = new TextEncoder();

function requiredEnv(name: string): string | null {
  const value = process.env[name]?.trim();
  return value || null;
}

function booleanEnv(name: string, fallback: boolean): boolean {
  const value = requiredEnv(name)?.toLowerCase();
  if (!value) return fallback;
  return ["1", "true", "yes", "on"].includes(value);
}

function base64UrlEncode(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function base64UrlDecode(value: string): Uint8Array {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  const binary = atob(padded);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function encodeText(value: string): string {
  return base64UrlEncode(encoder.encode(value));
}

function decodeText(value: string): string {
  return new TextDecoder().decode(base64UrlDecode(value));
}

function randomBytes(size: number): Uint8Array {
  const bytes = new Uint8Array(size);
  crypto.getRandomValues(bytes);
  return bytes;
}

async function sign(value: string): Promise<string> {
  const secret = requiredEnv("TRADINGLAB_ALPACA_OAUTH_STATE_SECRET");
  if (!secret) throw new Error("OAuth state secret is not configured");
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(value));
  return base64UrlEncode(new Uint8Array(signature));
}

async function verify(value: string, signature: string): Promise<boolean> {
  const secret = requiredEnv("TRADINGLAB_ALPACA_OAUTH_STATE_SECRET");
  if (!secret) return false;
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["verify"],
  );
  return crypto.subtle.verify(
    "HMAC",
    key,
    base64UrlDecode(signature),
    encoder.encode(value),
  );
}

async function encryptionKey(): Promise<CryptoKey> {
  const encoded = requiredEnv("TRADINGLAB_ALPACA_TOKEN_ENCRYPTION_KEY");
  if (!encoded) throw new Error("OAuth token encryption key is not configured");
  const raw = base64UrlDecode(encoded);
  if (raw.byteLength !== 32) throw new Error("OAuth token encryption key must be 32 bytes");
  return crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt", "decrypt"]);
}

async function encryptToken(token: AlpacaToken): Promise<string> {
  const iv = randomBytes(12);
  const encrypted = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    await encryptionKey(),
    encoder.encode(JSON.stringify(token)),
  );
  return (
    base64UrlEncode(iv) +
    "." +
    base64UrlEncode(new Uint8Array(encrypted))
  );
}

async function decryptToken(value: string): Promise<AlpacaToken | null> {
  const [encodedIv, encodedCiphertext] = value.split(".");
  if (!encodedIv || !encodedCiphertext) return null;
  try {
    const decrypted = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: base64UrlDecode(encodedIv) },
      await encryptionKey(),
      base64UrlDecode(encodedCiphertext),
    );
    const token = JSON.parse(new TextDecoder().decode(decrypted)) as AlpacaToken;
    return token.access_token ? token : null;
  } catch {
    return null;
  }
}

export function redirectUri(request: Request): string {
  return (
    requiredEnv("ALPACA_OAUTH_REDIRECT_URI") ??
    new URL("/api/alpaca/oauth/callback", request.url).toString()
  );
}

export async function createAuthorizationRedirect(
  request: Request,
  userId: string,
  environment: AlpacaOAuthEnvironment = "paper",
  mode: AlpacaOAuthMode = "read",
): Promise<Response> {
  if (environment === "live" && !booleanEnv("TRADINGLAB_OAUTH_LIVE_CONNECT_ENABLED", false)) {
    throw new AlpacaOAuthError(
      "live_connect_disabled",
      "A conexão Live está preparada, mas permanece bloqueada até aprovação e revisão operacional.",
      423,
    );
  }
  if (mode === "trade" && !booleanEnv(
    environment === "paper"
      ? "TRADINGLAB_OAUTH_PAPER_TRADING_SCOPE_ENABLED"
      : "TRADINGLAB_OAUTH_LIVE_TRADING_SCOPE_ENABLED",
    false,
  )) {
    throw new AlpacaOAuthError(
      "trading_scope_disabled",
      "A autorização de trading ainda não está habilitada para este ambiente.",
      423,
    );
  }
  const clientId = requiredEnv("ALPACA_OAUTH_CLIENT_ID");
  const redirect = requiredEnv("ALPACA_OAUTH_REDIRECT_URI") ?? redirectUri(request);
  if (!clientId) throw new AlpacaOAuthError("oauth_not_configured", "Client ID OAuth da Alpaca não configurado.");

  const verifier = base64UrlEncode(randomBytes(32));
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(verifier));
  const challenge = base64UrlEncode(new Uint8Array(digest));
  const statePayload = encodeText(
    JSON.stringify({
      userId,
      issuedAt: Date.now(),
      nonce: base64UrlEncode(randomBytes(18)),
      environment,
      mode,
    }),
  );
  const state = statePayload + "." + (await sign(statePayload));
  const query = new URLSearchParams({
    response_type: "code",
    client_id: clientId,
    redirect_uri: redirect,
    scope: mode === "trade" ? "data trading" : "data",
    env: environment,
    state,
    code_challenge: challenge,
    code_challenge_method: "S256",
  });
  const response = Response.redirect(
    "https://app.alpaca.markets/oauth/authorize?" + query.toString(),
    302,
  );
  response.headers.append(
    "Set-Cookie",
    STATE_COOKIE +
      "=" +
      encodeURIComponent(state) +
      "; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=" +
      OAUTH_TTL_SECONDS,
  );
  response.headers.append(
    "Set-Cookie",
    VERIFIER_COOKIE +
      "=" +
      encodeURIComponent(verifier) +
      "; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=" +
      OAUTH_TTL_SECONDS,
  );
  return response;
}

export async function readOAuthState(): Promise<{
  state: string;
  verifier: string;
  payload: OAuthState;
} | null> {
  const cookieStore = await cookies();
  const state = cookieStore.get(STATE_COOKIE)?.value;
  const verifier = cookieStore.get(VERIFIER_COOKIE)?.value;
  if (!state || !verifier) return null;
  const [payload, signature] = state.split(".");
  if (!payload || !signature || !(await verify(payload, signature))) return null;
  try {
    const decoded = JSON.parse(decodeText(payload)) as OAuthState;
    if (
      !decoded.userId ||
      !decoded.issuedAt ||
      !["paper", "live"].includes(decoded.environment) ||
      !["read", "trade"].includes(decoded.mode) ||
      Date.now() - decoded.issuedAt > OAUTH_TTL_SECONDS * 1000
    ) {
      return null;
    }
    return { state, verifier, payload: decoded };
  } catch {
    return null;
  }
}

export async function exchangeAuthorizationCode(
  code: string,
  verifier: string,
  userId: string,
  environment: AlpacaOAuthEnvironment = "paper",
): Promise<AlpacaToken> {
  const clientId = requiredEnv("ALPACA_OAUTH_CLIENT_ID");
  const clientSecret = requiredEnv("ALPACA_OAUTH_CLIENT_SECRET");
  const redirect = requiredEnv("ALPACA_OAUTH_REDIRECT_URI");
  if (!clientId || !clientSecret || !redirect) {
    throw new Error("Alpaca OAuth credentials are not configured");
  }
  const response = await fetch("https://api.alpaca.markets/oauth/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code,
      client_id: clientId,
      client_secret: clientSecret,
      redirect_uri: redirect,
      code_verifier: verifier,
    }),
  });
  if (!response.ok) throw new Error("Alpaca OAuth token exchange failed");
  const result = (await response.json()) as Omit<
    AlpacaToken,
    "user_id" | "environment" | "connected_at"
  >;
  if (!result.access_token) throw new Error("Alpaca did not return an access token");
  return {
    ...result,
    user_id: userId,
    environment,
    connected_at: new Date().toISOString(),
  };
}

export async function storeToken(token: AlpacaToken, userEmail: string): Promise<Response> {
  const encrypted = await encryptToken(token);
  const persisted = await upsertAlpacaConnection({
    userId: token.user_id,
    userEmail,
    environment: token.environment,
    encryptedToken: encrypted,
    scope: token.scope ?? "data",
    connectedAt: token.connected_at,
  });
  const response = new Response(null, { status: 204 });
  if (!persisted) {
    response.headers.append(
      "Set-Cookie",
      TOKEN_COOKIE +
        "=" +
        encodeURIComponent(encrypted) +
        "; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=" +
        TOKEN_TTL_SECONDS,
    );
  } else {
    response.headers.append(
      "Set-Cookie",
      TOKEN_COOKIE + "=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0",
    );
  }
  response.headers.append(
    "Set-Cookie",
    STATE_COOKIE +
      "=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0",
  );
  response.headers.append(
    "Set-Cookie",
    VERIFIER_COOKIE +
      "=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0",
  );
  return response;
}

export async function getStoredToken(expectedUserId?: string): Promise<AlpacaToken | null> {
  return getStoredTokenForEnvironment(expectedUserId, "paper");
}

export async function getStoredTokenForEnvironment(
  expectedUserId: string | undefined,
  environment: AlpacaOAuthEnvironment,
): Promise<AlpacaToken | null> {
  if (expectedUserId && (await hasTradingDatabase())) {
    const connection = await getAlpacaConnection(expectedUserId, environment);
    if (!connection) return null;
    const token = await decryptToken(connection.encrypted_token);
    if (!token || token.user_id !== expectedUserId) return null;
    return { ...token, environment };
  }
  const cookieStore = await cookies();
  const value = cookieStore.get(TOKEN_COOKIE)?.value;
  const token = value ? await decryptToken(value) : null;
  if (expectedUserId && token?.user_id !== expectedUserId) return null;
  if (token && token.environment !== environment) return null;
  return token;
}

export async function getStoredConnections(userId: string): Promise<Array<{
  environment: "paper" | "live";
  scope: string;
  connected_at: string;
  updated_at: string;
}>> {
  if (!(await hasTradingDatabase())) return [];
  const connections = await listAlpacaConnections(userId);
  return connections.map((connection) => ({
    environment: connection.environment,
    scope: connection.scope,
    connected_at: connection.connected_at,
    updated_at: connection.updated_at,
  }));
}

export async function disconnectStoredConnection(
  userId: string,
  environment: AlpacaOAuthEnvironment,
): Promise<Response> {
  if (await hasTradingDatabase()) await revokeAlpacaConnection(userId, environment);
  const response = new Response(null, { status: 204 });
  response.headers.append(
    "Set-Cookie",
    TOKEN_COOKIE + "=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0",
  );
  return response;
}
