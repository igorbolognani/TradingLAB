import Image from "next/image";
import Link from "next/link";
import { chatGPTSignInPath, getChatGPTUser } from "../../chatgpt-auth";

export const dynamic = "force-dynamic";

export default async function AlpacaConnectPage() {
  const user = await getChatGPTUser();
  const continueHref = user
    ? "/api/alpaca/oauth/start?env=paper"
    : chatGPTSignInPath("/alpaca/connect");

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
              Alpaca Paper · access to market-data endpoints · no trading scope
              · no order submission in this version.
            </span>
          </div>

          <div className="oauth-actions">
            <a className="button button-primary" href={continueHref}>
              {user ? "Continue to Alpaca →" : "Sign in with ChatGPT →"}
            </a>
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
