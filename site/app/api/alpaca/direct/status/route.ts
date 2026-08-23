import { errorResponse, getDirectAlpacaConfig, isOwnerRequest } from "../../../../alpaca-direct";

export const dynamic = "force-dynamic";

export async function GET(request: Request): Promise<Response> {
  if (!(await isOwnerRequest(request))) return Response.json({ error: "owner_access_required" }, { status: 403 });
  try {
    const config = getDirectAlpacaConfig();
    return Response.json({
      configured: config.configured,
      environment: config.executionEnv,
      market_data_feed: config.marketDataFeed,
      realtime_enabled: config.realtimeEnabled,
      execution_enabled: config.executionEnabled,
      paper_enabled: config.paperEnabled,
      live_enabled: config.liveEnabled,
      kill_switch: config.killSwitch,
      max_order_notional_usd: config.maxOrderNotionalUsd,
      max_order_quantity: config.maxOrderQuantity,
      allowed_symbols: config.allowedSymbols,
      missing: config.missing,
      transport: config.realtimeEnabled ? "websocket_probe_with_rest_fallback" : "rest_disabled",
    });
  } catch (error) {
    return errorResponse(error);
  }
}
