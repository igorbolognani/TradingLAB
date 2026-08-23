"use client";

import type { ChangeEvent, PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from "react";
import Image from "next/image";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import PaperControl from "./paper-control";
import { HelpDot, InfoDisclosure } from "./ui";

type ViewId = "landing" | "overview" | "paper" | "market" | "experiments" | "portfolio" | "provenance" | "profile" | "settings" | "help" | "admin";

type ResearchLabProps = {
  isOwner: boolean;
  viewer: { displayName: string; email: string } | null;
  signInHref: string;
  signOutHref: string;
  initialView: "landing" | "overview";
};

type DashboardRow = {
  strategy: string;
  asset: string;
  split: string;
  cagr: number;
  sharpe: number;
  drawdown: number;
  trades: number;
  source: "imported";
};

type RowInput = Record<string, unknown>;

type Candle = {
  event_time: string;
  receive_time_utc?: string | null;
  session: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  sma_20?: number | null;
  sma_50?: number | null;
  sma_200?: number | null;
  atr_14?: number | null;
  is_complete?: boolean | null;
};

type ChartTool = "crosshair" | "pan" | "horizontal" | "trend" | "marker";
type IndicatorKey = "sma_20" | "sma_50" | "sma_200" | "volume";
type ChartDrawing = {
  id: number;
  type: "horizontal" | "trend" | "marker";
  startIndex: number;
  startPrice: number;
  endIndex?: number;
  endPrice?: number;
};
type ChartHover = { index: number; x: number; y: number };

type CandlePayload = {
  symbol: string;
  timeframe: string;
  candles: Candle[];
  returned_row_count: number;
  available_row_count: number;
  source: {
    provider: string;
    provider_version: string;
    retrieved_at: string | null;
    ingested_at?: string | null;
    dataset_id: string;
    dataset_checksum: string | null;
    manifest_hash: string | null;
    exchange_calendar: string;
    source_timezone: string;
    normalized_timezone: string;
    price_basis_id: string;
    normalization_version: string;
    corporate_actions_preserved: boolean;
    raw_rows_redistributable?: boolean;
  };
  freshness: {
    mode: string;
    last_event_time: string | null;
    last_session: string;
    bar_is_complete: boolean | null;
    realtime_active: boolean;
    latency_ms: number | null;
    latency_scope?: string | null;
    data_age_seconds?: number | null;
    observed_at?: string | null;
    message: string;
  };
  quality: {
    status: "pass" | "warning" | "fail";
    row_count: number;
    duplicate_timestamp_count: number;
    out_of_order_count: number;
    missing_value_count: number;
    invalid_ohlc_count: number;
    missing_session_count: number;
    incomplete_count?: number;
    unknown_completeness_count?: number;
    errors: string[];
    warnings: string[];
    manifest_validation?: { valid: boolean; source_file?: string };
  };
  calculated: {
    latest: {
      open: number | null;
      high: number | null;
      low: number | null;
      close: number | null;
      volume: number | null;
    } | null;
    change: number | null;
    change_pct: number | null;
    session_range_pct: number | null;
    atr_14: number | null;
    sma_20: number | null;
    sma_50: number | null;
    sma_200: number | null;
    volume_vs_20_session_median: number | null;
  };
};

type PortfolioPosition = {
  symbol: string;
  quantity: number;
  mark_close?: number;
  market_value?: number;
  weight?: number | null;
};

type PortfolioEquityPoint = {
  session: string;
  cash: number;
  gross_equity: number;
  net_equity: number;
  invested_symbols: string[];
  positions: PortfolioPosition[];
};

type PortfolioPayload = {
  contract: string;
  status: string;
  evidence_class: string;
  dataset: {
    dataset_id: string;
    dataset_checksum: string | null;
    manifest_hash: string | null;
    provider: string;
    provider_version: string;
    retrieved_at: string | null;
    symbols: string[];
    interval: string;
    normalized_timezone: string;
    exchange_calendar: string;
    price_basis_id: string;
    manifest_validation: { valid: boolean };
  };
  configuration: {
    split: string;
    split_label: string;
    evaluation_start: string;
    evaluation_end: string;
    effective_start: string;
    effective_end: string;
    allocation_method: "equal_weight" | "inverse_vol";
    sma_window: number;
    rebalance_every: number;
    volatility_lookback: number;
    friction_bps: number;
    initial_cash: number;
    long_only: boolean;
    integer_shares: boolean;
    leverage: number;
    terminal_convention: string;
  };
  provenance: {
    git_commit: string;
    git_branch: string;
    dirty_worktree: boolean;
    dependency_lock_hash: string;
  };
  metrics: {
    total_return: number;
    CAGR: number;
    annualized_volatility: number | null;
    Sharpe: number | null;
    max_drawdown: number;
    exposure: number;
    turnover: number;
    number_of_trades: number;
    number_of_fills: number;
    number_of_rebalances: number;
    observations: number;
    modeled_costs: number;
    gross_to_net_cost_drag: number;
    final_equity: number;
  };
  decisions: Array<{
    decision_session: string;
    execution_session: string;
    target_symbols: string[];
  }>;
  fills: Array<{
    session: string;
    symbol: string;
    side: string;
    quantity: number;
    price: number;
    modeled_cost: number;
  }>;
  equity: PortfolioEquityPoint[];
  final_positions: PortfolioPosition[];
  safety: {
    project_holdout_evaluated: boolean;
    paper_execution: boolean;
    live_execution: boolean;
    broker_order_submission: boolean;
    automatic_optimization: boolean;
  };
  message: string;
};

const ASSETS = ["SPY", "IWM", "EFA", "TLT", "GLD"] as const;
const STRATEGIES = [
  "CASH_0_V1",
  "BUY_HOLD_V1",
  "TREND_SMA200_V1",
  "MEANREV_Z20_V1",
] as const;
const SPLITS = ["Development", "Validation OOS", "Project Holdout"] as const;

const STRATEGY_LABELS: Record<string, string> = {
  CASH_0_V1: "Cash control",
  BUY_HOLD_V1: "Buy & Hold",
  TREND_SMA200_V1: "Trend SMA200",
  MEANREV_Z20_V1: "Mean Reversion Z20",
  PORTFOLIO_TREND_SMA200_V1: "Portfolio Trend",
};

const SPLIT_LABELS: Record<string, string> = {
  development: "Development",
  validation_oos: "Validation OOS",
  project_holdout: "Project Holdout",
};

const EMPTY_ROWS: DashboardRow[] = [];

function labelForStrategy(strategy: string): string {
  return STRATEGY_LABELS[strategy] ?? strategy.replaceAll("_", " ");
}

function canonicalSplit(value: unknown): string {
  const normalized = String(value ?? "").trim().toLowerCase();
  return SPLIT_LABELS[normalized] ?? String(value ?? "Unknown");
}

function canonicalStrategy(value: unknown): string {
  return String(value ?? "Unknown").trim();
}

function parseNumber(value: unknown): number {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  const parsed = Number(String(value ?? "").replace(",", "."));
  return Number.isFinite(parsed) ? parsed : 0;
}

function normalizedKeys(record: RowInput): Map<string, unknown> {
  return new Map(
    Object.entries(record).map(([key, value]) => [
      key.toLowerCase().replaceAll(/[^a-z0-9]/g, ""),
      value,
    ]),
  );
}

function firstValue(values: Map<string, unknown>, aliases: string[]): unknown {
  for (const alias of aliases) {
    const value = values.get(alias);
    if (value !== undefined && value !== "") return value;
  }
  return undefined;
}

function normalizeRow(record: RowInput): DashboardRow {
  const values = normalizedKeys(record);
  return {
    strategy: canonicalStrategy(
      firstValue(values, ["strategy", "strategyid", "signal"]),
    ),
    asset: String(firstValue(values, ["asset", "symbol", "ticker"]) ?? "Unknown"),
    split: canonicalSplit(
      firstValue(values, ["split", "temporalsplit", "period"]),
    ),
    cagr: parseNumber(firstValue(values, ["cagr", "annualreturn"])),
    sharpe: parseNumber(firstValue(values, ["sharpe", "sharperatio"])),
    drawdown: parseNumber(
      firstValue(values, ["maxdrawdown", "drawdown", "mdd"]),
    ),
    trades: Math.round(
      parseNumber(firstValue(values, ["numberoftrades", "trades", "tradecount"])),
    ),
    source: "imported",
  };
}

function parseCsvLine(line: string): string[] {
  const values: string[] = [];
  let current = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];
    if (character === '"' && line[index + 1] === '"') {
      current += '"';
      index += 1;
    } else if (character === '"') {
      quoted = !quoted;
    } else if (character === "," && !quoted) {
      values.push(current.trim());
      current = "";
    } else {
      current += character;
    }
  }
  values.push(current.trim());
  return values;
}

function canonicalValue(values: Record<string, string>, aliases: string[]): string | undefined {
  for (const alias of aliases) {
    const value = values[alias.toLowerCase()];
    if (value !== undefined && value.trim() !== "") return value.trim();
  }
  return undefined;
}

function parseCandleNumber(value: string | undefined, field: string): number {
  const parsed = Number(value ?? "");
  if (!Number.isFinite(parsed)) throw new Error(`${field} inválido`);
  return parsed;
}

function parseCandleTimestamp(value: string | undefined, field: string): string {
  if (!value) throw new Error(`${field} ausente`);
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error(`${field} precisa informar horário UTC`);
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) throw new Error(`${field} inválido`);
  return parsed.toISOString();
}

function parseCandleBoolean(value: string | undefined): boolean | null {
  if (!value) return null;
  if (["1", "true", "yes", "y"].includes(value.toLowerCase())) return true;
  if (["0", "false", "no", "n"].includes(value.toLowerCase())) return false;
  throw new Error("is_complete inválido");
}

function medianNumber(values: number[]): number | null {
  if (!values.length) return null;
  const ordered = [...values].sort((left, right) => left - right);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2;
}

function parseCandleFile(text: string, filename: string): CandlePayload {
  const lines = text.split(/\r?\n/).filter((line) => line.trim());
  if (lines.length < 2) throw new Error("arquivo sem linhas de candles");
  const headers = parseCsvLine(lines[0]).map((header) => header.toLowerCase());
  const records = lines.slice(1).map((line) => {
    const cells = parseCsvLine(line);
    return Object.fromEntries(headers.map((header, index) => [header, cells[index] ?? ""]));
  });
  const sourceSymbol = canonicalValue(records[0], ["symbol", "ticker"]) ?? "IMPORT";
  const selected = records.filter(
    (record) => (canonicalValue(record, ["symbol", "ticker"]) ?? sourceSymbol) === sourceSymbol,
  );
  const candles: Candle[] = selected.map((record, index) => {
    const eventTime = parseCandleTimestamp(
      canonicalValue(record, ["event_time_utc", "bar_start_utc", "timestamp_utc", "timestamp", "datetime", "date"]),
      `event_time_utc na linha ${index + 2}`,
    );
    const open = parseCandleNumber(canonicalValue(record, ["open"]), "open");
    const high = parseCandleNumber(canonicalValue(record, ["high"]), "high");
    const low = parseCandleNumber(canonicalValue(record, ["low"]), "low");
    const close = parseCandleNumber(canonicalValue(record, ["close"]), "close");
    const volume = parseCandleNumber(canonicalValue(record, ["volume"]), "volume");
    if (open <= 0 || high <= 0 || low <= 0 || close <= 0 || volume < 0) throw new Error(`OHLCV inválido na linha ${index + 2}`);
    if (high < Math.max(open, close, low) || low > Math.min(open, close, high)) throw new Error(`relação OHLC inválida na linha ${index + 2}`);
    const receive = canonicalValue(record, ["receive_time_utc"]);
    return {
      event_time: eventTime,
      receive_time_utc: receive ? parseCandleTimestamp(receive, "receive_time_utc") : null,
      session: canonicalValue(record, ["session_date"]) ?? eventTime.slice(0, 10),
      open,
      high,
      low,
      close,
      volume,
      is_complete: parseCandleBoolean(canonicalValue(record, ["is_complete"])),
    };
  });
  if (!candles.length) throw new Error("nenhum candle compatível encontrado");
  const duplicateCount = candles.length - new Set(candles.map((candle) => candle.event_time)).size;
  const outOfOrderCount = candles.slice(1).filter((candle, index) => candle.event_time < candles[index].event_time).length;
  if (duplicateCount || outOfOrderCount) throw new Error("arquivo possui timestamps duplicados ou fora de ordem");

  const closes = candles.map((candle) => candle.close ?? 0);
  const trueRanges = candles.map((candle, index) => {
    const previousClose = index ? closes[index - 1] : candle.close ?? 0;
    return Math.max(candle.high! - candle.low!, Math.abs(candle.high! - previousClose), Math.abs(candle.low! - previousClose));
  });
  const rolling = (values: number[], window: number, index: number): number | null =>
    index + 1 < window ? null : values.slice(index + 1 - window, index + 1).reduce((sum, value) => sum + value, 0) / window;
  candles.forEach((candle, index) => {
    candle.sma_20 = rolling(closes, 20, index);
    candle.sma_50 = rolling(closes, 50, index);
    candle.sma_200 = rolling(closes, 200, index);
    candle.atr_14 = rolling(trueRanges, 14, index);
  });
  const latest = candles[candles.length - 1];
  const previousClose = candles.length > 1 ? candles[candles.length - 2].close : null;
  const change = previousClose == null ? null : latest.close! - previousClose!;
  const volumeWindow = candles.slice(-20).map((candle) => candle.volume!);
  const volumeMedian = medianNumber(volumeWindow);
  const receiveTimes = candles.flatMap((candle) => (candle.receive_time_utc ? [Date.parse(candle.receive_time_utc) - Date.parse(candle.event_time)] : []));
  const observedAt = new Date();
  const completeValues = candles.map((candle) => candle.is_complete);
  const barIsComplete = completeValues.every((value) => value === true) ? true : completeValues.some((value) => value === false) ? false : null;
  const provider = canonicalValue(records[0], ["provider"]) ?? `arquivo: ${filename}`;
  const providerVersion = canonicalValue(records[0], ["provider_version"]) ?? "tradinglab.candle.v1";
  const priceBasis = canonicalValue(records[0], ["price_basis"]) ?? "unknown";
  const timeframe = canonicalValue(records[0], ["interval", "timeframe"]) ?? "unknown";
  const unknownCompleteness = completeValues.filter((value) => value == null).length;
  const warnings = [
    unknownCompleteness ? `${unknownCompleteness} candles sem completude informada` : "",
    receiveTimes.length ? "" : "receive_time_utc ausente; latência não medida",
  ].filter(Boolean);
  return {
    symbol: sourceSymbol,
    timeframe,
    candles,
    returned_row_count: candles.length,
    available_row_count: candles.length,
    source: {
      provider,
      provider_version: providerVersion,
      retrieved_at: null,
      ingested_at: observedAt.toISOString(),
      dataset_id: `file:${filename}`,
      dataset_checksum: null,
      manifest_hash: null,
      exchange_calendar: "unknown",
      source_timezone: "UTC",
      normalized_timezone: "UTC",
      price_basis_id: priceBasis,
      normalization_version: "tradinglab.candle.v1",
      corporate_actions_preserved: false,
      raw_rows_redistributable: false,
    },
    freshness: {
      mode: "browser_file",
      last_event_time: latest.event_time,
      last_session: latest.session,
      bar_is_complete: barIsComplete,
      realtime_active: false,
      latency_ms: medianNumber(receiveTimes),
      latency_scope: receiveTimes.length ? "event_to_receive" : null,
      data_age_seconds: Math.max(0, (observedAt.getTime() - Date.parse(latest.event_time)) / 1000),
      observed_at: observedAt.toISOString(),
      message: "Arquivo externo validado no navegador; não é um feed realtime.",
    },
    quality: {
      status: warnings.length ? "warning" : "pass",
      row_count: candles.length,
      duplicate_timestamp_count: 0,
      out_of_order_count: 0,
      missing_value_count: 0,
      invalid_ohlc_count: 0,
      missing_session_count: 0,
      incomplete_count: completeValues.filter((value) => value === false).length,
      unknown_completeness_count: unknownCompleteness,
      errors: [],
      warnings,
      manifest_validation: { valid: true, source_file: filename },
    },
    calculated: {
      latest: { open: latest.open, high: latest.high, low: latest.low, close: latest.close, volume: latest.volume },
      change,
      change_pct: change == null || previousClose == null ? null : change / previousClose,
      session_range_pct: (latest.high! - latest.low!) / latest.close!,
      atr_14: latest.atr_14 ?? null,
      sma_20: latest.sma_20 ?? null,
      sma_50: latest.sma_50 ?? null,
      sma_200: latest.sma_200 ?? null,
      volume_vs_20_session_median: volumeMedian ? latest.volume! / volumeMedian : null,
    },
  };
}

