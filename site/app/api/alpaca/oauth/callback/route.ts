import { NextResponse } from "next/server";
import { getChatGPTUser } from "../../../../chatgpt-auth";
import {
  exchangeAuthorizationCode,
  readOAuthState,
  storeToken,
} from "../../../../alpaca-oauth";

export const dynamic = "force-dynamic";

export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const providerError = url.searchParams.get("error");
  if (providerError) {
    return new Response("A autorização na Alpaca foi cancelada.", { status: 400 });
  }
  const code = url.searchParams.get("code");
  const returnedState = url.searchParams.get("state");
  const saved = await readOAuthState();
  if (!code || !returnedState || !saved || returnedState !== saved.state) {
    return new Response("Callback OAuth inválido ou expirado.", { status: 400 });
  }
  const user = await getChatGPTUser();
  if (!user || user.userId !== saved.payload.userId) {
    return new Response("A sessão do ChatGPT não corresponde à autorização iniciada.", { status: 401 });
  }
  try {
    const token = await exchangeAuthorizationCode(code, saved.verifier, saved.payload.userId, "paper");
    const response = await storeToken(token);
    const redirect = NextResponse.redirect(
      new URL("/?alpaca=connected", request.url),
    );
    response.headers.forEach((value, key) => redirect.headers.append(key, value));
    return redirect;
  } catch {
    return new Response(
      "Não foi possível concluir a autorização Alpaca.",
      { status: 502 },
    );
  }
}
