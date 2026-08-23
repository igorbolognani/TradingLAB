import Image from "next/image";
import Link from "next/link";
import { chatGPTSignInPath, getChatGPTUser } from "../../chatgpt-auth";

export const dynamic = "force-dynamic";

export default async function AlpacaConnectPage() {
  const user = await getChatGPTUser();
  const oauthConfigured = Boolean(
    process.env.ALPACA_OAUTH_CLIENT_ID?.trim() &&
      process.env.ALPACA_OAUTH_CLIENT_SECRET?.trim() &&
      process.env.ALPACA_OAUTH_REDIRECT_URI?.trim(),
  );
  const continueHref = user && oauthConfigured
    ? "/api/alpaca/oauth/start?env=paper"
    : chatGPTSignInPath("/alpaca/connect");
  const paperTradingScopeEnabled = process.env.TRADINGLAB_OAUTH_PAPER_TRADING_SCOPE_ENABLED === "true";
  const liveConnectEnabled = process.env.TRADINGLAB_OAUTH_LIVE_CONNECT_ENABLED === "true";

  return (
    <main className="oauth-shell">
      <section className="oauth-card" aria-labelledby="oauth-title">
        <div className="oauth-card-header">
          <Image
            src="/tradinglab-logo.svg"
            width={500}
            height={112}
            className="oauth-logo"
            alt="TradingLAB"
            priority
          />
          <span className="oauth-provider">ALPACA CONNECT · PAPER</span>
        </div>

        <div className="oauth-card-body">
          <div className="oauth-eyebrow">External account authorization</div>
          <h1 id="oauth-title">Authorize TradingLAB</h1>
          <p className="oauth-intro">
            Review the disclosure below before continuing to Alpaca. You will
            authorize your own Alpaca account; TradingLAB never receives your
            Alpaca password.
          </p>

          <div className="oauth-disclosure" role="note">
            <strong>Authorize TradingLAB</strong>
            <p>
              By allowing TradingLAB to access your Alpaca account, you are
              granting TradingLAB access to your account information and
              authorization to place transactions in your account at your
              direction. Alpaca does not warrant or guarantee that TradingLAB
              will work as advertised or expected. Before authorizing, learn
              more about TradingLAB.
            </p>
          </div>

          <div className="oauth-scope-note">
            <strong>Current TradingLAB request</strong>
            <span>
              {oauthConfigured
                ? "Alpaca Paper · access to market-data endpoints · no trading scope · no order submission until the pilot is explicitly enabled."
                : "A conexão está preparada, mas o cadastro OAuth da Alpaca ainda não foi configurado no ambiente publicado."
              }
            </span>
          </div>

          <div className="oauth-mode-list" aria-label="TradingLAB authorization modes">
            <div><strong>Paper · leitura</strong><span>Ativo agora: conta, posições, ordens e candles da sua própria conta.</span></div>
            <div className={paperTradingScopeEnabled ? "" : "oauth-mode-disabled"}><strong>Paper · trading</strong><span>{paperTradingScopeEnabled ? "Disponível somente para usuários convidados do piloto." : "Bloqueado até aprovação, testes e convite do piloto."}</span></div>
            <div className={liveConnectEnabled ? "" : "oauth-mode-disabled"}><strong>Live</strong><span>{liveConnectEnabled ? "Preparado para revisão final." : "Bloqueado nesta versão; nenhum dinheiro real é acessado."}</span></div>
          </div>

          <div className="oauth-actions">
            {user && !oauthConfigured ? (
              <span className="button button-primary button-disabled" aria-disabled="true">
                OAuth aguardando configuração
              </span>
            ) : (
              <a className="button button-primary" href={continueHref}>
                {user ? "Continue to Alpaca →" : "Sign in with ChatGPT →"}
              </a>
            )}
            <Link className="button button-quiet" href="/">
              Cancel
            </Link>
          </div>

          <p className="oauth-legal-links">
            Read the <Link href="/terms">Terms of Use</Link> and{" "}
            <Link href="/privacy">Privacy Policy</Link> before continuing.
          </p>
        </div>
      </section>
    </main>
  );
}
