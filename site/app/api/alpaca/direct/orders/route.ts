import {
  alpacaJson,
  errorResponse,
  isOwnerRequest,
  liveQuote,
  normalizeSymbol,
  requireConfiguredPaper,
  requireOrderCapability,
  safeOrderId,
} from "../../../../alpaca-direct";

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

function numeric(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function orderStatus(payload: unknown): Record<string, unknown> {
  return payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};
}

export async function GET(request: Request): Promise<Response> {
  if (!(await isOwnerRequest(request))) return Response.json({ error: "owner_access_required" }, { status: 403 });
  try {
    const query = new URL(request.url).searchParams;
    const status = ["open", "closed", "all"].includes(query.get("status") ?? "") ? query.get("status")! : "open";
    const payload = await alpacaJson(`/v2/orders?status=${status}&limit=100&direction=desc&nested=false`);
    const orders = Array.isArray(payload) ? payload.map(orderStatus) : [];
    return Response.json({
      orders,
      source: "Alpaca Trading API",
      environment: "paper",
      reconciliation: orders.map((order) => ({
        client_order_id: order.client_order_id ?? null,
        broker_order_id: order.id ?? null,
        status: order.status ?? "unknown",
        filled_qty: order.filled_qty ?? "0",
        filled_avg_price: order.filled_avg_price ?? null,
        updated_at: order.updated_at ?? null,
      })),
    });
  } catch (error) {
    return errorResponse(error);
  }
}

export async function POST(request: Request): Promise<Response> {
  if (!(await isOwnerRequest(request))) return Response.json({ error: "owner_access_required" }, { status: 403 });
  try {
    const config = requireOrderCapability();
    const body = (await request.json()) as OrderInput;
    const symbol = normalizeSymbol(String(body.symbol ?? ""));
    const side = body.side === "buy" || body.side === "sell" ? body.side : null;
    const quantity = numeric(body.qty);
    const type = body.type === "limit" ? "limit" : body.type === "market" ? "market" : null;
    const timeInForce = body.time_in_force === "gtc" ? "gtc" : "day";
    if (!side || !type || quantity == null || !Number.isInteger(quantity) || quantity < 1) {
      return Response.json({ error: "invalid_order", message: "Informe ativo, lado, quantidade inteira e tipo válido." }, { status: 400 });
    }
    if (quantity > config.maxOrderQuantity) {
      return Response.json({ error: "risk_limit_quantity", message: `Quantidade acima do limite Paper (${config.maxOrderQuantity}).` }, { status: 422 });
    }
    const limitPrice = body.limit_price == null ? null : numeric(body.limit_price);
    if (type === "limit" && (limitPrice == null || limitPrice <= 0)) {
      return Response.json({ error: "invalid_limit_price", message: "Ordens limit precisam de preço positivo." }, { status: 400 });
    }
    const quotePayload = await liveQuote(symbol);
    const quote = quotePayload.quote;
    if (quotePayload.data_age_seconds == null || quotePayload.data_age_seconds > 120) {
      return Response.json(
        { error: "stale_quote", message: "A cotação de referência está ausente ou antiga demais para uma nova ordem." },
        { status: 422 },
      );
    }
    const referencePrice = limitPrice ?? (side === "buy" ? quote?.ask_price : quote?.bid_price) ?? quote?.last_price;
    if (!referencePrice || referencePrice <= 0) throw new Error("quote unavailable");
    const notional = quantity * referencePrice;
    if (notional > config.maxOrderNotionalUsd) {
      return Response.json({ error: "risk_limit_notional", message: `Notional acima do limite Paper (US$${config.maxOrderNotionalUsd}).` }, { status: 422 });
    }
    if (side === "sell") {
      const positions = await alpacaJson("/v2/positions");
      const position = Array.isArray(positions) ? positions.find((item) => item && typeof item === "object" && (item as Record<string, unknown>).symbol === symbol) as Record<string, unknown> | undefined : undefined;
      const available = numeric(position?.qty);
      if (available == null || quantity > available) {
        return Response.json({ error: "risk_limit_position", message: "Venda acima da posição Paper disponível." }, { status: 422 });
      }
    }
    const clientOrderId = typeof body.client_order_id === "string" && body.client_order_id ? safeOrderId(body.client_order_id) : `tradinglab-paper-${crypto.randomUUID().replaceAll("-", "").slice(0, 20)}`;
    const brokerPayload: Record<string, string> = {
      symbol,
      qty: String(quantity),
      side,
      type,
      time_in_force: timeInForce,
      client_order_id: clientOrderId,
    };
    if (limitPrice != null) brokerPayload.limit_price = String(limitPrice);
    const submitted = await alpacaJson("/v2/orders", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(brokerPayload) });
    return Response.json({
      intent: { client_order_id: clientOrderId, symbol, side, quantity, reference_price: referencePrice, notional, risk_limit_usd: config.maxOrderNotionalUsd },
      order: submitted,
      reconciliation: { status: "submitted_to_paper", client_order_id: clientOrderId, broker_order_id: submitted.id ?? null },
      source: "Alpaca Paper Trading API",
    }, { status: 201 });
  } catch (error) {
    return errorResponse(error);
  }
}

export async function DELETE(request: Request): Promise<Response> {
  if (!(await isOwnerRequest(request))) return Response.json({ error: "owner_access_required" }, { status: 403 });
  try {
    requireConfiguredPaper();
    const query = new URL(request.url).searchParams;
    const orderId = query.get("id");
    if (orderId) {
      const deleted = await alpacaJson(`/v2/orders/${encodeURIComponent(safeOrderId(orderId))}`, { method: "DELETE" });
      return Response.json({ canceled: true, order_id: orderId, provider_response: deleted });
    }
    const canceled = await alpacaJson("/v2/orders", { method: "DELETE" });
    return Response.json({ canceled: true, count: Array.isArray(canceled) ? canceled.length : null, orders: canceled });
  } catch (error) {
    return errorResponse(error);
  }
}
