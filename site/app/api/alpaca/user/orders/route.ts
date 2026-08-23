import { getChatGPTUser } from "../../../../chatgpt-auth";
import {
  currentUser,
  errorResponse,
  normalizeUserSymbol,
  numeric,
  orderRecord,
  requireUserPaperOrderCapability,
  requireUserPaperTradingToken,
  userQuote,
  userTradingJson,
  type UserAlpacaError,
} from "../../../../alpaca-user";
import {
  createOrderIntent,
  hasTradingDatabase,
  listOrderIntents,
  updateOrderIntent,
} from "../../../../../db/trading-store";

export const dynamic = "force-dynamic";

type OrderInput = {
  symbol?: unknown;
  side?: unknown;
  qty?: unknown;
  type?: unknown;
  time_in_force?: unknown;
  limit_price?: unknown;
  client_order_id?: unknown;
};

function safeOrderId(value: string): string {
  if (!/^[A-Za-z0-9._-]{1,64}$/.test(value)) throw new Error("invalid_order_id");
  return value;
}

function userErrorStatus(error: unknown): { code: string; message: string } | null {
  const candidate = error as Partial<UserAlpacaError>;
  return typeof candidate.code === "string" && typeof candidate.message === "string" ? { code: candidate.code, message: candidate.message } : null;
}

export async function GET(request: Request): Promise<Response> {
  try {
    const user = await currentUser();
    const query = new URL(request.url).searchParams;
    const environment = query.get("env") === "live" ? "live" : "paper";
    const status = ["open", "closed", "all"].includes(query.get("status") ?? "") ? query.get("status")! : "open";
    const payload = await userTradingJson<unknown[]>(user.userId, environment, `/v2/orders?status=${status}&limit=100&direction=desc&nested=false`);
    const orders = Array.isArray(payload) ? payload.map(orderRecord) : [];
    for (const order of orders) {
      const clientOrderId = typeof order.client_order_id === "string" ? order.client_order_id : null;
      if (clientOrderId) {
        await updateOrderIntent({
          clientOrderId,
          userId: user.userId,
          status: typeof order.status === "string" ? order.status : "unknown",
          brokerOrderId: typeof order.id === "string" ? order.id : null,
          payload: order,
        });
      }
    }
    return Response.json({
      orders,
      source: "Alpaca Trading API via OAuth",
      environment,
      reconciliation: orders.map((order) => ({
        client_order_id: order.client_order_id ?? null,
        broker_order_id: order.id ?? null,
        status: order.status ?? "unknown",
        filled_qty: order.filled_qty ?? "0",
        filled_avg_price: order.filled_avg_price ?? null,
        updated_at: order.updated_at ?? null,
      })),
      local_intents: await listOrderIntents(user.userId, 100),
    });
  } catch (error) {
    return errorResponse(error);
  }
}

