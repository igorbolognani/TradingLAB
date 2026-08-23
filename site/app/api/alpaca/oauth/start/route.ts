import { getChatGPTUser } from "../../../../chatgpt-auth";
import {
  AlpacaOAuthError,
  createAuthorizationRedirect,
  type AlpacaOAuthEnvironment,
  type AlpacaOAuthMode,
} from "../../../../alpaca-oauth";

export const dynamic = "force-dynamic";

export async function GET(request: Request): Promise<Response> {
  const user = await getChatGPTUser();
  if (!user) {
    return new Response(
      "Faça login com ChatGPT antes de conectar a Alpaca.",
      { status: 401 },
    );
  }
  try {
    const query = new URL(request.url).searchParams;
    const environment: AlpacaOAuthEnvironment = query.get("env") === "live" ? "live" : "paper";
    const mode: AlpacaOAuthMode = query.get("mode") === "trade" ? "trade" : "read";
    return await createAuthorizationRedirect(request, user.userId, environment, mode);
  } catch (error) {
    if (error instanceof AlpacaOAuthError) {
      return Response.json({ error: error.code, message: error.message }, { status: error.status });
    }
    return Response.json(
      { error: "oauth_not_configured", message: "OAuth da Alpaca ainda não foi configurado no backend." },
      { status: 503 },
    );
  }
}
