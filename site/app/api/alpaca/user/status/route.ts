import { getChatGPTUser } from "../../../../chatgpt-auth";
import { getStoredConnections, getStoredTokenForEnvironment } from "../../../../alpaca-oauth";
import { errorResponse } from "../../../../alpaca-user";

export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  try {
    const user = await getChatGPTUser();
    if (!user) return Response.json({ authenticated: false, connected: false });
    const stored = await getStoredConnections(user.userId);
    const connections = stored.length
      ? stored
      : (await Promise.all((['paper', 'live'] as const).map(async (environment) => {
          const token = await getStoredTokenForEnvironment(user.userId, environment);
          return token ? { environment, scope: token.scope ?? "data", connected_at: token.connected_at, updated_at: token.connected_at } : null;
        }))).filter((value): value is { environment: "paper" | "live"; scope: string; connected_at: string; updated_at: string } => Boolean(value));
    const paper = connections.find((connection) => connection.environment === "paper") ?? null;
    const live = connections.find((connection) => connection.environment === "live") ?? null;
    const paperExecutionEnabled = process.env.TRADINGLAB_OAUTH_PAPER_EXECUTION_ENABLED === "true";
    const paperKillSwitch = process.env.TRADINGLAB_OAUTH_PAPER_KILL_SWITCH !== "false";
    const allowedSymbols = (process.env.TRADINGLAB_OAUTH_ALLOWED_SYMBOLS ?? "SPY,IWM,EFA,TLT,GLD").split(",").map((symbol) => symbol.trim()).filter(Boolean);
    return Response.json({
      authenticated: true,
      connected: Boolean(paper || live),
      configured: Boolean(paper),
      environment: paper ? "paper" : live ? "live" : "not_connected",
      market_data_feed: "iex",
      realtime_enabled: false,
      execution_enabled: paperExecutionEnabled,
      paper_enabled: paperExecutionEnabled,
      live_enabled: false,
      kill_switch: paperKillSwitch,
      max_order_notional_usd: Number(process.env.TRADINGLAB_OAUTH_MAX_ORDER_NOTIONAL_USD ?? "250") || 250,
      max_order_quantity: Number(process.env.TRADINGLAB_OAUTH_MAX_ORDER_QUANTITY ?? "5") || 5,
      allowed_symbols: allowedSymbols,
      missing: [],
      transport: "oauth_rest_with_stream_preparation",
      environments: {
        paper: paper ? { connected: true, connected_at: paper.connected_at, scope: paper.scope } : { connected: false },
        live: live ? { connected: true, connected_at: live.connected_at, scope: live.scope } : { connected: false },
      },
      persistence: stored.length || (await getStoredTokenForEnvironment(user.userId, "paper")) ? "server_database" : "not_connected",
      paper_trading_scope_enabled: process.env.TRADINGLAB_OAUTH_PAPER_TRADING_SCOPE_ENABLED === "true",
      paper_execution_enabled: paperExecutionEnabled,
      paper_kill_switch: paperKillSwitch,
      live_authorization_enabled: process.env.TRADINGLAB_OAUTH_LIVE_CONNECT_ENABLED === "true",
      live_execution_enabled: false,
      message: "O ambiente Live permanece bloqueado nesta versão.",
    });
  } catch (error) {
    return errorResponse(error);
  }
}
