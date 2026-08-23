import { currentUser, errorResponse, userTradingJson } from "../../../../alpaca-user";

export const dynamic = "force-dynamic";

export async function GET(request: Request): Promise<Response> {
  try {
    const user = await currentUser();
    const environment = new URL(request.url).searchParams.get("env") === "live" ? "live" : "paper";
    const positions = await userTradingJson<unknown[]>(user.userId, environment, "/v2/positions");
    return Response.json({ positions: Array.isArray(positions) ? positions : [], environment, source: "Alpaca Trading API via OAuth" });
  } catch (error) {
    return errorResponse(error);
  }
}