function parseCsv(text: string): DashboardRow[] {
  const lines = text.split(/\r?\n/).filter((line) => line.trim());
  if (lines.length < 2) throw new Error("CSV sem linhas de resultados");
  const headers = parseCsvLine(lines[0]);
  return lines
    .slice(1)
    .map((line) => {
      const cells = parseCsvLine(line);
      return normalizeRow(
        Object.fromEntries(headers.map((header, index) => [header, cells[index]])),
      );
    })
    .filter((row) => row.asset !== "Unknown" && row.strategy !== "Unknown");
}

function parseImportedText(text: string, filename: string): DashboardRow[] {
  if (filename.toLowerCase().endsWith(".json")) {
    const payload: unknown = JSON.parse(text);
    const rows = Array.isArray(payload)
      ? payload
      : payload && typeof payload === "object" && "rows" in payload
        ? (payload.rows as unknown)
        : payload && typeof payload === "object" && "trials" in payload
          ? (payload.trials as unknown)
          : [];
    if (!Array.isArray(rows)) throw new Error("JSON sem uma lista rows/trials");
    return rows.map((row) => normalizeRow(row as RowInput));
  }
  return parseCsv(text);
}

function parsePortfolioText(text: string): PortfolioPayload {
  const payload: unknown = JSON.parse(text);
  if (!payload || typeof payload !== "object") {
    throw new Error("JSON de portfólio inválido");
  }
  const candidate = payload as Partial<PortfolioPayload>;
  if (
    candidate.contract !== "tradinglab/v0.6-portfolio/v1" ||
    candidate.status !== "completed" ||
    !Array.isArray(candidate.equity) ||
    !candidate.configuration ||
    !candidate.metrics
  ) {
    throw new Error("JSON não contém um resultado V0.6 completo");
  }
  return payload as PortfolioPayload;
}

function median(values: number[]): number {
  if (!values.length) return 0;
  const ordered = [...values].sort((left, right) => left - right);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2
    ? ordered[middle]
    : (ordered[middle - 1] + ordered[middle]) / 2;
}

function formatPercent(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

function formatOptionalPercent(value: number | null, digits = 1): string {
  return value == null ? "—" : formatPercent(value, digits);
}

function formatSignedPercent(value: number, digits = 1): string {
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${formatPercent(value, digits)}`;
}

function formatNumber(value: number, digits = 2): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function MetricCard({
  label,
  value,
  detail,
  tone = "blue",
}: {
  label: string;
  value: string;
  detail: string;
  tone?: "blue" | "green" | "orange" | "violet";
}) {
  return (
    <article className={`metric-card metric-${tone}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-detail">{detail}</div>
    </article>
  );
}

function EmptyState({ message }: { message: string }) {
  return <div className="empty-state">{message}</div>;
}

