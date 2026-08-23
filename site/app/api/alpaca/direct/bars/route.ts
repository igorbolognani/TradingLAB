import {
  alpacaJson,
  errorResponse,
  isOwnerRequest,
  normalizeSymbol,
  requireConfiguredPaper,
} from "../../../../alpaca-direct";

export const dynamic = "force-dynamic";

function asNumber(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function sessionFor(timestamp: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }).format(new Date(timestamp));
}

function rolling(values: Array<number | null>, window: number, index: number): number | null {
  if (index + 1 < window) return null;
  const sample = values.slice(index + 1 - window, index + 1).filter((value): value is number => value != null);
  return sample.length === window ? sample.reduce((sum, value) => sum + value, 0) / window : null;
}

export async function GET(request: Request): Promise<Response> {
  if (!(await isOwnerRequest(request))) return Response.json({ error: "owner_access_required" }, { status: 403 });
  try {
    const query = new URL(request.url).searchParams;
    const symbol = normalizeSymbol(query.get("symbol") ?? "SPY");
    const timeframe = ["1Min", "5Min", "15Min", "1Hour", "1Day"].includes(query.get("timeframe") ?? "") ? query.get("timeframe")! : "1Min";
    const requestedLimit = Number(query.get("limit") ?? "120");
    const limit = Number.isInteger(requestedLimit) ? Math.min(500, Math.max(20, requestedLimit)) : 120;
    const retrievedAt = new Date();
    requireConfiguredPaper();
    const lookbackDays = timeframe === "1Day" ? 370 : 10;
    const end = new Date();
    const start = new Date(end.getTime() - lookbackDays * 24 * 60 * 60 * 1000);
    const payload = await alpacaJson(
      `/v2/stocks/${encodeURIComponent(symbol)}/bars?timeframe=${encodeURIComponent(timeframe)}&feed=iex&limit=${limit}&sort=asc&start=${encodeURIComponent(start.toISOString())}&end=${encodeURIComponent(end.toISOString())}`,
      {},
      "https://data.alpaca.markets",
    );
    const barsContainer = payload.bars;
    const bars = Array.isArray(barsContainer)
      ? barsContainer
      : barsContainer && typeof barsContainer === "object" && Array.isArray((barsContainer as Record<string, unknown>)[symbol])
        ? ((barsContainer as Record<string, unknown>)[symbol] as unknown[])
        : [];
    const closes = bars.map((bar) => asNumber((bar as Record<string, unknown>).c));
    const candles = bars.map((raw, index) => {
      const bar = raw as Record<string, unknown>;
      const eventTime = String(bar.t ?? "");
      const open = asNumber(bar.o);
      const high = asNumber(bar.h);
      const low = asNumber(bar.l);
      const close = asNumber(bar.c);
      const volume = asNumber(bar.v);
      return {
        event_time: eventTime,
        receive_time_utc: retrievedAt.toISOString(),
        session: eventTime ? sessionFor(eventTime) : "unknown",
        open,
        high,
        low,
        close,
        volume,
        sma_20: rolling(closes, 20, index),
        sma_50: rolling(closes, 50, index),
        sma_200: rolling(closes, 200, index),
        atr_14: null,
        is_complete: timeframe === "1Day" ? true : index < bars.length - 1,
      };
    });
    const latest = candles.at(-1) ?? null;
    const previous = candles.at(-2) ?? null;
    const close = latest?.close ?? null;
    const change = close != null && previous?.close != null ? close - previous.close : null;
    return Response.json({
      symbol,
      timeframe,
      candles,
      returned_row_count: candles.length,
      available_row_count: candles.length,
      source: {
        provider: "Alpaca Market Data API",
        provider_version: "v2",
        retrieved_at: retrievedAt.toISOString(),
        ingested_at: retrievedAt.toISOString(),
        dataset_id: `alpaca:paper:iex:${symbol}:${timeframe}`,
        dataset_checksum: null,
        manifest_hash: null,
        exchange_calendar: "XNYS",
        source_timezone: "UTC",
        normalized_timezone: "UTC",
        price_basis_id: "alpaca_iex_raw",
        normalization_version: "provider_raw_v1",
        corporate_actions_preserved: false,
        raw_rows_redistributable: false,
      },
      freshness: {
        mode: "alpaca_paper_market_data",
        last_event_time: latest?.event_time ?? null,
        last_session: latest?.session ?? "unknown",
        bar_is_complete: latest?.is_complete ?? null,
        realtime_active: false,
        latency_ms: null,
        latency_scope: null,
        data_age_seconds: latest?.event_time ? Math.max(0, (retrievedAt.getTime() - Date.parse(latest.event_time)) / 1000) : null,
        observed_at: retrievedAt.toISOString(),
        message: "Candles reais da Alpaca IEX. A última barra intraday pode estar incompleta.",
      },
      quality: {
        status: candles.length ? "pass" : "warning",
        row_count: candles.length,
        duplicate_timestamp_count: new Set(candles.map((candle) => candle.event_time)).size === candles.length ? 0 : 1,
        out_of_order_count: 0,
        missing_value_count: candles.filter((candle) => [candle.open, candle.high, candle.low, candle.close, candle.volume].some((value) => value == null)).length,
        invalid_ohlc_count: candles.filter((candle) => candle.high != null && candle.low != null && candle.high < candle.low).length,
        missing_session_count: candles.filter((candle) => candle.session === "unknown").length,
        incomplete_count: candles.filter((candle) => candle.is_complete === false).length,
        unknown_completeness_count: 0,
        errors: [],
        warnings: timeframe === "1Day" ? [] : ["A última barra intraday pode ainda estar em formação."],
        manifest_validation: { valid: false, source_file: "Alpaca live provider response" },
      },
      calculated: {
        latest: latest ? { open: latest.open, high: latest.high, low: latest.low, close: latest.close, volume: latest.volume } : null,
        change,
        change_pct: change != null && previous?.close ? change / previous.close : null,
        session_range_pct: latest?.high != null && latest.low != null && latest.close ? (latest.high - latest.low) / latest.close : null,
        atr_14: null,
        sma_20: latest?.sma_20 ?? null,
        sma_50: latest?.sma_50 ?? null,
        sma_200: latest?.sma_200 ?? null,
        volume_vs_20_session_median: null,
      },
    });
  } catch (error) {
    return errorResponse(error);
  }
}
