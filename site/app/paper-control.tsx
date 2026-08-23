"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type PaperStatus = {
  configured: boolean;
  environment: string;
  market_data_feed: string;
  realtime_enabled: boolean;
  execution_enabled: boolean;
  paper_enabled: boolean;
  live_enabled: boolean;
  kill_switch: boolean;
  max_order_notional_usd: number;
  max_order_quantity: number;
  allowed_symbols: string[];
  missing: string[];
  transport: string;
};

type QuotePayload = {
  quote: {
    symbol: string;
    bid_price: number | null;
    bid_size: number | null;
    ask_price: number | null;
    ask_size: number | null;
    last_price: number | null;
    last_size: number | null;
    event_time: string | null;
    receive_time_utc: string;
  };
  transport: string;
  realtime_active: boolean;
  latency_ms: number | null;
  data_age_seconds: number | null;
  observed_at: string;
  message: string;
};

type BarsPayload = {
  symbol: string;
  timeframe: string;
  candles: Array<{
    event_time: string;
    session: string;
    open: number | null;
    high: number | null;
    low: number | null;
    close: number | null;
    volume: number | null;
    is_complete: boolean | null;
  }>;
  source: { provider: string; provider_version: string; price_basis_id: string };
  freshness: { data_age_seconds: number | null; message: string };
};

type AccountPayload = {
  status: string | null;
  currency: string | null;
  cash: string | null;
  equity: string | null;
  buying_power: string | null;
  environment: string;
};

type Position = Record<string, unknown>;
type Order = Record<string, unknown>;