function formatPrice(value: number | null | undefined): string {
  return value == null ? "—" : value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

function CandleChart({ candles, symbol, persistDrawings = true }: { candles: Candle[]; symbol: string; persistDrawings?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const dragRef = useRef<{ startX: number; start: number; end: number } | null>(null);
  const drawingIdRef = useRef<number | null>(null);
  const drawingsLoadedRef = useRef(false);
  const valid = useMemo(
    () => candles.filter((candle) => candle.high != null && candle.low != null),
    [candles],
  );
  const [view, setView] = useState({ start: 0, end: 0 });
  const [tool, setTool] = useState<ChartTool>("crosshair");
  const [hover, setHover] = useState<ChartHover | null>(null);
  const [draftDrawing, setDraftDrawing] = useState<ChartDrawing | null>(null);
  const [drawings, setDrawings] = useState<ChartDrawing[]>([]);
  const [indicatorVisibility, setIndicatorVisibility] = useState<Record<IndicatorKey, boolean>>({
    sma_20: true,
    sma_50: true,
    sma_200: true,
    volume: true,
  });
  const viewWindow = useMemo(() => {
    const defaultCount = Math.min(90, valid.length);
    if (!valid.length) return { start: 0, end: 0 };
    const requestedCount = view.end > view.start ? view.end - view.start : defaultCount;
    const count = Math.max(24, Math.min(valid.length, requestedCount));
    const requestedStart = view.end > view.start ? view.start : valid.length - count;
    const start = Math.max(0, Math.min(valid.length - count, requestedStart));
    return { start, end: start + count };
  }, [valid.length, view]);
  const visible = useMemo(() => valid.slice(viewWindow.start, viewWindow.end), [valid, viewWindow]);
  const chartMetrics = useMemo(() => {
    const prices = visible.flatMap((candle) => [candle.high ?? 0, candle.low ?? 0]);
    const maximum = Math.max(...prices, 1);
    const minimum = Math.min(...prices, maximum);
    return { maximum, minimum, range: Math.max(maximum - minimum, Math.abs(maximum) * 0.002, 0.000001) };
  }, [visible]);

  useEffect(() => {
    drawingsLoadedRef.current = false;
    let cancelled = false;
    const loadDrawings = window.setTimeout(() => {
      if (cancelled) return;
      try {
        if (!persistDrawings) {
          setDrawings([]);
          drawingsLoadedRef.current = true;
          return;
        }
        const stored = window.localStorage.getItem(`tradinglab-chart-drawings:${symbol}`);
        const parsed = stored ? JSON.parse(stored) : [];
        setDrawings(Array.isArray(parsed) ? (parsed as ChartDrawing[]) : []);
      } catch {
        setDrawings([]);
      }
      drawingsLoadedRef.current = true;
    }, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(loadDrawings);
    };
  }, [persistDrawings, symbol]);

  useEffect(() => {
    if (!drawingsLoadedRef.current) return;
    if (!persistDrawings) return;
    try {
      window.localStorage.setItem(`tradinglab-chart-drawings:${symbol}`, JSON.stringify(drawings));
    } catch {
      // Drawing persistence is a convenience; chart interaction must still work when storage is unavailable.
    }
  }, [drawings, persistDrawings, symbol]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !visible.length) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    function draw() {
      const rect = canvas.getBoundingClientRect();
      const width = Math.max(320, rect.width);
      const height = 360;
      const pixelRatio = window.devicePixelRatio || 1;
      const left = 60;
      const right = 14;
      const top = 18;
      const priceBottom = 258;
      const volumeTop = 280;
      const volumeBottom = 326;
      const chartWidth = Math.max(120, width - left - right);
      const slot = chartWidth / Math.max(visible.length, 1);
      const bodyWidth = Math.max(2, Math.min(13, slot * 0.62));
      const y = (price: number) => top + ((chartMetrics.maximum - price) / chartMetrics.range) * (priceBottom - top);
      const x = (index: number) => left + (index - viewWindow.start) * slot + slot / 2;
      const volumes = visible.map((candle) => candle.volume ?? 0);
      const maximumVolume = Math.max(...volumes, 1);

      canvas.width = width * pixelRatio;
      canvas.height = height * pixelRatio;
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
      context.clearRect(0, 0, width, height);
      context.fillStyle = "#fbfdff";
      context.fillRect(0, 0, width, height);
      context.font = "10px ui-monospace, monospace";
      context.lineWidth = 1;

      for (let index = 0; index <= 4; index += 1) {
        const gridY = top + ((priceBottom - top) * index) / 4;
        const label = chartMetrics.maximum - (chartMetrics.range * index) / 4;
        context.strokeStyle = "#e5eaf2";
        context.beginPath();
        context.moveTo(left, gridY);
        context.lineTo(width - right, gridY);
        context.stroke();
        context.fillStyle = "#8190a5";
        context.fillText(formatPrice(label), 5, gridY + 3);
      }
      context.fillStyle = "#8190a5";
      context.fillText("volume", left, volumeBottom + 18);

      visible.forEach((candle, index) => {
        const center = x(viewWindow.start + index);
        const open = candle.open ?? candle.close ?? 0;
        const close = candle.close ?? open;
        const high = candle.high ?? Math.max(open, close);
        const low = candle.low ?? Math.min(open, close);
        const rising = close >= open;
        const color = rising ? "#19a974" : "#e36d5c";
        context.strokeStyle = color;
        context.fillStyle = color;
        context.beginPath();
        context.moveTo(center, y(high));
        context.lineTo(center, y(low));
        context.stroke();
        const bodyTop = Math.min(y(open), y(close));
        const bodyHeight = Math.max(1, Math.abs(y(open) - y(close)));
        context.fillRect(center - bodyWidth / 2, bodyTop, bodyWidth, bodyHeight);
        if (indicatorVisibility.volume) {
          const volumeHeight = ((candle.volume ?? 0) / maximumVolume) * (volumeBottom - volumeTop);
          context.globalAlpha = 0.32;
          context.fillRect(center - bodyWidth / 2, volumeBottom - volumeHeight, bodyWidth, volumeHeight);
          context.globalAlpha = 1;
        }
      });

      function drawIndicator(key: Exclude<IndicatorKey, "volume">, color: string) {
        if (!indicatorVisibility[key]) return;
        context.strokeStyle = color;
        context.lineWidth = 1.4;
        context.beginPath();
        let started = false;
        visible.forEach((candle, index) => {
          const indicator = candle[key];
          if (indicator == null) {
            started = false;
            return;
          }
          const center = x(viewWindow.start + index);
          if (started) context.lineTo(center, y(indicator));
          else context.moveTo(center, y(indicator));
          started = true;
        });
        context.stroke();
      }
      drawIndicator("sma_20", "#3267f3");
      drawIndicator("sma_50", "#7a5cf0");
      drawIndicator("sma_200", "#e68a3e");

      context.save();
      context.beginPath();
      context.rect(left, top, chartWidth, priceBottom - top);
      context.clip();
      drawings.concat(draftDrawing ? [draftDrawing] : []).forEach((drawing) => {
        const startX = x(drawing.startIndex);
        const startY = y(drawing.startPrice);
        context.strokeStyle = drawing.type === "horizontal" ? "#3267f3" : drawing.type === "trend" ? "#7a5cf0" : "#e68a3e";
        context.fillStyle = context.strokeStyle;
        context.lineWidth = drawing.type === "marker" ? 2 : 1.4;
        if (drawing.type === "horizontal") {
          context.setLineDash([5, 4]);
          context.beginPath();
          context.moveTo(left, startY);
          context.lineTo(width - right, startY);
          context.stroke();
          context.setLineDash([]);
        } else if (drawing.type === "trend" && drawing.endIndex != null && drawing.endPrice != null) {
          context.beginPath();
          context.moveTo(startX, startY);
          context.lineTo(x(drawing.endIndex), y(drawing.endPrice));
          context.stroke();
        } else if (drawing.type === "marker") {
          context.beginPath();
          context.arc(startX, startY, 4, 0, Math.PI * 2);
          context.fill();
          context.strokeStyle = "#fff";
          context.lineWidth = 1;
          context.stroke();
        }
      });
      context.restore();

      if (hover && hover.index >= viewWindow.start && hover.index < viewWindow.end) {
        const hoverX = x(hover.index);
        context.strokeStyle = "#8a98aa";
        context.setLineDash([3, 3]);
        context.beginPath();
        context.moveTo(hoverX, top);
        context.lineTo(hoverX, volumeBottom);
        context.moveTo(left, hover.y);
        context.lineTo(width - right, hover.y);
        context.stroke();
        context.setLineDash([]);
      }

      context.fillStyle = "#8190a5";
      const labelIndexes = [0, Math.floor((visible.length - 1) / 2), visible.length - 1];
      labelIndexes.forEach((index) => {
        context.fillText(visible[index].session, Math.max(left, x(viewWindow.start + index) - 30), height - 8);
      });
    }

    draw();
    window.addEventListener("resize", draw);
    return () => window.removeEventListener("resize", draw);
  }, [chartMetrics, drawings, draftDrawing, hover, indicatorVisibility, valid, viewWindow, visible]);

  const chartPoint = useCallback((clientX: number, clientY: number) => {
    const canvas = canvasRef.current;
    if (!canvas || !visible.length) return null;
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(320, rect.width);
    const left = 60;
    const right = 14;
    const top = 18;
    const priceBottom = 258;
    const chartWidth = Math.max(120, width - left - right);
    const slot = chartWidth / visible.length;
    const xPosition = Math.max(left, Math.min(width - right, clientX - rect.left));
    const yPosition = Math.max(top, Math.min(priceBottom, clientY - rect.top));
    const localIndex = Math.max(0, Math.min(visible.length - 1, Math.floor((xPosition - left) / slot)));
    const price = chartMetrics.maximum - ((yPosition - top) / (priceBottom - top)) * chartMetrics.range;
    return { x: xPosition, y: yPosition, index: viewWindow.start + localIndex, price };
  }, [chartMetrics, viewWindow.start, visible.length]);

  function nextDrawing(drawing: Omit<ChartDrawing, "id">): ChartDrawing {
    if (drawingIdRef.current == null) drawingIdRef.current = Date.now();
    drawingIdRef.current += 1;
    return { ...drawing, id: drawingIdRef.current };
  }

  function handlePointerDown(event: ReactPointerEvent<HTMLCanvasElement>) {
    const point = chartPoint(event.clientX, event.clientY);
    if (!point) return;
    // A touch on the inspection tool should still be able to scroll the page.
    // Drawing and pan tools keep capture so their gesture remains inside the chart.
    if (event.pointerType !== "touch" || tool !== "crosshair") {
      event.currentTarget.setPointerCapture(event.pointerId);
    }
    setHover({ index: point.index, x: point.x, y: point.y });
    if (tool === "pan") {
      dragRef.current = { startX: point.x, start: viewWindow.start, end: viewWindow.end };
    } else if (tool === "horizontal") {
      setDrawings((current) => [...current, nextDrawing({ type: "horizontal", startIndex: point.index, startPrice: point.price })]);
      setTool("crosshair");
    } else if (tool === "marker") {
      setDrawings((current) => [...current, nextDrawing({ type: "marker", startIndex: point.index, startPrice: point.price })]);
      setTool("crosshair");
    } else if (tool === "trend") {
      setDraftDrawing(nextDrawing({ type: "trend", startIndex: point.index, startPrice: point.price }));
    }
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLCanvasElement>) {
    const point = chartPoint(event.clientX, event.clientY);
    if (!point) return;
    setHover({ index: point.index, x: point.x, y: point.y });
    if (dragRef.current) {
      const current = dragRef.current;
      const count = current.end - current.start;
      const shift = Math.round(((current.startX - point.x) / Math.max(120, event.currentTarget.getBoundingClientRect().width - 74)) * count);
      const start = Math.max(0, Math.min(valid.length - count, current.start + shift));
      setView({ start, end: start + count });
    }
    if (draftDrawing?.type === "trend") {
      setDraftDrawing({ ...draftDrawing, endIndex: point.index, endPrice: point.price });
    }
  }

  function handlePointerUp(event: ReactPointerEvent<HTMLCanvasElement>) {
    const point = chartPoint(event.clientX, event.clientY);
    dragRef.current = null;
    if (draftDrawing?.type === "trend" && point) {
      setDrawings((current) => [...current, { ...draftDrawing, endIndex: point.index, endPrice: point.price }]);
      setDraftDrawing(null);
      setTool("crosshair");
    }
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const handleNativeWheel = (event: WheelEvent) => {
      if (!visible.length || valid.length <= 24) return;
      event.preventDefault();
      event.stopPropagation();
      const point = chartPoint(event.clientX, event.clientY);
      if (!point) return;
      const currentCount = viewWindow.end - viewWindow.start;
      const step = Math.max(4, Math.round(currentCount * 0.18));
      const nextCount = Math.max(24, Math.min(valid.length, currentCount + (event.deltaY > 0 ? step : -step)));
      const rect = canvas.getBoundingClientRect();
      const chartWidth = Math.max(120, rect.width - 74);
      const ratio = Math.max(0, Math.min(1, (point.x - 60) / chartWidth));
      const anchor = viewWindow.start + Math.floor(ratio * currentCount);
      const start = Math.max(0, Math.min(valid.length - nextCount, anchor - Math.floor(ratio * nextCount)));
      setView({ start, end: start + nextCount });
      setHover(null);
    };

    canvas.addEventListener("wheel", handleNativeWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", handleNativeWheel);
  }, [chartMetrics, chartPoint, valid.length, viewWindow, visible.length]);

  function preventChartScroll(event: ReactWheelEvent<HTMLCanvasElement>) {
    event.preventDefault();
    event.stopPropagation();
  }

  function resetView() {
    const count = Math.min(90, valid.length);
    setView({ start: Math.max(0, valid.length - count), end: valid.length });
    setHover(null);
  }

  const activeCandle = hover ? valid[hover.index] : null;
  const toolLabels: Array<[ChartTool, string]> = [["crosshair", "Cursor"], ["pan", "Mover"], ["horizontal", "Nível"], ["trend", "Linha"], ["marker", "Marcar"]];

  return (
    <div className="interactive-chart-shell">
      <div className="chart-toolbar" role="toolbar" aria-label="Ferramentas do gráfico">
        <div className="chart-tool-group">{toolLabels.map(([value, label]) => <button key={value} type="button" className={`chart-tool-button ${tool === value ? "active" : ""}`} onClick={() => setTool(value)} title={value === "crosshair" ? "Mover o cursor e inspecionar uma barra" : value === "pan" ? "Arrastar para navegar no histórico" : value === "horizontal" ? "Adicionar um nível horizontal" : value === "trend" ? "Desenhar uma linha de tendência" : "Adicionar um marcador"}>{label}</button>)}</div>
        <span className="chart-toolbar-divider" />
        <div className="chart-indicator-group" aria-label="Indicadores visíveis">
          {(["sma_20", "sma_50", "sma_200", "volume"] as IndicatorKey[]).map((key) => <button key={key} type="button" className={`chart-indicator-button indicator-${key} ${indicatorVisibility[key] ? "active" : ""}`} onClick={() => setIndicatorVisibility((current) => ({ ...current, [key]: !current[key] }))}>{key === "volume" ? "VOL" : key.replace("sma_", "SMA ")}</button>)}
        </div>
        <button type="button" className="chart-tool-button" onClick={resetView}>Ajustar</button>
        <button type="button" className="chart-tool-button" onClick={() => setDrawings((current) => current.slice(0, -1))} disabled={!drawings.length}>Desfazer</button>
        <button type="button" className="chart-tool-button chart-clear-button" onClick={() => setDrawings([])} disabled={!drawings.length}>Limpar</button>
      </div>
      <div className={`chart-stage chart-stage-${tool}`}>
        <canvas ref={canvasRef} className="candle-canvas" aria-label={`Gráfico interativo de candles ${symbol}`} onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerUp={handlePointerUp} onPointerCancel={handlePointerUp} onPointerLeave={() => { if (!dragRef.current) setHover(null); }} onWheel={preventChartScroll} onDoubleClick={resetView} />
        {activeCandle && hover ? <div className="chart-tooltip" style={{ left: `${Math.min(Math.max(hover.x + 14, 10), 260)}px`, top: `${Math.min(Math.max(hover.y + 12, 10), 245)}px` }}><div className="chart-tooltip-heading"><strong>{activeCandle.session}</strong><span>{activeCandle.is_complete === false ? "aberta" : "encerrada"}</span></div><div className="chart-tooltip-grid"><span>O <b>{formatPrice(activeCandle.open)}</b></span><span>H <b>{formatPrice(activeCandle.high)}</b></span><span>L <b>{formatPrice(activeCandle.low)}</b></span><span>C <b>{formatPrice(activeCandle.close)}</b></span><span>VOL <b>{activeCandle.volume == null ? "—" : Math.round(activeCandle.volume).toLocaleString("en-US")}</b></span><span>Δ <b>{activeCandle.close != null && activeCandle.open != null ? formatSignedPercent((activeCandle.close - activeCandle.open) / activeCandle.open) : "—"}</b></span></div></div> : null}
      </div>
      <div className="chart-footer"><span>Roda: zoom · arraste com <strong>Mover</strong> · clique para marcar · duplo clique para ajustar</span><span>{viewWindow.start + 1}–{viewWindow.end} de {valid.length} barras</span></div>
    </div>
  );
}

function PortfolioChart({ equity }: { equity: PortfolioEquityPoint[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !equity.length) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    function draw() {
      const rect = canvas.getBoundingClientRect();
      const width = Math.max(320, rect.width);
      const height = 300;
      const pixelRatio = window.devicePixelRatio || 1;
      canvas.width = width * pixelRatio;
      canvas.height = height * pixelRatio;
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
      context.clearRect(0, 0, width, height);

      const values = equity.map((point) => point.net_equity);
      const maximum = Math.max(...values);
      const minimum = Math.min(...values);
      const range = Math.max(maximum - minimum, 0.000001);
      const left = 68;
      const right = 16;
      const top = 20;
      const bottom = 250;
      const chartWidth = width - left - right;
      const x = (index: number) => left + (chartWidth * index) / Math.max(values.length - 1, 1);
      const y = (value: number) => top + ((maximum - value) / range) * (bottom - top);

      context.font = "10px ui-monospace, monospace";
      context.lineWidth = 1;
      for (let index = 0; index <= 4; index += 1) {
        const gridY = top + ((bottom - top) * index) / 4;
        const label = maximum - (range * index) / 4;
        context.strokeStyle = "#e5eaf2";
        context.beginPath();
        context.moveTo(left, gridY);
        context.lineTo(width - right, gridY);
        context.stroke();
        context.fillStyle = "#8190a5";
        context.fillText(formatPrice(label), 5, gridY + 3);
      }

      context.strokeStyle = "#3267f3";
      context.lineWidth = 2;
      context.beginPath();
      values.forEach((value, index) => {
        const pointX = x(index);
        const pointY = y(value);
        if (index === 0) context.moveTo(pointX, pointY);
        else context.lineTo(pointX, pointY);
      });
      context.stroke();

      context.fillStyle = "#8190a5";
      const labelIndexes = [0, Math.floor((equity.length - 1) / 2), equity.length - 1];
      labelIndexes.forEach((index) => {
        context.fillText(equity[index].session, Math.max(left, x(index) - 30), height - 10);
      });
    }

    draw();
    window.addEventListener("resize", draw);
    return () => window.removeEventListener("resize", draw);
  }, [equity]);

  return <canvas ref={canvasRef} className="portfolio-canvas" aria-label="Curva de patrimônio do portfólio" />;
}

function AppMark() {
  // This is a tiny local SVG mark; image optimization would add overhead for a 128px asset.
  // eslint-disable-next-line @next/next/no-img-element
  return <img className="app-mark" src="/tradinglab-mark.svg" alt="" aria-hidden="true" />;
}

