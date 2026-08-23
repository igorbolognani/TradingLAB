import { getChatGPTUser } from "../../../chatgpt-auth";
import { disconnectStoredConnection, getStoredConnections, getStoredTokenForEnvironment } from "../../../alpaca-oauth";

export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  const user = await getChatGPTUser();
  if (!user) return Response.json({ authenticated: false, connected: false });
  const stored = await getStoredConnections(user.userId);
  const connections = stored.length
    ? stored
    : (await Promise.all((['paper', 'live'] as const).map(async (environment) => {
        const token = await getStoredTokenForEnvironment(user.userId, environment);
        return token ? { environment, connected_at: token.connected_at, scope: token.scope ?? "data" } : null;
      }))).filter((value): value is { environment: "paper" | "live"; connected_at: string; scope: string } => Boolean(value));
  const paper = connections.find((connection) => connection.environment === "paper") ?? null;
  const live = connections.find((connection) => connection.environment === "live") ?? null;
  return Response.json({
    authenticated: true,
    connected: Boolean(paper || live),
    environments: {
      paper: paper ? { connected: true, connected_at: paper.connected_at, scope: paper.scope } : { connected: false },
      live: live ? { connected: true, connected_at: live.connected_at, scope: live.scope } : { connected: false },
    },
    live_authorization_enabled: process.env.TRADINGLAB_OAUTH_LIVE_CONNECT_ENABLED === "true",
    paper_trading_scope_enabled: process.env.TRADINGLAB_OAUTH_PAPER_TRADING_SCOPE_ENABLED === "true",
    paper_execution_enabled: process.env.TRADINGLAB_OAUTH_PAPER_EXECUTION_ENABLED === "true",
  });
}

export async function DELETE(request: Request): Promise<Response> {
  const user = await getChatGPTUser();
  if (!user) return Response.json({ error: "authentication_required" }, { status: 401 });
  const environment = new URL(request.url).searchParams.get("env") === "live" ? "live" : "paper";
  return disconnectStoredConnection(user.userId, environment);
}
