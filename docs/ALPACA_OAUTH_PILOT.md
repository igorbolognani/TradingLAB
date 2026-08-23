# Alpaca OAuth Paper pilot

Status: implemented as a read-first foundation; user Paper execution and Live
remain disabled by default.

## What changed

The public site can now lead a signed-in visitor to `/alpaca/connect`. The
visitor authorizes their own Alpaca account; TradingLAB does not receive the
Alpaca password and does not reuse the owner’s direct API key.

The OAuth callback uses PKCE and a signed state. When D1 is available, the
server stores an encrypted token and connection metadata in the
`alpaca_connections` table. The browser receives only normalized account,
market-data and order information. The token itself is never returned.

The user workspace uses separate routes from the owner bridge:

| Route | Purpose |
| --- | --- |
| `GET /api/alpaca/user/status` | Connected Paper/Live status and gates |
| `GET /api/alpaca/user/account?env=paper` | User-owned account state |
| `GET /api/alpaca/user/positions?env=paper` | User-owned positions |
| `GET /api/alpaca/user/quote?symbol=SPY&env=paper` | IEX quote with explicit REST/non-realtime status |
| `GET /api/alpaca/user/bars?symbol=SPY&env=paper` | User-authorized IEX candles |
| `GET /api/alpaca/user/orders?status=open&env=paper` | Orders plus local reconciliation |
| `POST /api/alpaca/user/orders` | Paper order path, disabled by default |
| `DELETE /api/alpaca/user/orders` | Paper cancellation, only with user trading scope |

## Default safety configuration

```text
TRADINGLAB_OAUTH_PAPER_TRADING_SCOPE_ENABLED=false
TRADINGLAB_OAUTH_PAPER_EXECUTION_ENABLED=false
TRADINGLAB_OAUTH_PAPER_KILL_SWITCH=true
TRADINGLAB_OAUTH_PAPER_ALLOWED_USER_EMAILS=
TRADINGLAB_OAUTH_PAPER_ALLOWED_USER_IDS=
TRADINGLAB_OAUTH_LIVE_CONNECT_ENABLED=false
TRADINGLAB_OAUTH_LIVE_EXECUTION_ENABLED=false
TRADINGLAB_OAUTH_LIVE_KILL_SWITCH=true
```

This means a user can connect in read mode after the OAuth application is
configured, but cannot submit a Paper order until the application is approved,
the scope is requested, the user is intentionally invited, and the operator
enables the Paper pilot.

## Order contract

When the pilot is eventually enabled, the server will require:

- authenticated ChatGPT identity;
- Paper OAuth token with `trading` scope;
- invited-user allowlist;
- Paper environment only;
- active execution flag and inactive kill switch;
- symbol allowlist;
- integer quantity and maximum quantity;
- fresh IEX reference quote;
- maximum notional;
- long-only sell against the broker-reported position;
- persistent intent before provider submission;
- append-only event after intent, submission, rejection or status change.

If the ledger is unavailable, the order is refused before contacting Alpaca.
Retries must reuse the same `client_order_id`; they must not create a second
order intent.

## Phase C boundary

The Live path is deliberately prepared but not enabled. The code can represent
Paper and Live connections, but the authorization gate defaults to off and
there is no Live `POST` or Live cancellation path. A future Live release needs
provider approval, legal/compliance review, user consent, a separate risk
policy, incident procedures and a controlled canary.