export default function ResearchLab({ isOwner, viewer, signInHref, signOutHref, initialView }: ResearchLabProps) {
  const [activeView, setActiveView] = useState<ViewId>(initialView);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [tooltipsEnabled, setTooltipsEnabled] = useState(true);
  const [compactMode, setCompactMode] = useState(false);
  const [persistDrawings, setPersistDrawings] = useState(true);
  const [strategy, setStrategy] = useState("ALL");
  const [asset, setAsset] = useState("ALL");
  const [split, setSplit] = useState("ALL");
  const [rows, setRows] = useState<DashboardRow[]>(EMPTY_ROWS);
  const [dataLabel, setDataLabel] = useState("No dataset loaded");
  const [notice, setNotice] = useState("");
  const [localApiAvailable, setLocalApiAvailable] = useState(false);
  const [localDatasetId, setLocalDatasetId] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [candleSymbol, setCandleSymbol] = useState("SPY");
  const [candleLimit, setCandleLimit] = useState("240");
  const [candlePayload, setCandlePayload] = useState<CandlePayload | null>(null);
  const [isLoadingCandles, setIsLoadingCandles] = useState(false);
  const [candleNotice, setCandleNotice] = useState("");
  const [candleSource, setCandleSource] = useState<"snapshot" | "external_file" | "browser_file">("snapshot");
  const [externalFileAvailable, setExternalFileAvailable] = useState(false);
  const [portfolioPayload, setPortfolioPayload] = useState<PortfolioPayload | null>(null);
  const [portfolioSplit, setPortfolioSplit] = useState("development");
  const [portfolioMethod, setPortfolioMethod] = useState<"equal_weight" | "inverse_vol">("equal_weight");
  const [portfolioFriction, setPortfolioFriction] = useState("5");
  const [isRunningPortfolio, setIsRunningPortfolio] = useState(false);
  const [portfolioNotice, setPortfolioNotice] = useState("");
  const [alpacaConnection, setAlpacaConnection] = useState<"loading" | "connected" | "disconnected">("disconnected");
  const fileInput = useRef<HTMLInputElement>(null);
  const candleFileInput = useRef<HTMLInputElement>(null);
  const portfolioFileInput = useRef<HTMLInputElement>(null);
  const autoLoadedDatasetRef = useRef<string | null>(null);

  useEffect(() => {
    const loadSettings = window.setTimeout(() => {
      try {
        const stored = JSON.parse(window.localStorage.getItem("tradinglab-ui-settings") ?? "{}");
        if (typeof stored.tooltipsEnabled === "boolean") setTooltipsEnabled(stored.tooltipsEnabled);
        if (typeof stored.compactMode === "boolean") setCompactMode(stored.compactMode);
        if (typeof stored.persistDrawings === "boolean") setPersistDrawings(stored.persistDrawings);
      } catch {
        // UI preferences are optional; the workspace remains usable when storage is unavailable.
      }
    }, 0);
    return () => window.clearTimeout(loadSettings);
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        "tradinglab-ui-settings",
        JSON.stringify({ tooltipsEnabled, compactMode, persistDrawings }),
      );
    } catch {
      // UI preferences are best-effort only.
    }
  }, [compactMode, persistDrawings, tooltipsEnabled]);

  const navigate = useCallback((view: ViewId) => {
    setActiveView(view);
    setSidebarOpen(false);
  }, []);

  useEffect(() => {
    if (!isOwner) return;
    let active = true;
    fetch("/api/alpaca/direct/status", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("status unavailable");
        return (await response.json()) as { configured?: boolean };
      })
      .then((payload) => {
        if (active) setAlpacaConnection(payload.configured ? "connected" : "disconnected");
      })
      .catch(() => {
        if (active) setAlpacaConnection("disconnected");
      });
    return () => {
      active = false;
    };
  }, [isOwner]);

  useEffect(() => {
    if (!isOwner) {
      const clearPrivateState = window.setTimeout(() => {
        setLocalApiAvailable(false);
        setLocalDatasetId("");
        setExternalFileAvailable(false);
      }, 0);
      return () => window.clearTimeout(clearPrivateState);
    }
    let active = true;
    fetch("http://127.0.0.1:8787/api/health")
      .then(async (response) => {
        if (!response.ok) throw new Error("local API unavailable");
        return (await response.json()) as {
          dataset_ids?: string[];
          recommended_dataset_id?: string | null;
          capabilities?: {
            configured_external_file?: boolean;
            portfolio_reference?: boolean;
          };
        };
      })
      .then((payload) => {
        if (!active) return;
        setLocalApiAvailable(true);
        setLocalDatasetId(payload.recommended_dataset_id ?? payload.dataset_ids?.at(-1) ?? "");
        const hasExternalFile = Boolean(payload.capabilities?.configured_external_file);
        setExternalFileAvailable(hasExternalFile);
        if (!payload.recommended_dataset_id && hasExternalFile) setCandleSource("external_file");
      })
      .catch(() => {
        if (active) setLocalApiAvailable(false);
      });
    return () => {
      active = false;
    };
  }, [isOwner]);

  useEffect(() => {
    if (
      !isOwner ||
      !localApiAvailable ||
      !localDatasetId ||
      candleSource !== "snapshot" ||
      candlePayload ||
      autoLoadedDatasetRef.current === localDatasetId
    ) {
      return;
    }

    autoLoadedDatasetRef.current = localDatasetId;
    let active = true;
    setIsLoadingCandles(true);
    setCandleNotice("Conectando o gráfico ao snapshot validado…");
    const query = new URLSearchParams({ dataset_id: localDatasetId, symbol: "SPY", limit: "240" });
    fetch(`http://127.0.0.1:8787/api/candles?${query.toString()}`)
      .then(async (response) => {
        const payload = (await response.json()) as CandlePayload & { error?: string };
        if (!response.ok) throw new Error(payload.error ?? "snapshot recusado");
        return payload;
      })
      .then((payload) => {
        if (!active) return;
        setCandlePayload(payload);
        setCandleSymbol(payload.symbol);
        setCandleNotice(`${payload.returned_row_count.toLocaleString("en-US")} candles reais carregados automaticamente.`);
      })
      .catch((error) => {
        if (active) setCandleNotice(`O gráfico está pronto, mas o snapshot não respondeu: ${error instanceof Error ? error.message : "erro desconhecido"}.`);
      })
      .finally(() => {
        if (active) setIsLoadingCandles(false);
      });

    return () => {
      active = false;
    };
  }, [candlePayload, candleSource, isOwner, localApiAvailable, localDatasetId]);

  const filteredRows = useMemo(
    () =>
      rows.filter(
        (row) =>
          (strategy === "ALL" || row.strategy === strategy) &&
          (asset === "ALL" || row.asset === asset) &&
          (split === "ALL" || row.split === split),
      ),
    [asset, rows, split, strategy],
  );

  const metrics = useMemo(() => {
    const cagr = median(filteredRows.map((row) => row.cagr));
    const sharpe = median(filteredRows.map((row) => row.sharpe));
    const drawdown = median(filteredRows.map((row) => row.drawdown));
    const trades = filteredRows.reduce((total, row) => total + row.trades, 0);
    return { cagr, sharpe, drawdown, trades };
  }, [filteredRows]);

  const chartRows = useMemo(
    () =>
      STRATEGIES.map((item) => ({
        strategy: item,
        value: median(
          filteredRows
            .filter((row) => row.strategy === item)
            .map((row) => row.cagr),
        ),
      })),
    [filteredRows],
  );

  const command = useMemo(() => {
    const specMap: Record<string, string> = {
      CASH_0_V1: "strategy_specs/CASH_0_V1.yaml",
      BUY_HOLD_V1: "strategy_specs/BUY_HOLD_V1.yaml",
      TREND_SMA200_V1: "strategy_specs/TREND_SMA200_V1.yaml",
      MEANREV_Z20_V1: "strategy_specs/MEANREV_Z20_V1.yaml",
    };
    const selectedStrategy = strategy === "ALL" ? "TREND_SMA200_V1" : strategy;
    const selectedAsset = asset === "ALL" ? "SPY" : asset;
    const selectedSplit =
      split === "ALL" ? "development" : split.toLowerCase().replaceAll(" ", "_");
    return `uv run tradinglab run --spec ${specMap[selectedStrategy]} --dataset-id <dataset_id> --asset ${selectedAsset} --split ${selectedSplit} --parameters-json '{}' --friction-bps 5 --purpose primary`;
  }, [asset, split, strategy]);

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const imported = parseImportedText(await file.text(), file.name);
      if (!imported.length) throw new Error("nenhuma linha compatível encontrada");
      setRows(imported);
      setDataLabel(`Importado: ${file.name}`);
      setNotice(`${imported.length.toLocaleString("en-US")} linhas carregadas no navegador.`);
    } catch (error) {
      setNotice(
        `Não foi possível ler o arquivo: ${error instanceof Error ? error.message : "formato inválido"}.`,
      );
    } finally {
      event.target.value = "";
    }
  }

  async function handleCandleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const payload = parseCandleFile(await file.text(), file.name);
      setCandlePayload(payload);
      setCandleSource("browser_file");
      setCandleSymbol(payload.symbol);
      setCandleNotice(`${payload.returned_row_count.toLocaleString("en-US")} candles reais importados no navegador; nenhum dado foi enviado ao servidor.`);
    } catch (error) {
      setCandlePayload(null);
      setCandleNotice(`Não foi possível ler o arquivo de candles: ${error instanceof Error ? error.message : "formato inválido"}.`);
    } finally {
      event.target.value = "";
    }
  }

  function resetData() {
    setRows(EMPTY_ROWS);
    setDataLabel("No dataset loaded");
    setNotice("Nenhum dado local carregado. Importe all_trials.csv ou JSON.");
  }

  async function copyCommand() {
    await navigator.clipboard.writeText(command);
    setNotice("Comando copiado. Execute-o na raiz do repositório local.");
  }

  async function runLocalBattery() {
    if (!localApiAvailable || !localDatasetId) {
      setNotice("Inicie o servidor local com `uv run tradinglab-dashboard` para executar.");
      return;
    }
    if (split === "Project Holdout") {
      setNotice("O Project Holdout permanece bloqueado para execução pela interface.");
      return;
    }
    if (!window.confirm("Executar a bateria local de pesquisa sem holdout?")) return;
    setIsRunning(true);
    setNotice("Executando Development/Validation localmente…");
    try {
      const response = await fetch("http://127.0.0.1:8787/api/run-battery", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          dataset_id: localDatasetId,
          splits: split === "Validation OOS" ? ["validation_oos"] : ["development"],
          confirmed: true,
        }),
      });
      const payload = (await response.json()) as { message?: string; error?: string };
      if (!response.ok) throw new Error(payload.error ?? "execução recusada");
      setNotice(payload.message ?? "Execução local concluída.");
    } catch (error) {
      setNotice(
        `A execução local falhou: ${error instanceof Error ? error.message : "erro desconhecido"}.`,
      );
    } finally {
      setIsRunning(false);
    }
  }

  async function loadCandles() {
    if (candleSource === "browser_file") {
      setCandleNotice("A fonte atual é um arquivo carregado no navegador; selecione outra fonte para atualizar.");
      return;
    }
    if (!localApiAvailable || (candleSource === "snapshot" && !localDatasetId)) {
      setCandleNotice("Inicie `uv run tradinglab-dashboard` para carregar o snapshot real local.");
      return;
    }
    setIsLoadingCandles(true);
    setCandleNotice("Validando manifesto, checksum e candles…");
    try {
      const query = new URLSearchParams({ symbol: candleSymbol, limit: candleLimit });
      if (candleSource === "snapshot") query.set("dataset_id", localDatasetId);
      const endpoint = candleSource === "external_file" ? "api/candles-file" : "api/candles";
      const response = await fetch(`http://127.0.0.1:8787/${endpoint}?${query.toString()}`);
      const payload = (await response.json()) as CandlePayload & { error?: string };
      if (!response.ok) throw new Error(payload.error ?? "snapshot recusado");
      setCandlePayload(payload);
      setCandleNotice(`${payload.returned_row_count.toLocaleString("en-US")} candles reais carregados; sem feed realtime ativo.`);
    } catch (error) {
      setCandlePayload(null);
      setCandleNotice(`Não foi possível carregar os candles: ${error instanceof Error ? error.message : "erro desconhecido"}.`);
    } finally {
      setIsLoadingCandles(false);
    }
  }

  async function handlePortfolioFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const imported = parsePortfolioText(await file.text());
      setPortfolioPayload(imported);
      setPortfolioSplit(imported.configuration.split);
      setPortfolioMethod(imported.configuration.allocation_method);
      setPortfolioFriction(String(imported.configuration.friction_bps));
      setPortfolioNotice(`Resultado V0.6 carregado no navegador: ${file.name}.`);
    } catch (error) {
      setPortfolioPayload(null);
      setPortfolioNotice(
        `Não foi possível ler o resultado V0.6: ${error instanceof Error ? error.message : "JSON inválido"}.`,
      );
    } finally {
      event.target.value = "";
    }
  }

  async function runLocalPortfolio() {
    if (!localApiAvailable || !localDatasetId) {
      setPortfolioNotice("Inicie o servidor local com `uv run tradinglab-dashboard` para executar o portfólio.");
      return;
    }
    if (!window.confirm("Executar o replay V0.6 com caixa simulado e sem holdout?")) return;
    setIsRunningPortfolio(true);
    setPortfolioNotice("Validando o snapshot completo e executando o replay V0.6…");
    try {
      const response = await fetch("http://127.0.0.1:8787/api/run-portfolio", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          confirmed: true,
          dataset_id: localDatasetId,
          split: portfolioSplit,
          allocation_method: portfolioMethod,
          friction_bps: Number(portfolioFriction),
        }),
      });
      const payload = (await response.json()) as PortfolioPayload & { error?: string };
      if (!response.ok) throw new Error(payload.error ?? "replay recusado");
      setPortfolioPayload(payload);
      setPortfolioNotice(`${payload.configuration.split_label}: ${payload.equity.length.toLocaleString("en-US")} sessões reproduzidas com dados reais.`);
    } catch (error) {
      setPortfolioPayload(null);
      setPortfolioNotice(
        `O replay V0.6 falhou: ${error instanceof Error ? error.message : "erro desconhecido"}.`,
      );
    } finally {
      setIsRunningPortfolio(false);
    }
  }

  function renderMarketPreview({ publicMode = false }: { publicMode?: boolean } = {}) {
    const market = candlePayload;
    const latest = market?.calculated.latest;
    const calculated = market?.calculated;
    const canUsePrivateSnapshot = isOwner && !publicMode && Boolean(localDatasetId);
    const sourceLabel = publicMode || !canUsePrivateSnapshot ? "CSV deste navegador" : "Snapshot privado";

    return (
      <section id={publicMode ? "market-preview" : undefined} className={`panel chart-workspace-card ${publicMode ? "chart-workspace-public" : ""}`}>
        <div className="panel-heading">
          <div>
            <div className="panel-kicker">{publicMode ? "Market workspace" : "Chart workspace"}</div>
            <h2>{publicMode ? "Gráfico de mercado" : "Seu gráfico principal"}</h2>
            <p className="panel-copy">{publicMode ? "Veja como o workspace funciona e carregue um CSV real para experimentar candles, zoom, cursor e marcações." : "O gráfico fica no centro do trabalho: acompanhe preço, volume, indicadores e contexto antes de abrir outra ferramenta."}</p>
          </div>
          <span className={`api-badge ${market ? "api-online" : "api-offline"}`}><span />{market ? `${market.symbol} · ${market.freshness.realtime_active ? "tempo real" : "histórico"}` : publicMode ? "pronto para dados" : localApiAvailable ? "snapshot conectado" : "aguardando fonte"}</span>
        </div>
        <div className="chart-workspace-controls">
          <div className="chart-source-note"><span>FONTE</span><strong>{market ? market.source.provider : sourceLabel}</strong></div>
          <label htmlFor={publicMode ? "public-candle-symbol" : "overview-candle-symbol"}>Ativo<select id={publicMode ? "public-candle-symbol" : "overview-candle-symbol"} value={candleSymbol} onChange={(event) => setCandleSymbol(event.target.value)}>{ASSETS.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
          <label htmlFor={publicMode ? "public-candle-limit" : "overview-candle-limit"}>Histórico<select id={publicMode ? "public-candle-limit" : "overview-candle-limit"} value={candleLimit} onChange={(event) => setCandleLimit(event.target.value)}><option value="120">120 barras</option><option value="240">240 barras</option><option value="500">500 barras</option><option value="1000">1.000 barras</option></select></label>
          <div className="chart-workspace-actions">
            {canUsePrivateSnapshot ? <button className="button button-primary" type="button" onClick={() => void loadCandles()} disabled={isLoadingCandles}>{isLoadingCandles ? "Validando…" : "Atualizar gráfico"}</button> : null}
            <button className="button button-outline" type="button" onClick={() => candleFileInput.current?.click()}>Inserir CSV</button>
            <input ref={candleFileInput} className="visually-hidden" type="file" accept=".csv,text/csv" onChange={(event) => void handleCandleFile(event)} />
          </div>
        </div>
        {candleNotice ? <div className="notice" role="status">{candleNotice}</div> : null}
        {market ? (
          <>
            <div className="chart-market-summary" aria-label="Resumo do ativo">
              <div><span>ÚLTIMO</span><strong>{formatPrice(latest?.close)}</strong></div>
              <div><span>VARIAÇÃO</span><strong className={(calculated?.change_pct ?? 0) >= 0 ? "positive" : "negative"}>{formatOptionalPercent(calculated?.change_pct ?? null)}</strong></div>
              <div><span>SMA 200</span><strong>{formatPrice(calculated?.sma_200)}</strong></div>
              <div><span>ATR 14</span><strong>{formatPrice(calculated?.atr_14)}</strong></div>
              <div><span>ÚLTIMA SESSÃO</span><strong>{market.freshness.last_session}</strong></div>
            </div>
            <CandleChart candles={market.candles} symbol={market.symbol} persistDrawings={persistDrawings} />
          </>
        ) : (
          <div className="chart-empty-state">
            <div className="chart-empty-grid" aria-hidden="true"><span /><span /><span /><span /><i /><i /><i /></div>
            <div className="chart-empty-copy"><div className="panel-kicker">Área de trabalho pronta</div><h3>{publicMode ? "Insira dados reais para começar" : "O gráfico será preenchido ao conectar uma fonte"}</h3><p>{publicMode ? "O arquivo permanece no seu navegador e não é enviado para o TradingLAB. Depois de carregar, use Cursor, Mover, Nível, Linha e Marcar." : "No computador do laboratório, o snapshot privado é carregado automaticamente. Se estiver em outro dispositivo, insira um CSV validado para trabalhar localmente."}</p><button className="button button-primary" type="button" onClick={() => candleFileInput.current?.click()}>Inserir candles</button></div>
          </div>
        )}
        <div className="chart-footnote">{market ? `${market.freshness.message} Os indicadores são calculados sobre a série completa antes do recorte visual.` : "Nenhum preço é inventado: sem dados válidos, o gráfico permanece vazio."}</div>
      </section>
    );
  }

  function renderLanding() {
    return (
      <section className="landing page-stack">
        <section className="landing-hero">
          <div className="landing-hero-copy">
            <div className="eyebrow">Trading workspace · V1.0</div>
            <h1>O mercado em um espaço de trabalho mais claro.</h1>
            <p className="hero-copy">Gráficos, métricas e simulações em uma interface profissional para observar, testar e acompanhar decisões com capital virtual.</p>
            <div className="hero-actions">
              {viewer ? <button className="button button-primary" onClick={() => navigate("overview")}>Abrir aplicativo <span aria-hidden="true">→</span></button> : <a className="button button-primary" href={signInHref}>Entrar com ChatGPT <span aria-hidden="true">→</span></a>}
            </div>
            <div className="landing-trust" aria-label="Princípios do produto">
              <span><i>✓</i> dados com origem</span>
              <span><i>✓</i> capital virtual</span>
              <span><i>✓</i> controle por usuário</span>
            </div>
          </div>
          <div className="landing-signal-card" aria-label="Fluxo de uso das ferramentas TradingLAB">
            <div className="landing-card-top"><span className="panel-kicker">Workspace preview</span><span className="live-badge"><b /> paper / virtual</span></div>
            <div className="landing-signal-title">Observe antes de agir</div>
            <div className="product-flow">
              <div><span>01</span><strong>Mercado</strong><small>candles, volume e indicadores</small></div>
              <div><span>02</span><strong>Cenário</strong><small>ativo, período e regra explícita</small></div>
              <div><span>03</span><strong>Replay</strong><small>patrimônio, custos e risco</small></div>
            </div>
            <div className="landing-card-footer"><span>TRADINGLAB</span><strong>clareza antes da execução</strong></div>
          </div>
        </section>

        {renderMarketPreview({ publicMode: true })}

        <section id="public-features" className="landing-section">
          <div className="section-intro"><div className="eyebrow">O produto</div><h2>As ferramentas essenciais, no mesmo espaço.</h2><p>O aplicativo adapta o workspace ao acesso da pessoa: mercado, gráficos, simulações, conta Paper autorizada e controles privados quando disponíveis.</p></div>
          <div className="landing-feature-grid">
            <article className="landing-feature"><span className="feature-number">01</span><h3>Gráfico interativo</h3><p>Candles, zoom, cursor, linhas, níveis, marcações, volume e médias móveis.</p></article>
            <article className="landing-feature"><span className="feature-number">02</span><h3>Simulação</h3><p>Compare patrimônio, exposição, custos e risco usando dinheiro virtual.</p></article>
            <article className="landing-feature"><span className="feature-number">03</span><h3>Dados explicáveis</h3><p>Fonte, horário, completude, latência e qualidade acompanham os valores.</p></article>
            <article className="landing-feature"><span className="feature-number">04</span><h3>Workspace seguro</h3><p>Permissões separadas, credenciais protegidas e ações externas sob controles explícitos.</p></article>
          </div>
        </section>

        <section id="public-how-to-use" className="landing-section landing-split-section">
          <div className="landing-panel-copy"><div className="eyebrow">Fluxo de uso</div><h2>Um caminho simples para começar.</h2><div className="landing-step-list"><div><span>01</span><p><strong>Entrar.</strong> Abra o aplicativo com sua conta.</p></div><div><span>02</span><p><strong>Escolher.</strong> Selecione ativo, período e ferramenta.</p></div><div><span>03</span><p><strong>Explorar.</strong> Leia o gráfico e teste um cenário.</p></div><div><span>04</span><p><strong>Acompanhar.</strong> Confira resultado, risco e origem.</p></div></div></div>
          <div className="landing-info-stack"><InfoDisclosure title="O que significam as métricas?"><p><strong>CAGR</strong> é o ritmo anualizado; <strong>Sharpe</strong> relaciona retorno e oscilação; <strong>drawdown</strong> é a maior queda do patrimônio; <strong>fricção</strong> representa custos estimados.</p></InfoDisclosure><InfoDisclosure title="Como os dados são tratados?"><p>O painel identifica provedor, horário, timezone, completude, latência e qualidade. Quando não existe dado válido, a interface mostra vazio em vez de inventar preço.</p></InfoDisclosure><InfoDisclosure title="O que não fica ativo automaticamente?"><p>Uma simulação não é recomendação. Ações externas, live trading e acesso a dinheiro real dependem de permissões e controles separados.</p></InfoDisclosure></div>
        </section>

        <section className="landing-access">
          <div><div className="eyebrow">Pronto para explorar?</div><h2>{viewer ? "Abra seu workspace." : "Entre no TradingLAB."}</h2><p>{viewer ? `Conectado como ${viewer.displayName}. As ferramentas disponíveis aparecem após a entrada.` : "Faça login para abrir o aplicativo e continuar com seu próprio espaço de trabalho."}</p></div>
          {viewer ? <button className="button button-primary" onClick={() => navigate("overview")}>Abrir aplicativo →</button> : <a className="button button-primary" href={signInHref}>Entrar com ChatGPT →</a>}
        </section>
      </section>
    );
  }

  function renderOverview() {
    return (
      <>
        <section className="hero-grid">
          <div>
            <div className="eyebrow">Workspace / dashboard · V1.0</div>
            <h1>Veja o que está acontecendo, em um só lugar.</h1>
            <p className="hero-copy">Escolha um ativo, leia o gráfico e abra Paper ou replay quando quiser. Os dados, limites e permissões ficam visíveis sem ocupar o centro da tela.</p>
            <div className="hero-actions">
              <button className="button button-primary" onClick={() => navigate(isOwner ? "market" : "paper")}>{isOwner ? "Abrir Market data" : "Abrir Paper workspace"} <span aria-hidden="true">→</span></button>
              <button className="button button-quiet" onClick={() => navigate("provenance")}>Ver origem dos dados</button>
            </div>
          </div>
          <div className="hero-note">
            <div className="note-icon">⌁</div>
            <div>
              <strong>Workspace pronto</strong>
              <p>{isOwner ? "Dados locais e Paper monitor disponíveis quando conectados." : "Conecte sua conta para acompanhar seu próprio Paper."}</p>
            </div>
            <span className="status-dot" aria-label="ativo" />
          </div>
        </section>

        <section className="workspace-mode-grid" aria-label="Áreas do aplicativo">
          <article className="panel workspace-mode-card workspace-online-card">
            <div className="panel-kicker">Trading workspace</div>
            <h2>{isOwner ? "Mercado e portfólio no mesmo painel" : "Sua conta e seu mercado"}</h2>
            <p className="panel-copy">
              {isOwner
                ? "Abra candles completos e rode um replay de portfólio com dinheiro simulado. A execução externa continua desligada."
                : "Acompanhe cotações, candles, conta e ordens da sua própria conta autorizada. Dados privados do proprietário não são carregados."}
            </p>
            <div className="workspace-badges"><span>{isOwner ? "ORDENS CONTROLADAS" : "CONTA PRÓPRIA"}</span><span>{isOwner ? "DADOS PRIVADOS" : "OAUTH"}</span>{isOwner ? <span>{alpacaConnection === "connected" ? "ALPACA PAPER · LEITURA" : "ALPACA PAPER PENDENTE"}</span> : viewer ? <span>ALPACA PAPER · OAUTH</span> : null}</div>
            <div className="workspace-actions">
              {isOwner ? <><button className="button button-outline" onClick={() => navigate("paper")}>Abrir Paper monitor</button><button className="button button-outline" onClick={() => navigate("market")}>Abrir Market data</button><button className="button button-outline" onClick={() => navigate("portfolio")}>Abrir Portfolio</button><a className="button button-primary" href="/alpaca/connect">Configurar OAuth</a></> : viewer ? <><button className="button button-outline" onClick={() => navigate("paper")}>Abrir Paper workspace</button><a className="button button-primary" href="/alpaca/connect">Conectar minha Alpaca</a></> : <span className="small-muted">Faça login para conectar sua conta.</span>}
            </div>
          </article>
          {isOwner ? <article className="panel workspace-mode-card workspace-research-card"><div className="panel-kicker">Research tools</div><h2>Teste cenários com dados identificados</h2><p className="panel-copy">Importe resultados reais ou use a API local para Development e Validation OOS. O holdout continua protegido.</p><div className="workspace-actions"><button className="button button-primary" onClick={() => navigate("experiments")}>Abrir Experiments <span aria-hidden="true">→</span></button></div></article> : <article className="panel workspace-mode-card workspace-research-card"><div className="panel-kicker">Account tools</div><h2>Origem e preferências no seu controle</h2><p className="panel-copy">Confira a origem dos dados e ajuste a densidade, ajuda contextual e marcações do gráfico neste dispositivo.</p><div className="workspace-actions"><button className="button button-outline" onClick={() => navigate("provenance")}>Data & trust</button><button className="button button-primary" onClick={() => navigate("settings")}>Settings</button></div></article>}
        </section>

        {renderMarketPreview()}

        <section className="metric-grid" aria-label="Resumo filtrado">
          <MetricCard
            label="CAGR mediano"
            value={filteredRows.length ? formatPercent(metrics.cagr) : "—"}
            detail={filteredRows.length ? `${filteredRows.length.toLocaleString("en-US")} linhas no recorte` : "importe um resultado local"}
            tone="blue"
          />
          <MetricCard
            label="Sharpe mediano"
            value={filteredRows.length ? formatNumber(metrics.sharpe) : "—"}
            detail="risk-free 0 · 252 sessões"
            tone="green"
          />
          <MetricCard
            label="Max drawdown"
            value={filteredRows.length ? formatPercent(metrics.drawdown) : "—"}
            detail="mediana do recorte atual"
            tone="orange"
          />
          <MetricCard
            label="Trades observados"
            value={filteredRows.length ? metrics.trades.toLocaleString("en-US") : "—"}
            detail="contagem agregada, não performance"
            tone="violet"
          />
        </section>

        <section className="content-grid">
          <article className="panel panel-chart">
            <div className="panel-heading">
              <div>
                <div className="panel-kicker">Comparação de famílias</div>
                <h2>CAGR mediano por estratégia</h2>
              </div>
              <span className="source-pill">{dataLabel}</span>
            </div>
            {filteredRows.length ? <div className="bar-chart" role="img" aria-label="CAGR mediano por estratégia">
              {chartRows.map((item) => {
                const width = Math.min(100, Math.max(4, item.value * 1000));
                return (
                  <div className="bar-row" key={item.strategy}>
                    <div className="bar-label">{labelForStrategy(item.strategy)}</div>
                    <div className="bar-track">
                      <div className={`bar-fill bar-${item.strategy}`} style={{ width: `${width}%` }} />
                    </div>
                    <div className="bar-value">{formatPercent(item.value)}</div>
                  </div>
                );
              })}
            </div> : <EmptyState message="Carregue all_trials.csv ou um JSON exportado para visualizar valores reais." />}
            <div className="chart-footnote">
              Visualização de resumo. A mediana evita que uma única configuração seja
              tratada como conclusão da família.
            </div>
          </article>

          <article className="panel panel-integrity">
            <div className="panel-kicker">Control checks</div>
            <h2>O que permanece sob controle</h2>
            <div className="integrity-list">
              <div><span className="check">✓</span><span>Close confirmado → próximo open</span></div>
              <div><span className="check">✓</span><span>RAW, actions e normalized separados</span></div>
              <div><span className="check">✓</span><span>Holdout não executável pelo painel</span></div>
              <div><span className="check">✓</span><span>Sem broker, credenciais ou ordens</span></div>
            </div>
            <button className="text-link" onClick={() => navigate("provenance")}>
              Ver origem e limites <span aria-hidden="true">↗</span>
            </button>
          </article>
        </section>

        <section className="panel panel-table">
          <div className="panel-heading">
            <div>
              <div className="panel-kicker">Evidence matrix</div>
              <h2>Linhas do recorte atual</h2>
            </div>
            <span className="small-muted">{filteredRows.length} resultados</span>
          </div>
          {filteredRows.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Estratégia</th><th>Ativo</th><th>Período</th><th>CAGR</th><th>Sharpe</th><th>Drawdown</th><th>Trades</th></tr>
                </thead>
                <tbody>
                  {filteredRows.slice(0, 12).map((row, index) => (
                    <tr key={`${row.strategy}-${row.asset}-${row.split}-${index}`}>
                      <td><strong>{labelForStrategy(row.strategy)}</strong></td>
                      <td><span className="asset-badge">{row.asset}</span></td>
                      <td>{row.split}</td>
                      <td className={row.cagr >= 0 ? "positive" : "negative"}>{formatSignedPercent(row.cagr)}</td>
                      <td>{formatNumber(row.sharpe)}</td>
                      <td className="negative">{formatPercent(row.drawdown)}</td>
                      <td>{row.trades}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <EmptyState message="Nenhuma linha corresponde aos filtros atuais." />}
        </section>
      </>
    );
  }

  function renderExperiments() {
    return (
      <section className="page-stack">
        <div className="page-heading">
          <div><div className="eyebrow">Experiments</div><h1>Selecione, visualize e reproduza.</h1></div>
          <span className={`api-badge ${localApiAvailable ? "api-online" : "api-offline"}`}>
            <span /> {localApiAvailable ? "API local conectada" : "Modo visualização"}
          </span>
        </div>
        <div className="experiment-grid">
          <article className="panel control-panel">
            <div className="panel-kicker">Research controls</div>
            <h2>Recorte do experimento</h2>
            <p className="panel-copy">Os filtros alteram apenas a visualização. O dataset escolhido continua sendo identificado pelo seu manifesto.</p>
            <div className="field-grid">
              <label htmlFor="experiment-strategy">Estratégia<select id="experiment-strategy" value={strategy} onChange={(event) => setStrategy(event.target.value)}><option value="ALL">Todas as estratégias</option>{STRATEGIES.map((item) => <option key={item} value={item}>{labelForStrategy(item)}</option>)}</select></label>
              <label htmlFor="experiment-asset">Ativo<select id="experiment-asset" value={asset} onChange={(event) => setAsset(event.target.value)}><option value="ALL">Todos os ativos</option>{ASSETS.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
              <label htmlFor="experiment-split">Período<select id="experiment-split" value={split} onChange={(event) => setSplit(event.target.value)}><option value="ALL">Todos os períodos</option>{SPLITS.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
            </div>
            <div className="control-actions">
              <button className="button button-primary" onClick={() => void runLocalBattery()} disabled={isRunning}>
                {isRunning ? "Executando…" : "Executar bateria local"}
              </button>
              <button className="button button-outline" onClick={() => fileInput.current?.click()}>Carregar CSV/JSON</button>
              <input ref={fileInput} className="visually-hidden" type="file" accept=".csv,.json,text/csv,application/json" onChange={(event) => void handleFile(event)} />
            </div>
            <div className="execution-note">
              <strong>{localApiAvailable ? "Execução disponível" : "Execução segura e local"}</strong>
              <span>{localApiAvailable ? `Dataset detectado: ${localDatasetId || "nenhum"}` : "O site hospedado nunca executa shell. Inicie a API local para habilitar a bateria sem holdout."}</span>
            </div>
          </article>
          <article className="panel command-panel">
            <div className="panel-kicker">Reproducibility command</div>
            <h2>Comando preparado</h2>
            <p className="panel-copy">Quando a API local não estiver conectada, esta é a ponte explícita entre a interface e o motor Python.</p>
            <pre><code>{command}</code></pre>
            <button className="button button-outline full-width" onClick={() => void copyCommand()}>Copiar comando</button>
            <div className="command-warning"><span>i</span><span>O Project Holdout é deliberadamente bloqueado nesta interface. Uma mudança após observá-lo exige nova versão.</span></div>
          </article>
        </div>
        {notice ? <div className="notice" role="status">{notice}</div> : null}
      </section>
    );
  }

  function renderMarket() {
    const market = candlePayload;
    const calculated = market?.calculated;
    const latest = calculated?.latest;
    return (
      <section className="page-stack">
        <div className="page-heading">
          <div><div className="eyebrow">Market data / local snapshot</div><h1>Candles completos, com origem visível.</h1></div>
          <span className={`api-badge ${localApiAvailable ? "api-online" : "api-offline"}`}><span /> {localApiAvailable ? "Snapshot local disponível" : "API local offline"}</span>
        </div>
          <div className="market-controls panel">
            <div className="panel-kicker">Data controls</div>
            <h2>Escolha o ativo e o recorte</h2>
          <p className="panel-copy">Escolha entre o snapshot privado, um arquivo externo/licenciado configurado localmente ou um arquivo que ficará somente neste navegador. Não há preço gerado nem conexão com broker.</p>
          <div className="field-grid market-field-grid">
            <label htmlFor="candle-source">Fonte<select id="candle-source" value={candleSource} onChange={(event) => setCandleSource(event.target.value as "snapshot" | "external_file" | "browser_file")}><option value="snapshot" disabled={!localDatasetId}>Snapshot privado Yahoo</option><option value="external_file" disabled={!externalFileAvailable}>Arquivo externo configurado</option><option value="browser_file" disabled={!candlePayload || candleSource !== "browser_file"}>Arquivo deste navegador</option></select></label>
            <label htmlFor="candle-symbol">Ativo<select id="candle-symbol" value={candleSymbol} onChange={(event) => setCandleSymbol(event.target.value)}>{ASSETS.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
            <label htmlFor="candle-limit">Candles recentes<select id="candle-limit" value={candleLimit} onChange={(event) => setCandleLimit(event.target.value)}><option value="120">120</option><option value="240">240</option><option value="500">500</option><option value="1000">1000</option></select></label>
            <div className="market-action"><div className="market-action-buttons"><button className="button button-primary" onClick={() => void loadCandles()} disabled={isLoadingCandles || candleSource === "browser_file"}>{isLoadingCandles ? "Validando…" : "Carregar candles"}</button><button className="button button-outline" onClick={() => candleFileInput.current?.click()}>Importar CSV</button><input ref={candleFileInput} className="visually-hidden" type="file" accept=".csv,text/csv" onChange={(event) => void handleCandleFile(event)} /></div><span>{candleSource === "external_file" ? "arquivo externo configurado" : localDatasetId || "nenhum dataset detectado"}</span></div>
          </div>
          {candleNotice ? <div className="notice" role="status">{candleNotice}</div> : null}
        </div>

        {market ? (
          <>
            <div className="source-strip">
              <span className="source-pill">{market.source.provider} {market.source.provider_version}</span>
              <span>{market.source.retrieved_at ? `coletado em ${new Date(market.source.retrieved_at).toLocaleString("pt-BR")}` : `processado em ${market.source.ingested_at ? new Date(market.source.ingested_at).toLocaleString("pt-BR") : "horário desconhecido"}`}</span>
              <span>última sessão {market.freshness.last_session}</span>
              <span className="quality-pill">qualidade: {market.quality.status}</span>
              <span className="historical-pill">{market.freshness.realtime_active ? "realtime ativo" : "histórico · não realtime"}</span>
              <span className="source-pill">idade: {market.freshness.data_age_seconds == null ? "desconhecida" : `${Math.round(market.freshness.data_age_seconds / 86400)} dias`}</span>
              <span className="source-pill">latência: {market.freshness.latency_ms == null ? "não medida" : `${market.freshness.latency_ms.toFixed(1)} ms`}</span>
            </div>
            <section className="metric-grid market-metric-grid" aria-label="Métricas calculadas do candle">
              <MetricCard label="Último close" value={formatPrice(latest?.close)} detail={`${market.symbol} · basis normalizado`} tone="blue" />
              <MetricCard label="Variação da sessão" value={formatOptionalPercent(calculated?.change_pct ?? null)} detail={`Δ ${formatPrice(calculated?.change ?? null)}`} tone={(calculated?.change_pct ?? 0) >= 0 ? "green" : "orange"} />
              <MetricCard label="ATR 14" value={formatPrice(calculated?.atr_14)} detail="amplitude média recente" tone="violet" />
              <MetricCard label="Volume relativo" value={calculated?.volume_vs_20_session_median == null ? "—" : `${formatNumber(calculated.volume_vs_20_session_median)}x`} detail="contra mediana de 20 sessões" tone="orange" />
            </section>
            <div className="market-grid">
              <article className="panel candle-panel">
                <div className="panel-heading"><div><div className="panel-kicker">OHLCV / {market.timeframe}</div><h2>{market.symbol} — candle chart</h2></div><span className="source-pill">{market.returned_row_count} de {market.available_row_count} barras</span></div>
                <div className="chart-legend"><span><i className="legend-up" /> alta</span><span><i className="legend-down" /> baixa</span><span><i className="legend-sma20" /> SMA20</span><span><i className="legend-sma50" /> SMA50</span><span><i className="legend-sma200" /> SMA200</span><span>corpo + sombra + volume</span></div>
                <CandleChart candles={market.candles} symbol={market.symbol} persistDrawings={persistDrawings} />
                <div className="chart-footnote">Os horários do gráfico são eventos em UTC convertidos a partir da sessão regular. A barra final é marcada como encerrada pelo manifesto histórico.</div>
              </article>
              <article className="panel source-panel">
                <div className="panel-kicker">Source & integrity</div><h2>Como este valor chegou aqui</h2>
                <div className="source-detail-list">
                  <div><span>PROVIDER</span><strong>{market.source.provider}</strong></div>
                  <div><span>VERSION</span><strong>{market.source.provider_version}</strong></div>
                  <div><span>TIMEZONE</span><strong>{market.source.normalized_timezone}</strong></div>
                  <div><span>CALENDAR</span><strong>{market.source.exchange_calendar}</strong></div>
                  <div><span>PRICE BASIS</span><strong>{market.source.price_basis_id}</strong></div>
                  <div><span>ACTIONS</span><strong>{market.source.corporate_actions_preserved ? "preservadas" : "não informado"}</strong></div>
                  <div><span>COMPLETUDE</span><strong>{market.freshness.bar_is_complete == null ? "desconhecida" : market.freshness.bar_is_complete ? "encerradas" : "há barras abertas"}</strong></div>
                  <div><span>LATENCY SCOPE</span><strong>{market.freshness.latency_scope ?? "não disponível"}</strong></div>
                </div>
                <div className="hash-box"><span>DATASET</span><code>{market.source.dataset_id}</code><span>MANIFEST SHA-256</span><code>{market.source.manifest_hash}</code></div>
              </article>
            </div>
            <article className="panel calculated-panel">
              <div className="panel-heading"><div><div className="panel-kicker">Derived values</div><h2>Indicadores calculados no servidor local</h2></div><span className="small-muted">não são recomendações</span></div>
              <div className="calculated-grid"><div><span>SMA 20</span><strong>{formatPrice(calculated?.sma_20)}</strong></div><div><span>SMA 50</span><strong>{formatPrice(calculated?.sma_50)}</strong></div><div><span>SMA 200</span><strong>{formatPrice(calculated?.sma_200)}</strong></div><div><span>Range da sessão</span><strong>{formatOptionalPercent(calculated?.session_range_pct ?? null)}</strong></div></div>
              <div className="table-wrap candle-table-wrap"><table><thead><tr><th>Sessão</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th></tr></thead><tbody>{market.candles.slice(-12).reverse().map((candle) => <tr key={candle.event_time}><td>{candle.session}</td><td>{formatPrice(candle.open)}</td><td>{formatPrice(candle.high)}</td><td>{formatPrice(candle.low)}</td><td className={(candle.close ?? 0) >= (candle.open ?? 0) ? "positive" : "negative"}>{formatPrice(candle.close)}</td><td>{candle.volume == null ? "—" : Math.round(candle.volume).toLocaleString("en-US")}</td></tr>)}</tbody></table></div>
            </article>
          </>
        ) : <EmptyState message="Carregue um snapshot local para ver candles completos, qualidade e indicadores calculados." />}
      </section>
    );
  }

  function renderPortfolio() {
    const portfolio = portfolioPayload;
    const portfolioMetrics = portfolio?.metrics;
    return (
      <section className="page-stack">
        <div className="page-heading"><div><div className="eyebrow">V0.6 / Portfolio reference</div><h1>Um portfólio pequeno, auditável e sem otimizador.</h1></div><span className={`api-badge ${localApiAvailable ? "api-online" : "api-offline"}`}><span /> {localApiAvailable ? "Replay local disponível" : "Importe um resultado local"}</span></div>
        <div className="portfolio-grid">
          <article className="panel control-panel">
            <div className="panel-kicker">Portfolio controls</div>
            <h2>Executar uma referência real</h2>
            <p className="panel-copy">O replay usa o snapshot local validado, caixa inicial simulado de US$100.000 e apenas Development ou Validation OOS. O Project Holdout continua bloqueado.</p>
            <div className="field-grid">
              <label htmlFor="portfolio-split">Período<select id="portfolio-split" value={portfolioSplit} onChange={(event) => setPortfolioSplit(event.target.value)}><option value="development">Development</option><option value="validation_oos">Validation OOS</option></select></label>
              <label htmlFor="portfolio-method">Alocação<select id="portfolio-method" value={portfolioMethod} onChange={(event) => setPortfolioMethod(event.target.value as "equal_weight" | "inverse_vol")}><option value="equal_weight">Equal weight</option><option value="inverse_vol">Inverse volatility</option></select></label>
              <label htmlFor="portfolio-friction">Fricção por lado<select id="portfolio-friction" value={portfolioFriction} onChange={(event) => setPortfolioFriction(event.target.value)}><option value="0">0 bps</option><option value="5">5 bps</option><option value="10">10 bps</option><option value="25">25 bps</option></select></label>
            </div>
            <div className="control-actions">
              <button className="button button-primary" onClick={() => void runLocalPortfolio()} disabled={isRunningPortfolio}>{isRunningPortfolio ? "Executando…" : "Executar replay local"}</button>
              <button className="button button-outline" onClick={() => portfolioFileInput.current?.click()}>Carregar JSON V0.6</button>
              <input ref={portfolioFileInput} className="visually-hidden" type="file" accept=".json,application/json" onChange={(event) => void handlePortfolioFile(event)} />
            </div>
            <div className="execution-note"><strong>{localDatasetId ? "Snapshot detectado" : "Sem snapshot conectado"}</strong><span>{localDatasetId || "Inicie a API local ou importe um JSON produzido pelo comando run-portfolio."}</span></div>
          </article>
          <article className="panel portfolio-side">
            <div className="panel-kicker">Contract / fixed parameters</div><h2>O que fica congelado</h2>
            <div className="method-card active"><span>01</span><div><strong>SMA 200</strong><small>Decisão no fechamento confirmado</small></div><b>FIXO</b></div>
            <div className="method-card"><span>02</span><div><strong>Rebalance 21 sessões</strong><small>Execução na abertura seguinte</small></div><b>FIXO</b></div>
            <div className="method-card"><span>03</span><div><strong>Long-only / caixa compartilhado</strong><small>Shares inteiras, sem leverage</small></div><b>FIXO</b></div>
            <div className="method-card muted"><span>04</span><div><strong>Otimização automática</strong><small>Fora do escopo e bloqueada</small></div><b>OFF</b></div>
          </article>
        </div>
        {portfolioNotice ? <div className="notice" role="status">{portfolioNotice}</div> : null}
        {portfolio ? (
          <>
            <div className="source-strip"><span className="source-pill">{portfolio.dataset.provider} {portfolio.dataset.provider_version}</span><span>{portfolio.configuration.split_label} · {portfolio.configuration.allocation_method}</span><span>efetivo {portfolio.configuration.effective_start} → {portfolio.configuration.effective_end}</span><span className="quality-pill">manifesto validado</span><span className="historical-pill">sem holdout · sem execução externa</span></div>
            <section className="metric-grid market-metric-grid" aria-label="Métricas do portfólio V0.6">
              <MetricCard label="Patrimônio final" value={`$${formatPrice(portfolioMetrics?.final_equity)}`} detail={`inicial $${formatPrice(portfolio.configuration.initial_cash)}`} tone="blue" />
              <MetricCard label="CAGR" value={formatPercent(portfolioMetrics?.CAGR ?? 0)} detail={`${portfolioMetrics?.number_of_rebalances ?? 0} rebalanceamentos`} tone="green" />
              <MetricCard label="Sharpe" value={formatOptionalPercent(portfolioMetrics?.Sharpe ?? null, 2)} detail="retorno ajustado ao risco" tone="violet" />
              <MetricCard label="Max drawdown" value={formatSignedPercent(portfolioMetrics?.max_drawdown ?? 0)} detail={`${formatPercent(portfolioMetrics?.exposure ?? 0)} do tempo exposto`} tone="orange" />
              <MetricCard label="Custos modelados" value={`$${formatPrice(portfolioMetrics?.modeled_costs)}`} detail={`${portfolioMetrics?.number_of_fills ?? 0} fills simulados`} tone="violet" />
            </section>
            <div className="market-grid">
              <article className="panel candle-panel"><div className="panel-heading"><div><div className="panel-kicker">Equity curve / net</div><h2>Curva de patrimônio</h2></div><span className="source-pill">{portfolio.equity.length} sessões</span></div><PortfolioChart equity={portfolio.equity} /><div className="chart-footnote">A curva é marcada a mercado no fechamento. Não existe liquidação sintética no último dia.</div></article>
              <article className="panel source-panel"><div className="panel-kicker">Result & provenance</div><h2>Configuração executada</h2><div className="source-detail-list"><div><span>DATASET</span><strong>{portfolio.dataset.dataset_id}</strong></div><div><span>MANIFEST</span><strong>{portfolio.dataset.manifest_hash}</strong></div><div><span>PRICE BASIS</span><strong>{portfolio.dataset.price_basis_id}</strong></div><div><span>FRACTION</span><strong>{portfolio.configuration.friction_bps} bps / lado</strong></div><div><span>VOLATILITY</span><strong>{portfolioMetrics?.annualized_volatility == null ? "—" : formatPercent(portfolioMetrics.annualized_volatility)}</strong></div><div><span>WORKTREE</span><strong>{portfolio.provenance.dirty_worktree ? "alterado" : "limpo"}</strong></div></div><div className="portfolio-callout"><strong>Limite:</strong> este resultado é uma referência de pesquisa com dinheiro simulado. Não é recomendação, paper fill ou ordem.</div></article>
            </div>
            <div className="portfolio-grid">
              <article className="panel portfolio-main"><div className="panel-heading"><div><div className="panel-kicker">Final positions</div><h2>Posições no último fechamento</h2></div><span className="source-pill">caixa ${formatPrice(portfolio.equity.at(-1)?.cash)}</span></div><div className="allocation-list">{portfolio.final_positions.length ? portfolio.final_positions.map((position, index) => <div className="allocation-row" key={position.symbol}><div className="allocation-symbol"><span className={`allocation-color allocation-${index % ASSETS.length}`} />{position.symbol}</div><div className="allocation-bar"><span style={{ width: `${Math.min(100, (position.weight ?? 0) * 100)}%` }} /></div><strong>{formatPercent(position.weight ?? 0)}</strong></div>) : <EmptyState message="O portfólio terminou em caixa neste período." />}</div></article>
              <article className="panel portfolio-side"><div className="panel-kicker">Last fills</div><h2>Últimas movimentações</h2><div className="fill-list">{portfolio.fills.slice(-8).reverse().map((fill) => <div className="fill-row" key={`${fill.session}-${fill.symbol}-${fill.side}-${fill.quantity}`}><span className={fill.side === "buy" ? "positive" : "negative"}>{fill.side === "buy" ? "BUY" : "SELL"}</span><strong>{fill.symbol}</strong><small>{fill.session} · {fill.quantity} @ {formatPrice(fill.price)}</small></div>)}{!portfolio.fills.length ? <EmptyState message="Nenhum fill simulado no recorte." /> : null}</div></article>
            </div>
          </>
        ) : <EmptyState message="Execute o replay local ou carregue o JSON V0.6 para visualizar patrimônio, posições e fills reais." />}
        <div className="panel roadmap-panel"><div className="panel-kicker">Product map</div><h2>Até onde o produto está preparado</h2><div className="roadmap-line">{["V0.1 Local lab", "V0.2 LEAN", "V0.3 Paper bridge", "V0.4 TradingView", "V0.5 Forex", "V0.6 Portfolio"].map((item) => <div className="roadmap-step done" key={item}><span>✓</span><strong>{item}</strong></div>)}</div></div>
      </section>
    );
  }

  function renderProvenance() {
    return (
      <section className="page-stack">
        <div className="page-heading"><div><div className="eyebrow">Admin / provenance</div><h1>Controle técnico e evidência do produto.</h1></div><span className="source-pill">owner only</span></div>
        <div className="provenance-grid">
          <article className="panel provenance-main"><div className="panel-kicker">Data contract</div><h2>O que esta interface aceita</h2><div className="contract-list"><div><span className="contract-key">RAW</span><p>Dados do provedor preservados separadamente; não são embutidos no site público.</p></div><div><span className="contract-key">ACTIONS</span><p>Ações corporativas permanecem auditáveis e não são recarregadas como um detalhe invisível.</p></div><div><span className="contract-key">NORMALIZED</span><p>O painel aceita <code>all_trials.csv</code> ou JSON exportado e calcula o resumo no navegador.</p></div><div><span className="contract-key">HASH</span><p>Dataset, manifesto, commit e lockfile continuam sendo a autoridade; o painel é uma camada de leitura.</p></div></div></article>
          <article className="panel safety-panel"><div className="safety-mark">0</div><div className="panel-kicker">Safety boundary</div><h2>Paper privado, live bloqueado</h2><p>A camada direta usa somente a conta Paper do proprietário, com credenciais server-side, allowlist, limites pequenos, reconciliação e kill switch. Live trading continua inexistente.</p><div className="safety-tags"><span>PAPER OWNER ONLY</span><span>LIVE OFF</span><span>KILL SWITCH</span></div></article>
        </div>
        <article className="panel provenance-table"><div className="panel-heading"><div><div className="panel-kicker">Evidence status</div><h2>Mapa de entregas</h2></div></div><div className="status-table"><div><strong>V0.1</strong><span className="status-complete">COMPLETA</span><p>Backtest causal, registry append-only, holdout controlado.</p></div><div><strong>V0.2</strong><span className="status-complete">REPRODUZIDA</span><p>60/60 configurações primárias no gate independente.</p></div><div><strong>V0.3</strong><span className="status-current">PAPER LOCAL</span><p>Conta, IEX, WebSocket, posições, ordens e cancelamento sob kill switch.</p></div><div><strong>V0.4–V0.6</strong><span className="status-bridge">EM EVOLUÇÃO</span><p>TradingView, Forex e portfólio continuam separados do executor Paper.</p></div><div><strong>V1.0</strong><span className="status-current">PRIVADA</span><p>Interface owner, dados reais server-side, mobile e proveniência.</p></div></div></article>
        <div className="admin-tools-grid">
          <article className="panel command-panel"><div className="panel-kicker">Use tips / reprodução</div><h2>Comando preparado para repetir um trial</h2><p className="panel-copy">O comando é uma ponte para o motor local. Ele não roda no site e não libera o Project Holdout.</p><pre><code>{command}</code></pre><button className="button button-outline full-width" onClick={() => void copyCommand()}>Copiar comando</button></article>
          <article className="panel admin-contract-panel"><div className="panel-kicker">Fixed parameters</div><h2>Contratos que não devem ser alterados aqui</h2><div className="admin-contract-list"><div><strong>DECISÃO</strong><span>close confirmado → próximo open válido</span></div><div><strong>BASE</strong><span>RAW, ações e normalized separados</span></div><div><strong>RISCO</strong><span>long-only, shares inteiras, sem leverage</span></div><div><strong>GATE</strong><span>holdout protegido e live ausente</span></div></div><InfoDisclosure title="Abrir mapa técnico"><p>O código canônico permanece no repositório local. Esta página reúne o mapa para revisão humana, não substitui os manifestos ou os artefatos imutáveis.</p></InfoDisclosure></article>
        </div>
      </section>
    );
  }

  function renderData() {
    return (
      <section className="page-stack">
        <div className="page-heading"><div><div className="eyebrow">Data & trust</div><h1>Veja de onde vem cada número.</h1></div><span className="source-pill">transparência</span></div>
        <div className="trust-overview-grid">
          <article className="panel trust-card"><span className="trust-card-icon">◎</span><div><h2>Fonte identificada</h2><p>Provedor, versão, horário de coleta e base de preço aparecem quando existem.</p></div><HelpDot label="Sobre a fonte dos dados">A fonte é o serviço ou arquivo que forneceu os candles. Sem essa informação, o valor não é plenamente rastreável.</HelpDot></article>
          <article className="panel trust-card"><span className="trust-card-icon">✓</span><div><h2>Qualidade visível</h2><p>Completude, duplicidade, ordem das barras, ausências e manifesto ficam junto do resultado.</p></div><HelpDot label="Sobre a qualidade">Qualidade indica se o conjunto passou pelas verificações básicas antes de ser exibido.</HelpDot></article>
          <article className="panel trust-card"><span className="trust-card-icon">◌</span><div><h2>Histórico ou realtime</h2><p>Snapshot, arquivo local e cotação realtime são estados diferentes. Latência desconhecida permanece desconhecida.</p></div><HelpDot label="Sobre realtime">Realtime significa que uma cotação está chegando agora. Um snapshot histórico não é transmissão ao vivo.</HelpDot></article>
        </div>
        <article className="panel data-contract-card">
          <div className="panel-heading"><div><div className="panel-kicker">Como confiar no painel</div><h2>Transparência sem sobrecarregar a tela</h2></div><span className="api-badge api-offline"><span /> não é recomendação</span></div>
          <div className="data-contract-grid"><div><strong>RAW</strong><span>preservado na origem quando disponível</span></div><div><strong>NORMALIZED</strong><span>base utilizada para cálculos e gráficos</span></div><div><strong>TIME</strong><span>sessão, timezone e horário do evento</span></div><div><strong>STATUS</strong><span>completo, em formação ou desconhecido</span></div></div>
          <InfoDisclosure title="Ver a explicação completa"><p>O workspace mostra os metadados necessários para uma decisão informada. O proprietário encontra hashes, manifestos, contratos, comandos de reprodução e mapa do produto em <button className="inline-button" type="button" onClick={() => navigate("admin")}>Admin</button>.</p></InfoDisclosure>
        </article>
      </section>
    );
  }

  function renderProfile() {
    const initials = viewer?.displayName.split(" ").map((part) => part[0]).slice(0, 2).join("").toUpperCase() ?? "TL";
    return (
      <section className="page-stack account-page">
        <div className="page-heading"><div><div className="eyebrow">Account / profile</div><h1>Seu perfil e seu nível de acesso.</h1></div><span className="source-pill">sessão atual</span></div>
        <div className="profile-grid">
          <article className="panel profile-card"><div className="profile-avatar">{initials}</div><div><h2>{isOwner ? "Proprietário local" : viewer?.displayName ?? "Visitante"}</h2><p>{isOwner ? "Sessão local do proprietário" : viewer?.email ?? "Faça login para personalizar seu workspace."}</p></div><span className="role-pill">{isOwner ? "PROPRIETÁRIO" : viewer ? "USUÁRIO CONECTADO" : "PÚBLICO"}</span></article>
          <article className="panel access-card"><div className="panel-kicker">Access scope</div><h2>O que aparece para você</h2><div className="access-list"><div><span>Workspace online</span><strong>disponível</strong></div><div><span>Conta Alpaca própria</span><strong>{viewer ? "via OAuth" : "após login"}</strong></div><div><span>Pesquisa local privada</span><strong>{isOwner ? "proprietário" : "restrita"}</strong></div><div><span>Live trading</span><strong className="negative">bloqueado</strong></div></div></article>
        </div>
        <article className="panel profile-session"><div><div className="panel-kicker">Session</div><h2>Conta reconhecida pelo ChatGPT</h2><p className="panel-copy">As permissões são definidas no servidor. Credenciais da Alpaca não são exibidas nesta página.</p></div>{viewer ? <a className="button button-outline" href={signOutHref}>Sair</a> : <a className="button button-primary" href={signInHref}>Entrar</a>}</article>
      </section>
    );
  }

  function renderSettings() {
    return (
      <section className="page-stack settings-page">
        <div className="page-heading"><div><div className="eyebrow">Workspace / settings</div><h1>Ajuste a interface ao seu jeito de trabalhar.</h1></div><span className="source-pill">salvo neste dispositivo</span></div>
        <div className="settings-grid">
          <article className="panel settings-panel"><div className="panel-kicker">Visualização</div><h2>Preferências do workspace</h2><div className="settings-list"><label className="setting-row" htmlFor="setting-tooltips"><span><strong>Ajuda contextual</strong><small>Mostra o pequeno ? junto dos campos e controles.</small></span><input id="setting-tooltips" aria-label="Ajuda contextual" type="checkbox" checked={tooltipsEnabled} onChange={(event) => setTooltipsEnabled(event.target.checked)} /></label><label className="setting-row" htmlFor="setting-compact"><span><strong>Modo compacto</strong><small>Reduz espaços para caber mais informação na tela.</small></span><input id="setting-compact" aria-label="Modo compacto" type="checkbox" checked={compactMode} onChange={(event) => setCompactMode(event.target.checked)} /></label><label className="setting-row" htmlFor="setting-drawings"><span><strong>Preservar marcações do gráfico</strong><small>Salva linhas e níveis neste dispositivo, por ativo.</small></span><input id="setting-drawings" aria-label="Preservar marcações do gráfico" type="checkbox" checked={persistDrawings} onChange={(event) => setPersistDrawings(event.target.checked)} /></label></div></article>
          <article className="panel settings-panel"><div className="panel-kicker">Safety defaults</div><h2>Limites que não mudam aqui</h2><div className="settings-list readonly-settings"><div className="setting-row"><span><strong>Live trading</strong><small>Não existe caminho ativo para dinheiro real.</small></span><b>OFF</b></div><div className="setting-row"><span><strong>Holdout</strong><small>Não é executado pela interface.</small></span><b>PROTEGIDO</b></div><div className="setting-row"><span><strong>Credenciais</strong><small>Ficam no servidor ou na autorização oficial.</small></span><b>SERVER-SIDE</b></div></div></article>
        </div>
        <article className="panel settings-note"><HelpDot label="Por que estas configurações são locais?">Preferências visuais não devem alterar dados, cálculos ou regras de execução. Elas ficam apenas neste navegador.</HelpDot><span>As preferências alteram aparência e interação; não alteram resultados, estratégias ou permissões.</span></article>
      </section>
    );
  }

  function renderHelp() {
    return (
      <section className="page-stack help-page">
        <div className="page-heading"><div><div className="eyebrow">Help / guide</div><h1>Orientação rápida, quando você precisar.</h1></div><span className="source-pill">sem excesso de texto</span></div>
        <div className="help-grid">
          <article className="panel help-intro"><div className="help-mark">?</div><div><h2>Como navegar</h2><p>Use a barra lateral para trocar de área. No gráfico, passe o mouse sobre uma barra, use a roda para zoom e escolha uma ferramenta para mover ou marcar.</p></div></article>
          <article className="panel help-contact"><div className="panel-kicker">Contact</div><h2>Fale com o proprietário</h2><p>Para dúvidas sobre acesso, dados ou integração, envie uma mensagem pelo canal de contato.</p><a className="button button-outline" href="mailto:igorbolognani@hotmail.com">Enviar mensagem</a></article>
        </div>
        <div className="help-topics"><InfoDisclosure title="Dashboard"><p>O Dashboard reúne o gráfico principal, o resumo filtrado e os atalhos para Paper, Market data e Portfolio quando sua conta possui essa permissão.</p></InfoDisclosure><InfoDisclosure title="Gráfico"><p>Cursor inspeciona uma barra; Mover navega; Nível e Linha desenham; Marcar registra um ponto. SMA e volume podem ser ligados ou desligados.</p></InfoDisclosure><InfoDisclosure title="Paper workspace"><p>Mostra conta, poder de compra, cotações, candles, posições e ordens da conta autorizada. O status de segurança informa quando uma ação está bloqueada.</p></InfoDisclosure><InfoDisclosure title="Dados e confiança"><p>A página Data & trust resume origem e qualidade. O proprietário também pode abrir Admin para contratos, hashes e comandos de reprodução.</p></InfoDisclosure></div>
      </section>
    );
  }

  const ownerOnlyViews: ViewId[] = ["market", "portfolio", "experiments", "admin"];
  const visibleActiveView: ViewId = !isOwner && ownerOnlyViews.includes(activeView)
    ? "overview"
    : !viewer && activeView === "paper"
      ? "overview"
      : activeView;
  function openCandleImporter() {
    if (candleFileInput.current) {
      candleFileInput.current.click();
      return;
    }
    navigate("overview");
    window.setTimeout(() => candleFileInput.current?.click(), 0);
  }

  if (visibleActiveView === "landing") {
    return (
      <main className="public-shell">
        <header className="public-header">
          <div className="public-brand"><Image className="public-logo" src="/tradinglab-logo.svg" width={500} height={112} alt="TradingLAB — Trading tools · decisão com controle" priority /></div>
          <nav className="public-tool-nav" aria-label="Atalhos da apresentação"><a href="#market-preview">Mercado</a><a href="#public-features">Ferramentas</a><a href="#public-how-to-use">Como usar</a></nav>
          <div className="public-header-actions">
            {viewer ? <button className="auth-link auth-link-primary" onClick={() => navigate("overview")}>Abrir aplicativo</button> : <a className="auth-link auth-link-primary" href={signInHref}>Entrar com ChatGPT</a>}
          </div>
        </header>
        <div className="public-content">{renderLanding()}</div>
        <footer className="public-footer"><span>TradingLAB · clareza antes da execução</span><span>Sem ordens externas · sem capital real</span></footer>
      </main>
    );
  }

  const onlineNavigation: Array<[ViewId, string, string]> = [
    ["overview", "Home / dashboard", "◈"],
    ...(viewer ? [["paper", isOwner ? "Paper monitor" : "Paper workspace", "◉"]] as Array<[ViewId, string, string]> : []),
    ...(isOwner ? [["market", "Market data", "▥"], ["portfolio", "Portfolio replay", "◒"]] as Array<[ViewId, string, string]> : []),
  ];
  const researchNavigation: Array<[ViewId, string, string]> = [
    ...(isOwner ? [["experiments", "Experiments", "⌘"]] as Array<[ViewId, string, string]> : []),
    ["provenance", "Data & trust", "⌬"],
  ];
  const manageNavigation: Array<[ViewId, string, string]> = [
    ["profile", "Profile", "◉"],
    ["settings", "Settings", "⚙"],
    ["help", "Help & contact", "?"],
    ...(isOwner ? [["admin", "Admin / use tips", "⌘"]] as Array<[ViewId, string, string]> : []),
  ];
  const viewContent = visibleActiveView === "overview"
    ? renderOverview()
    : visibleActiveView === "paper"
      ? <PaperControl userMode={!isOwner} />
      : visibleActiveView === "market"
        ? renderMarket()
        : visibleActiveView === "experiments"
          ? renderExperiments()
          : visibleActiveView === "portfolio"
            ? renderPortfolio()
            : visibleActiveView === "provenance"
              ? renderData()
              : visibleActiveView === "admin"
                ? renderProvenance()
                : visibleActiveView === "profile"
                  ? renderProfile()
                  : visibleActiveView === "settings"
                    ? renderSettings()
                    : renderHelp();
  const viewLabels: Record<ViewId, string> = {
    landing: "Landing",
    overview: "Home / dashboard",
    paper: isOwner ? "Paper monitor" : "Paper workspace",
    market: "Market data",
    experiments: "Experiments",
    portfolio: "Portfolio replay",
    provenance: "Data & trust",
    profile: "Profile",
    settings: "Settings",
    help: "Help & contact",
    admin: "Admin / use tips",
  };
  const showFilters = visibleActiveView === "overview" || visibleActiveView === "experiments";
  const showImport = visibleActiveView === "overview" || visibleActiveView === "market";

  return (
    <main className={`app-shell ${compactMode ? "is-compact" : ""} ${tooltipsEnabled ? "tooltips-on" : "tooltips-off"}`}>
      {sidebarOpen ? <button className="sidebar-scrim" type="button" aria-label="Fechar menu" onClick={() => setSidebarOpen(false)} /> : null}
      <aside className={`sidebar ${sidebarOpen ? "is-open" : ""}`}>
        <div className="brand"><AppMark /><div><strong>TradingLAB</strong><span>Trading workspace</span></div><button className="sidebar-close" type="button" aria-label="Fechar menu" onClick={() => setSidebarOpen(false)}>×</button></div>
        <div className="sidebar-scroll">
          <div className="sidebar-section"><div className="sidebar-label">Workspace</div><nav>{onlineNavigation.map(([id, label, icon]) => <button className={visibleActiveView === id ? "nav-item active" : "nav-item"} onClick={() => navigate(id)} key={id}><span aria-hidden="true">{icon}</span>{label}{id === "paper" ? <em>paper</em> : null}</button>)}</nav></div>
          <div className="sidebar-section sidebar-research-section"><div className="sidebar-label">Research</div><nav>{researchNavigation.map(([id, label, icon]) => <button className={visibleActiveView === id ? "nav-item active" : "nav-item"} onClick={() => navigate(id)} key={id}><span aria-hidden="true">{icon}</span>{label}{id === "experiments" ? <em>owner</em> : null}</button>)}</nav></div>
          <div className="sidebar-section sidebar-manage-section"><div className="sidebar-label">Manage</div><nav>{manageNavigation.map(([id, label, icon]) => <button className={visibleActiveView === id ? "nav-item active" : "nav-item"} onClick={() => navigate(id)} key={id}><span aria-hidden="true">{icon}</span>{label}{id === "admin" ? <em>owner</em> : null}</button>)}</nav></div>
        </div>
        <div className="sidebar-section sidebar-bottom"><div className="sidebar-label">Safety status</div><div className="safety-status"><span className="status-dot" /><div><strong>{isOwner ? "Owner workspace" : "Connected workspace"}</strong><small>{isOwner ? "online + offline tools" : "own account / public data"}</small></div></div><div className="version-box"><span>Product state</span><strong>V1.0 workspace</strong><small>live execution disabled</small></div></div>
      </aside>
      <div className="main-column">
        <header className="topbar"><div className="mobile-brand"><button className="mobile-menu-button" type="button" aria-label="Abrir menu" onClick={() => setSidebarOpen(true)}>☰</button><AppMark /><strong>TradingLAB</strong></div><div className="breadcrumb"><span>TradingLAB</span><b>/</b><strong>{viewLabels[visibleActiveView]}</strong></div><div className="topbar-right"><span className="sync-label"><span className="status-dot" /> {isOwner ? (localApiAvailable ? "Snapshot local conectado" : "Workspace privado") : "Workspace online"}</span>{viewer ? <><button className="avatar" type="button" aria-label="Abrir perfil" onClick={() => navigate("profile")}>{viewer.displayName.slice(0, 1).toUpperCase()}</button><a className="auth-link" href={signOutHref}>Sair</a></> : isOwner ? <span className="auth-link auth-link-local">Owner local</span> : <a className="auth-link auth-link-primary" href={signInHref}>Entrar</a>}</div></header>
        <div className="content"><div className="page-toolbar"><div><span className="page-toolbar-kicker">{isOwner ? "Owner workspace" : "Personal workspace"}</span><strong>{viewLabels[visibleActiveView]}</strong></div><div className="page-toolbar-actions">{showImport ? <button className="button button-outline" type="button" onClick={openCandleImporter}>Inserir candles</button> : null}{visibleActiveView === "overview" && viewer ? <button className="button button-primary" type="button" onClick={() => navigate("paper")}>Abrir Paper</button> : null}</div></div>{showFilters ? <div className="filter-strip"><div className="filter-title"><span className="filter-icon">≡</span><strong>Filtros</strong><span>{filteredRows.length} resultados</span><HelpDot label="Sobre os filtros">Os filtros alteram apenas o recorte visual dos resultados importados.</HelpDot></div><div className="filter-control"><span className="filter-control-label">Estratégia <HelpDot label="Sobre estratégia">A regra que gerou o resultado.</HelpDot></span><select aria-label="Strategy" value={strategy} onChange={(event) => setStrategy(event.target.value)}><option value="ALL">Todas</option>{STRATEGIES.map((item) => <option key={item} value={item}>{labelForStrategy(item)}</option>)}</select></div><div className="filter-control"><span className="filter-control-label">Ativo <HelpDot label="Sobre ativo">O símbolo do ETF ou ativo analisado.</HelpDot></span><select aria-label="Asset" value={asset} onChange={(event) => setAsset(event.target.value)}><option value="ALL">Todos</option>{ASSETS.map((item) => <option key={item} value={item}>{item}</option>)}</select></div><div className="filter-control"><span className="filter-control-label">Período <HelpDot label="Sobre período">A divisão temporal usada na pesquisa.</HelpDot></span><select aria-label="Split" value={split} onChange={(event) => setSplit(event.target.value)}><option value="ALL">Todos</option>{SPLITS.map((item) => <option key={item} value={item}>{item}</option>)}</select></div><button className="reset-button" onClick={resetData}>Limpar</button></div> : null}{viewContent}</div>
        <footer className="footer"><span>TradingLAB · Quant / Systematic Research Lab</span><span>Research first · evidence before execution</span></footer>
      </div>
    </main>
  );
}
