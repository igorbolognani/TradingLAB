import { errorResponse, isOwnerRequest, liveQuote } from "../../../../alpaca-direct";

export const dynamic = "force-dynamic";

export async function GET(request: Request): Promise<Response> {
  if (!(await isOwnerRequest(request))) return Response.json({ error: "owner_access_required" }, { status: 403 });
  try {
    const symbol = new URL(request.url).searchParams.get("symbol") ?? "SPY";
    return Response.json(await liveQuote(symbol));
  } catch (error) {
    return errorResponse(error);
  }
}