export async function POST(request: Request): Promise<Response> {
  let intent: { id: string; clientOrderId: string } | null = null;
  try {
    const user = await currentUser();
    const { config } = await requireUserPaperOrderCapability(user);
    if (!(await hasTradingDatabase())) {
      return Response.json({ error: "execution_ledger_unavailable", message: "A execução está bloqueada porque o ledger persistente não está disponível." }, { status: 503 });
    }
    const body = (await request.json()) as OrderInput;
    const symbol = normalizeUserSymbol(String(body.symbol ?? ""));
    const side = body.side === "buy" || body.side === "sell" ? body.side : null;
    const quantity = numeric(body.qty);
    const type = body.type === "limit" ? "limit" : body.type === "market" ? "market" : null;
    const timeInForce = body.time_in_force === "gtc" ? "gtc" : "day";
    if (!side || !type || quantity == null || !Number.isInteger(quantity) || quantity < 1) {
      return Response.json({ error: "invalid_order", message: "Informe ativo, lado, quantidade inteira e tipo válido." }, { status: 400 });
    }
    if (quantity > config.maxOrderQuantity) {
      return Response.json({ error: "risk_limit_quantity", message: `Quantidade acima do limite do piloto (${config.maxOrderQuantity}).` }, { status: 422 });
    }
    const limitPrice = body.limit_price == null ? null : numeric(body.limit_price);
    if (type === "limit" && (limitPrice == null || limitPrice <= 0)) {
      return Response.json({ error: "invalid_limit_price", message: "Ordens limit precisam de preço positivo." }, { status: 400 });
    }
    const quotePayload = await userQuote(user.userId, "paper", symbol);
    if (quotePayload.data_age_seconds == null || quotePayload.data_age_seconds > 120) {
      return Response.json({ error: "stale_quote", message: "A cotação de referência está ausente ou antiga demais para uma nova ordem." }, { status: 422 });
    }
    const quote = quotePayload.quote;
    const referencePrice = limitPrice ?? (side === "buy" ? quote.ask_price : quote.bid_price) ?? quote.last_price;
    if (!referencePrice || referencePrice <= 0) {
      return Response.json({ error: "quote_unavailable", message: "Não foi possível obter uma cotação de referência." }, { status: 422 });
    }
    const notional = quantity * referencePrice;
    if (notional > config.maxOrderNotionalUsd) {
      return Response.json({ error: "risk_limit_notional", message: `Notional acima do limite do piloto (US$${config.maxOrderNotionalUsd}).` }, { status: 422 });
    }
    if (side === "sell") {
      const positions = await userTradingJson<unknown[]>(user.userId, "paper", "/v2/positions");
      const position = Array.isArray(positions)
        ? positions.find((item) => orderRecord(item).symbol === symbol)
        : null;
      const available = numeric(orderRecord(position).qty);
      if (available == null || quantity > available) {
        return Response.json({ error: "risk_limit_position", message: "Venda acima da posição Paper disponível." }, { status: 422 });
      }
    }
    const clientOrderId = typeof body.client_order_id === "string" && body.client_order_id
      ? safeOrderId(body.client_order_id)
      : `tradinglab-user-paper-${crypto.randomUUID().replaceAll("-", "").slice(0, 20)}`;
    intent = { id: crypto.randomUUID(), clientOrderId };
    await createOrderIntent({
      id: intent.id,
      userId: user.userId,
      environment: "paper",
      clientOrderId,
      symbol,
      side,
      quantity,
      orderType: type,
      timeInForce,
      limitPrice,
      referencePrice,
      notional,
      status: "intent_created",
    });
    const brokerPayload: Record<string, string> = {
      symbol,
      qty: String(quantity),
      side,
      type,
      time_in_force: timeInForce,
      client_order_id: clientOrderId,
    };
    if (limitPrice != null) brokerPayload.limit_price = String(limitPrice);
    const submitted = await userTradingJson<Record<string, unknown>>(user.userId, "paper", "/v2/orders", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(brokerPayload),
    });
    await updateOrderIntent({
      clientOrderId,
      userId: user.userId,
      status: typeof submitted.status === "string" ? submitted.status : "submitted",
      brokerOrderId: typeof submitted.id === "string" ? submitted.id : null,
      eventType: "submitted",
      payload: submitted,
    });
    return Response.json({
      intent: { client_order_id: clientOrderId, symbol, side, quantity, reference_price: referencePrice, notional, risk_limit_usd: config.maxOrderNotionalUsd },
      order: submitted,
      reconciliation: { status: "submitted_to_paper", client_order_id: clientOrderId, broker_order_id: submitted.id ?? null },
      source: "Alpaca Paper Trading API via OAuth",
    }, { status: 201 });
  } catch (error) {
    if (intent) {
      const detail = userErrorStatus(error);
      const user = await getChatGPTUser();
      if (user) {
        await updateOrderIntent({
          clientOrderId: intent.clientOrderId,
          userId: user.userId,
          status: "provider_rejected",
          errorCode: detail?.code ?? "execution_error",
          errorMessage: detail?.message ?? "A ordem não foi aceita.",
          eventType: "provider_rejected",
          payload: { error: detail?.code ?? "execution_error" },
        });
      }
    }
    return errorResponse(error);
  }
}

export async function DELETE(request: Request): Promise<Response> {
  try {
    const user = await currentUser();
    const query = new URL(request.url).searchParams;
    if (query.get("env") === "live") {
      return Response.json({ error: "live_execution_disabled", message: "Cancelamento Live permanece bloqueado nesta versão." }, { status: 423 });
    }
    await requireUserPaperTradingToken(user);
    const orderId = query.get("id");
    if (orderId) {
      const safeId = safeOrderId(orderId);
      await userTradingJson<Record<string, unknown>>(user.userId, "paper", `/v2/orders/${encodeURIComponent(safeId)}`, { method: "DELETE" });
      return Response.json({ canceled: true, order_id: orderId, environment: "paper" });
    }
    const canceled = await userTradingJson<unknown[]>(user.userId, "paper", "/v2/orders", { method: "DELETE" });
    return Response.json({ canceled: true, count: Array.isArray(canceled) ? canceled.length : null, orders: canceled, environment: "paper" });
  } catch (error) {
    return errorResponse(error);
  }
}
