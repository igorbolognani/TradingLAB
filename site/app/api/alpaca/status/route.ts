import { getChatGPTUser } from "../../../chatgpt-auth";
import { getStoredToken } from "../../../alpaca-oauth";

export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  const user = await getChatGPTUser();
  if (!user) return Response.json({ authenticated: false, connected: false });
  const token = await getStoredToken(user.userId);
  return Response.json({
    authenticated: true,
    connected: Boolean(token),
    environment: token?.environment ?? null,
    connected_at: token?.connected_at ?? null,
    scope: token?.scope ?? null,
  });
}
