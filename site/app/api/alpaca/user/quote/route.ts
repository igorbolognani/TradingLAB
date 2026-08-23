import { currentUser, errorResponse, userQuote } from "../../../../alpaca-user";

export const dynamic = "force-dynamic";

export async function GET(request: Request): Promise<Response> {
  try {
    const user = await currentUser();
    const query = new URL(request.url).searchParams;
    const environment = query.get("env") === "live" ? "live" : "paper";
    return Response.json(await userQuote(user.userId, environment, query.get("symbol") ?? "SPY"));
  } catch (error) {
    return errorResponse(error);
  }
}
