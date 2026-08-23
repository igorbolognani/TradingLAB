import { alpacaJson, errorResponse, isOwnerRequest } from "../../../../alpaca-direct";

export const dynamic = "force-dynamic";

export async function GET(request: Request): Promise<Response> {
  if (!(await isOwnerRequest(request))) return Response.json({ error: "owner_access_required" }, { status: 403 });
  try {
    const account = await alpacaJson("/v2/account");
    return Response.json({
      id: account.id ?? null,
      status: account.status ?? null,
      currency: account.currency ?? null,
      cash: account.cash ?? null,
      equity: account.equity ?? null,
      buying_power: account.buying_power ?? null,
      daytrade_count: account.daytrade_count ?? null,
      pattern_day_trader: account.pattern_day_trader ?? null,
      last_equity: account.last_equity ?? null,
      environment: "paper",
      source: "Alpaca Trading API",
    });
  } catch (error) {
    return errorResponse(error);
  }
}
