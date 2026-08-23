import { getChatGPTUser } from "../../../../chatgpt-auth";
import { createAuthorizationRedirect } from "../../../../alpaca-oauth";

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
    return await createAuthorizationRedirect(request, user.userId);
  } catch {
    return new Response(
      "OAuth da Alpaca ainda não foi configurado no backend.",
      { status: 503 },
    );
  }
}
