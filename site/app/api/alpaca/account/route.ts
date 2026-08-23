import { getChatGPTUser } from "../../../chatgpt-auth";
import { getStoredToken } from "../../../alpaca-oauth";

export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  const user = await getChatGPTUser();
  if (!user) return Response.json({ error: "authentication_required" }, { status: 401 });
  const token = await getStoredToken(user.userId);
  if (!token) return Response.json({ error: "alpaca_not_connected" }, { status: 409 });
  const response = await fetch("https://paper-api.alpaca.markets/v2/account", {
    headers: { Authorization: "Bearer " + token.access_token },
  });
  if (!response.ok) {
    return Response.json({ error: "alpaca_account_unavailable" }, { status: 502 });
  }
  return Response.json(await response.json());
}
