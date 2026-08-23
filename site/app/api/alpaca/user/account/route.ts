import { currentUser, errorResponse, userTradingJson } from "../../../../alpaca-user";

export const dynamic = "force-dynamic";

export async function GET(request: Request): Promise<Response> {
  try {
    const user = await currentUser();
    const environment = new URL(request.url).searchParams.get("env") === "live" ? "live" : "paper";
    const account = await userTradingJson<Record<string, unknown>>(user.userId, environment, "/v2/account");
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
      environment,
      source: "Alpaca Trading API via OAuth",
    });
  } catch (error) {
    return errorResponse(error);
  }
}