function numberValue(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatMoney(value: unknown): string {
  const parsed = numberValue(value);
  return parsed == null
    ? "—"
    : parsed.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
}

function formatPrice(value: unknown): string {
  const parsed = numberValue(value);
  return parsed == null ? "—" : `$${parsed.toFixed(2)}`;
}

function formatTime(value: unknown): string {
  if (typeof value !== "string" || !value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

async function readPayload<T>(response: Response): Promise<T> {
  const payload = (await response.json()) as T & { message?: string; error?: string };
  if (!response.ok) throw new Error(payload.message ?? payload.error ?? "solicitação recusada");
  return payload;
}

export default function PaperControl({ userMode = false }: { userMode?: boolean }) {
  const apiRoot = userMode ? "/api/alpaca/user" : "/api/alpaca/direct";
  const [symbol, setSymbol] = useState("SPY");
  const [timeframe, setTimeframe] = useState("1Min");
  const [status, setStatus] = useState<PaperStatus | null>(null);
  const [quote, setQuote] = useState<QuotePayload | null>(null);
  const [bars, setBars] = useState<BarsPayload | null>(null);
  const [account, setAccount] = useState<AccountPayload | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [quantity, setQuantity] = useState("1");
  const [orderType, setOrderType] = useState<"market" | "limit">("market");
  const [limitPrice, setLimitPrice] = useState("");
  const [notice, setNotice] = useState("");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const refreshInFlight = useRef(false);

  const refresh = useCallback(async () => {
    if (refreshInFlight.current) return;
    refreshInFlight.current = true;
    setIsRefreshing(true);
    try {
      const statusPayload = await readPayload<PaperStatus>(await fetch(`${apiRoot}/status`, { cache: "no-store" }));
      setStatus(statusPayload);
      if (!statusPayload.configured) {
        setQuote(null);
        setAccount(null);
        setPositions([]);
        setOrders([]);
        setNotice(userMode ? "Conecte uma conta Alpaca Paper para abrir este workspace." : "O backend Paper está protegido, mas ainda não recebeu uma configuração válida.");
        return;
      }
      const [quoteResponse, accountResponse, positionsResponse, ordersResponse] = await Promise.all([
        fetch(`${apiRoot}/quote?symbol=${encodeURIComponent(symbol)}&env=paper`, { cache: "no-store" }),
        fetch(`${apiRoot}/account?env=paper`, { cache: "no-store" }),
        fetch(`${apiRoot}/positions?env=paper`, { cache: "no-store" }),
        fetch(`${apiRoot}/orders?status=open&env=paper`, { cache: "no-store" }),
      ]);
      setQuote(await readPayload<QuotePayload>(quoteResponse));
      setAccount(await readPayload<AccountPayload>(accountResponse));
      setPositions((await readPayload<{ positions: Position[] }>(positionsResponse)).positions);
      setOrders((await readPayload<{ orders: Order[] }>(ordersResponse)).orders);
      setNotice("Conta, cotação, posições e ordens atualizadas.");
    } catch (error) {
      setNotice(`O backend Paper não respondeu: ${error instanceof Error ? error.message : "erro desconhecido"}.`);
    } finally {
      refreshInFlight.current = false;
      setIsRefreshing(false);
    }
  }, [apiRoot, symbol, userMode]);

  useEffect(() => {
    // The initial refresh synchronizes the UI with the server-owned account.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function loadBars() {
    try {
      setNotice("Carregando candles reais da Alpaca IEX…");
      const response = await fetch(`${apiRoot}/bars?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}&limit=120&env=paper`, { cache: "no-store" });
      setBars(await readPayload<BarsPayload>(response));
      setNotice("Candles reais carregados; a última barra intraday pode estar incompleta.");
    } catch (error) {
      setNotice(`Não foi possível carregar candles: ${error instanceof Error ? error.message : "erro desconhecido"}.`);
    }
  }

  async function submitOrder() {
    setIsSubmitting(true);
    try {
      const response = await fetch(`${apiRoot}/orders`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ symbol, side, qty: Number(quantity), type: orderType, limit_price: orderType === "limit" ? Number(limitPrice) : undefined, time_in_force: "day" }),
      });
      const payload = await readPayload<{ reconciliation?: { client_order_id?: string | null } }>(response);
      setNotice(`Ordem Paper enviada. ID: ${payload.reconciliation?.client_order_id ?? "—"}.`);
      await refresh();
    } catch (error) {
      setNotice(`Ordem não enviada: ${error instanceof Error ? error.message : "execução bloqueada"}.`);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function cancelOrder(id?: string) {
    if (!window.confirm(id ? "Cancelar esta ordem Paper?" : "Cancelar todas as ordens Paper abertas?")) return;
    try {
      const endpoint = id ? `${apiRoot}/orders?id=${encodeURIComponent(id)}&env=paper` : `${apiRoot}/orders?env=paper`;
      const response = await fetch(endpoint, { method: "DELETE" });
      await readPayload(response);
      setNotice(id ? "Ordem cancelada." : "Ordens abertas canceladas.");
      await refresh();
    } catch (error) {
      setNotice(`Cancelamento não concluído: ${error instanceof Error ? error.message : "erro desconhecido"}.`);
    }
  }

  const symbols = useMemo(() => status?.allowed_symbols?.length ? status.allowed_symbols : ["SPY", "IWM", "EFA", "TLT", "GLD"], [status]);
  const orderLocked = !status?.configured || Boolean(status?.kill_switch) || !status?.execution_enabled || !status?.paper_enabled;
  const lockReason = status?.kill_switch ? "kill switch ativo" : !status?.paper_enabled ? "Paper trading desativado" : !status?.execution_enabled ? "execução desativada" : "backend não configurado";

  return (
    <section className="page-stack paper-control-page">
      <div className="page-heading"><div><div className="eyebrow">Alpaca Paper / {userMode ? "connected workspace" : "private control room"}</div><h1>Mercado, conta e execução em um único painel.</h1></div><span className={`api-badge ${status?.configured ? "api-online" : "api-offline"}`}><span />{status?.configured ? "Paper conectado" : "Paper aguardando configuração"}</span></div>
      <div className="notice" role="status">{notice || (userMode ? "Conecte sua própria conta Alpaca; a autorização fica vinculada somente ao seu usuário." : "O painel consulta o backend privado e nunca expõe as credenciais no navegador.")}</div>
      <div className="paper-status-grid">
        <article className="panel"><div className="panel-kicker">Connection</div><h2>{status?.configured ? "Conexão protegida" : "Conexão não disponível"}</h2><div className="paper-status-list"><span>Ambiente<strong>{status?.environment ?? "—"}</strong></span><span>Feed<strong>{status?.market_data_feed ?? "—"}</strong></span><span>Transporte<strong>{status?.transport ?? "—"}</strong></span><span>Realtime<strong>{status?.realtime_enabled ? "habilitado" : "desabilitado"}</strong></span></div>{status?.missing?.length ? <p className="panel-copy">Variáveis ausentes: {status.missing.join(", ")}</p> : null}{userMode && !status?.configured ? <a className="button button-primary" href="/alpaca/connect">Conectar Alpaca Paper</a> : null}</article>
        <article className="panel"><div className="panel-kicker">Safety gate</div><h2>{orderLocked ? "Novas ordens bloqueadas" : "Paper pronto para envio"}</h2><div className="safety-tags"><span>{status?.kill_switch ? "KILL SWITCH ON" : "KILL SWITCH OFF"}</span><span>{status?.live_enabled ? "LIVE INVALID" : "LIVE OFF"}</span><span>MAX ${status?.max_order_notional_usd ?? "—"}</span></div><p className="panel-copy">{orderLocked ? `Motivo: ${lockReason}. Cancelamento continua disponível como ação de redução de risco.` : "Toda ordem passa por allowlist, quantidade, notional e posição disponível."}</p></article>
      </div>
      <div className="paper-grid">
        <article className="panel paper-market-panel"><div className="panel-heading"><div><div className="panel-kicker">Live quote / IEX</div><h2>Cotação monitorada</h2></div><button className="button button-outline" type="button" onClick={() => void refresh()} disabled={isRefreshing}>{isRefreshing ? "Atualizando…" : "Atualizar"}</button></div><div className="paper-controls"><label>Ativo<select value={symbol} onChange={(event) => setSymbol(event.target.value)}>{symbols.map((item) => <option key={item}>{item}</option>)}</select></label><label>Timeframe<select value={timeframe} onChange={(event) => setTimeframe(event.target.value)}><option>1Min</option><option>5Min</option><option>15Min</option><option>1Hour</option><option>1Day</option></select></label><button className="button button-primary" type="button" onClick={() => void loadBars()} disabled={!status?.configured}>Carregar candles</button></div>{quote ? <div className="quote-grid"><div><span>Último negócio</span><strong>{formatPrice(quote.quote.last_price)}</strong></div><div><span>Bid</span><strong>{formatPrice(quote.quote.bid_price)}</strong><small>{quote.quote.bid_size ?? "—"}</small></div><div><span>Ask</span><strong>{formatPrice(quote.quote.ask_price)}</strong><small>{quote.quote.ask_size ?? "—"}</small></div><div><span>Latência / idade</span><strong>{quote.latency_ms == null ? "—" : `${quote.latency_ms} ms`}</strong><small>{quote.data_age_seconds == null ? quote.transport : `${Math.round(quote.data_age_seconds)} s · ${quote.transport}`}</small></div></div> : <div className="paper-empty">Aguardando uma cotação real.</div>}{quote ? <div className="chart-footnote">{quote.message} Evento {formatTime(quote.quote.event_time)} · recebido {formatTime(quote.quote.receive_time_utc)}.</div> : null}</article>
        <article className="panel paper-account-panel"><div className="panel-kicker">Account / paper</div><h2>Conta e poder de compra</h2>{account ? <div className="account-metric-grid"><div><span>Equity</span><strong>{formatMoney(account.equity)}</strong></div><div><span>Cash</span><strong>{formatMoney(account.cash)}</strong></div><div><span>Buying power</span><strong>{formatMoney(account.buying_power)}</strong></div><div><span>Status</span><strong>{account.status ?? "—"}</strong></div></div> : <div className="paper-empty">A conta aparecerá após validar as credenciais Paper.</div>}</article>
      </div>
      {bars ? <article className="panel"><div className="panel-heading"><div><div className="panel-kicker">Candles completos</div><h2>{bars.symbol} · {bars.timeframe}</h2></div><span className="source-pill">{bars.source.provider} · {bars.source.price_basis_id}</span></div><div className="table-wrap"><table><thead><tr><th>Hora</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th><th>Estado</th></tr></thead><tbody>{bars.candles.slice(-15).reverse().map((candle) => <tr key={candle.event_time}><td>{formatTime(candle.event_time)}</td><td>{formatPrice(candle.open)}</td><td>{formatPrice(candle.high)}</td><td>{formatPrice(candle.low)}</td><td>{formatPrice(candle.close)}</td><td>{candle.volume?.toLocaleString("en-US") ?? "—"}</td><td>{candle.is_complete ? "completo" : "em formação"}</td></tr>)}</tbody></table></div><div className="chart-footnote">{bars.freshness.message} Idade aproximada: {bars.freshness.data_age_seconds == null ? "—" : `${Math.round(bars.freshness.data_age_seconds)} s`}.</div></article> : null}
      <div className="paper-grid">
        <article className="panel"><div className="panel-heading"><div><div className="panel-kicker">Positions</div><h2>Posições atuais</h2></div><span className="source-pill">{positions.length} ativos</span></div>{positions.length ? <div className="table-wrap"><table><thead><tr><th>Ativo</th><th>Quantidade</th><th>Preço médio</th><th>Último preço</th><th>Valor</th><th>P/L</th></tr></thead><tbody>{positions.map((position) => <tr key={String(position.symbol)}><td>{String(position.symbol ?? "—")}</td><td>{String(position.qty ?? "—")}</td><td>{formatPrice(position.avg_entry_price)}</td><td>{formatPrice(position.current_price)}</td><td>{formatMoney(position.market_value)}</td><td className={numberValue(position.unrealized_pl) != null && Number(position.unrealized_pl) >= 0 ? "positive" : "negative"}>{formatMoney(position.unrealized_pl)}</td></tr>)}</tbody></table></div> : <div className="paper-empty">Nenhuma posição Paper aberta.</div>}</article>
        <article className="panel"><div className="panel-heading"><div><div className="panel-kicker">Orders / reconciliation</div><h2>Ordens abertas</h2></div><button className="button button-outline" type="button" onClick={() => void cancelOrder()} disabled={!orders.length}>Cancelar todas</button></div>{orders.length ? <div className="paper-order-list">{orders.map((order) => <div className="paper-order-row" key={String(order.id)}><div><strong>{String(order.side ?? "—").toUpperCase()} {String(order.symbol ?? "—")}</strong><small>{String(order.qty ?? "—")} · {String(order.type ?? "—")} · {String(order.status ?? "—")}</small><small>ID: {String(order.client_order_id ?? order.id ?? "—")}</small></div><button className="button button-quiet" type="button" onClick={() => void cancelOrder(String(order.id))}>Cancelar</button></div>)}</div> : <div className="paper-empty">Nenhuma ordem aberta para reconciliar.</div>}</article>
      </div>
      <article className="panel paper-order-panel"><div className="panel-kicker">Paper order gate</div><h2>Enviar uma ordem controlada</h2><p className="panel-copy">A tela existe para o fluxo end-to-end, mas o backend só enviará uma ordem quando as três chaves de segurança estiverem explicitamente liberadas. O estado atual permanece bloqueado.</p><div className="paper-order-form"><label>Ativo<select value={symbol} onChange={(event) => setSymbol(event.target.value)}>{symbols.map((item) => <option key={item}>{item}</option>)}</select></label><label>Lado<select value={side} onChange={(event) => setSide(event.target.value as "buy" | "sell")}><option value="buy">Compra</option><option value="sell">Venda</option></select></label><label>Quantidade<input type="number" min="1" step="1" value={quantity} onChange={(event) => setQuantity(event.target.value)} /></label><label>Tipo<select value={orderType} onChange={(event) => setOrderType(event.target.value as "market" | "limit")}><option value="market">Market</option><option value="limit">Limit</option></select></label>{orderType === "limit" ? <label>Preço limite<input type="number" min="0.01" step="0.01" value={limitPrice} onChange={(event) => setLimitPrice(event.target.value)} /></label> : null}<button className="button button-primary" type="button" onClick={() => void submitOrder()} disabled={orderLocked || isSubmitting}>{isSubmitting ? "Enviando…" : orderLocked ? `Bloqueado · ${lockReason}` : "Enviar ordem Paper"}</button></div></article>
    </section>
  );
}
