"use client";

import type { ChangeEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

type ViewId = "overview" | "market" | "experiments" | "portfolio" | "provenance";

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
};

type CandlePayload = {
  symbol: string;
  timeframe: string;
  candles: Candle[];
  returned_row_count: number;
  available_row_count: number;
  source: {
    provider: string;
    provider_version: string;
    retrieved_at: string;
    dataset_id: string;
    dataset_checksum: string;
    manifest_hash: string;
    exchange_calendar: string;
    source_timezone: string;
    normalized_timezone: string;
    price_basis_id: string;
    normalization_version: string;
    corporate_actions_preserved: boolean;
  };
  freshness: {
    mode: string;
    last_event_time: string | null;
    last_session: string;
    bar_is_complete: boolean;
    realtime_active: boolean;
    latency_ms: number | null;
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
    errors: string[];
    warnings: string[];
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

function CandleChart({ candles }: { candles: Candle[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !candles.length) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    function draw() {
      const rect = canvas.getBoundingClientRect();
      const width = Math.max(320, rect.width);
      const height = 360;
      const pixelRatio = window.devicePixelRatio || 1;
      canvas.width = width * pixelRatio;
      canvas.height = height * pixelRatio;
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
      context.clearRect(0, 0, width, height);

      const valid = candles.filter((candle) => candle.high != null && candle.low != null);
      if (!valid.length) return;
      const prices = valid.flatMap((candle) => [candle.high ?? 0, candle.low ?? 0]);
      const maximum = Math.max(...prices);
      const minimum = Math.min(...prices);
      const range = Math.max(maximum - minimum, 0.000001);
      const left = 52;
      const right = 14;
      const top = 18;
      const priceBottom = 270;
      const volumeTop = 292;
      const volumeBottom = 334;
      const chartWidth = width - left - right;
      const slot = chartWidth / Math.max(valid.length, 1);
      const bodyWidth = Math.max(2, Math.min(13, slot * 0.62));
      const y = (price: number) => top + ((maximum - price) / range) * (priceBottom - top);
      const volumes = valid.map((candle) => candle.volume ?? 0);
      const maximumVolume = Math.max(...volumes, 1);

      context.font = "10px ui-monospace, monospace";
      context.lineWidth = 1;
      for (let index = 0; index <= 4; index += 1) {
        const gridY = top + ((priceBottom - top) * index) / 4;
        const label = maximum - (range * index) / 4;
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

      valid.forEach((candle, index) => {
        const center = left + slot * index + slot / 2;
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
        const volumeHeight = ((candle.volume ?? 0) / maximumVolume) * (volumeBottom - volumeTop);
        context.globalAlpha = 0.42;
        context.fillRect(center - bodyWidth / 2, volumeBottom - volumeHeight, bodyWidth, volumeHeight);
        context.globalAlpha = 1;
      });
      function drawIndicator(key: "sma_20" | "sma_50" | "sma_200", color: string) {
        context.strokeStyle = color;
        context.lineWidth = 1.4;
        context.beginPath();
        let started = false;
        valid.forEach((candle, index) => {
          const indicator = candle[key];
          if (indicator == null) {
            started = false;
            return;
          }
          const center = left + slot * index + slot / 2;
          if (started) context.lineTo(center, y(indicator));
          else context.moveTo(center, y(indicator));
          started = true;
        });
        context.stroke();
      }
      drawIndicator("sma_20", "#3267f3");
      drawIndicator("sma_50", "#7a5cf0");
      drawIndicator("sma_200", "#e68a3e");
      context.fillStyle = "#8190a5";
      const labelIndexes = [0, Math.floor((valid.length - 1) / 2), valid.length - 1];
      labelIndexes.forEach((index) => {
        const center = left + slot * index + slot / 2;
        context.fillText(valid[index].session, Math.max(left, center - 30), height - 8);
      });
    }

    draw();
    window.addEventListener("resize", draw);
    return () => window.removeEventListener("resize", draw);
  }, [candles]);

  return <canvas ref={canvasRef} className="candle-canvas" aria-label="Candles OHLC e volume" />;
}

function AppMark() {
  return (
    <div className="app-mark" aria-hidden="true">
      <span />
      <span />
      <span />
    </div>
  );
}

export default function Home() {
  const [activeView, setActiveView] = useState<ViewId>("overview");
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
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let active = true;
    fetch("http://127.0.0.1:8787/api/health")
      .then(async (response) => {
        if (!response.ok) throw new Error("local API unavailable");
        return (await response.json()) as { dataset_ids?: string[]; recommended_dataset_id?: string | null };
      })
      .then((payload) => {
        if (!active) return;
        setLocalApiAvailable(true);
        setLocalDatasetId(payload.recommended_dataset_id ?? payload.dataset_ids?.at(-1) ?? "");
      })
      .catch(() => {
        if (active) setLocalApiAvailable(false);
      });
    return () => {
      active = false;
    };
  }, []);

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
    if (!localApiAvailable || !localDatasetId) {
      setCandleNotice("Inicie `uv run tradinglab-dashboard` para carregar o snapshot real local.");
      return;
    }
    setIsLoadingCandles(true);
    setCandleNotice("Validando manifesto, checksum e candles…");
    try {
      const query = new URLSearchParams({
        dataset_id: localDatasetId,
        symbol: candleSymbol,
        limit: candleLimit,
      });
      const response = await fetch(`http://127.0.0.1:8787/api/candles?${query.toString()}`);
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

  function renderOverview() {
    return (
      <>
        <section className="hero-grid">
          <div>
            <div className="eyebrow">Research control room / V0.6</div>
            <h1>Transforme hipóteses em evidência reproduzível.</h1>
            <p className="hero-copy">
              Um painel único para explorar os resultados do TradingLAB sem misturar
              dados, engines ou etapas de execução. Selecione um recorte, importe o
              relatório local e compare as famílias com contexto.
            </p>
            <div className="hero-actions">
              <button className="button button-primary" onClick={() => setActiveView("experiments")}>
                Abrir experimento <span aria-hidden="true">→</span>
              </button>
              <button className="button button-quiet" onClick={() => setActiveView("provenance")}>
                Ver proveniência
              </button>
            </div>
          </div>
          <div className="hero-note">
            <div className="note-icon">⌁</div>
            <div>
              <strong>Estado do laboratório</strong>
              <p>V0.1 congelada · V0.2 reproduzida · V0.6 em referência</p>
            </div>
            <span className="status-dot" aria-label="ativo" />
          </div>
        </section>

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
            <div className="panel-kicker">Integrity checks</div>
            <h2>O que está protegido</h2>
            <div className="integrity-list">
              <div><span className="check">✓</span><span>Close confirmado → próximo open</span></div>
              <div><span className="check">✓</span><span>RAW, actions e normalized separados</span></div>
              <div><span className="check">✓</span><span>Holdout não executável pelo painel</span></div>
              <div><span className="check">✓</span><span>Sem broker, credenciais ou ordens</span></div>
            </div>
            <button className="text-link" onClick={() => setActiveView("provenance")}>
              Abrir contrato de segurança <span aria-hidden="true">↗</span>
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
          <p className="panel-copy">O painel consulta somente os dados reais já congelados no seu computador. Não há preço gerado, preenchimento automático ou conexão com broker.</p>
          <div className="field-grid market-field-grid">
            <label htmlFor="candle-symbol">Ativo<select id="candle-symbol" value={candleSymbol} onChange={(event) => setCandleSymbol(event.target.value)}>{ASSETS.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
            <label htmlFor="candle-limit">Candles recentes<select id="candle-limit" value={candleLimit} onChange={(event) => setCandleLimit(event.target.value)}><option value="120">120</option><option value="240">240</option><option value="500">500</option><option value="1000">1000</option></select></label>
            <div className="market-action"><button className="button button-primary" onClick={() => void loadCandles()} disabled={isLoadingCandles}>{isLoadingCandles ? "Validando…" : "Carregar candles"}</button><span>{localDatasetId || "nenhum dataset detectado"}</span></div>
          </div>
          {candleNotice ? <div className="notice" role="status">{candleNotice}</div> : null}
        </div>

        {market ? (
          <>
            <div className="source-strip">
              <span className="source-pill">{market.source.provider} {market.source.provider_version}</span>
              <span>coletado em {new Date(market.source.retrieved_at).toLocaleString("pt-BR")}</span>
              <span>última sessão {market.freshness.last_session}</span>
              <span className="quality-pill">qualidade: {market.quality.status}</span>
              <span className="historical-pill">histórico · não realtime</span>
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
                <CandleChart candles={market.candles} />
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
    const equalWeight = 100 / ASSETS.length;
    return (
      <section className="page-stack">
        <div className="page-heading"><div><div className="eyebrow">V0.6 / Portfolio reference</div><h1>Um portfólio pequeno, auditável e sem otimizador.</h1></div><span className="coming-badge">REFERENCE READY</span></div>
        <div className="portfolio-grid">
          <article className="panel portfolio-main">
            <div className="panel-heading"><div><div className="panel-kicker">Allocation baseline</div><h2>Composição de referência</h2></div><span className="source-pill">V0.6 local</span></div>
            <div className="allocation-list">
              {ASSETS.map((item, index) => <div className="allocation-row" key={item}><div className="allocation-symbol"><span className={`allocation-color allocation-${index}`} />{item}</div><div className="allocation-bar"><span style={{ width: `${equalWeight}%` }} /></div><strong>{equalWeight.toFixed(1)}%</strong></div>)}
            </div>
            <div className="portfolio-callout"><strong>Regra declarada:</strong> equal weight entre os cinco ETFs quando todos estiverem elegíveis. Isto é uma referência de alocação, não uma posição real nem uma recomendação.</div>
          </article>
          <article className="panel portfolio-side">
            <div className="panel-kicker">Available methods</div><h2>Baselines declaradas</h2>
            <div className="method-card active"><span>01</span><div><strong>Equal weight</strong><small>Pesos iguais entre sinais long</small></div><b>BASE</b></div>
            <div className="method-card"><span>02</span><div><strong>Inverse volatility</strong><small>Menor volatilidade recebe mais peso</small></div><b>CHECK</b></div>
            <div className="method-card muted"><span>03</span><div><strong>Otimização automática</strong><small>Fora do escopo e bloqueada</small></div><b>OFF</b></div>
          </article>
        </div>
        <div className="panel roadmap-panel"><div className="panel-kicker">Product map</div><h2>Até onde o produto está preparado</h2><div className="roadmap-line">{["V0.1 Local lab", "V0.2 LEAN", "V0.3 Paper bridge", "V0.4 TradingView", "V0.5 Forex", "V0.6 Portfolio"].map((item, index) => <div className={`roadmap-step ${index < 5 ? "done" : "current"}`} key={item}><span>{index < 5 ? "✓" : "6"}</span><strong>{item}</strong></div>)}</div></div>
      </section>
    );
  }

  function renderProvenance() {
    return (
      <section className="page-stack">
        <div className="page-heading"><div><div className="eyebrow">Data & provenance</div><h1>A evidência começa no que pode ser refeito.</h1></div><span className="source-pill">local-first</span></div>
        <div className="provenance-grid">
          <article className="panel provenance-main"><div className="panel-kicker">Data contract</div><h2>O que esta interface aceita</h2><div className="contract-list"><div><span className="contract-key">RAW</span><p>Dados do provedor preservados separadamente; não são embutidos no site público.</p></div><div><span className="contract-key">ACTIONS</span><p>Ações corporativas permanecem auditáveis e não são recarregadas como um detalhe invisível.</p></div><div><span className="contract-key">NORMALIZED</span><p>O painel aceita <code>all_trials.csv</code> ou JSON exportado e calcula o resumo no navegador.</p></div><div><span className="contract-key">HASH</span><p>Dataset, manifesto, commit e lockfile continuam sendo a autoridade; o painel é uma camada de leitura.</p></div></div></article>
          <article className="panel safety-panel"><div className="safety-mark">0</div><div className="panel-kicker">Safety boundary</div><h2>Research only</h2><p>Não existe no site SDK de broker, credencial, endpoint de ordem, paper trading, live trading ou promoção automática.</p><div className="safety-tags"><span>NO BROKER</span><span>NO CAPITAL</span><span>NO AUTO-PROMOTION</span></div></article>
        </div>
        <article className="panel provenance-table"><div className="panel-heading"><div><div className="panel-kicker">Evidence status</div><h2>Mapa de entregas</h2></div></div><div className="status-table"><div><strong>V0.1</strong><span className="status-complete">COMPLETA</span><p>Backtest causal, registry append-only, holdout controlado.</p></div><div><strong>V0.2</strong><span className="status-complete">REPRODUZIDA</span><p>60/60 configurações primárias no gate independente.</p></div><div><strong>V0.3–V0.5</strong><span className="status-bridge">BRIDGES</span><p>Contratos e simuladores sem side effects externos.</p></div><div><strong>V0.6</strong><span className="status-current">UTILIZÁVEL</span><p>Referência de portfólio e painel visual sem otimizador.</p></div></div></article>
      </section>
    );
  }

  const viewContent = activeView === "overview" ? renderOverview() : activeView === "market" ? renderMarket() : activeView === "experiments" ? renderExperiments() : activeView === "portfolio" ? renderPortfolio() : renderProvenance();

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><AppMark /><div><strong>TradingLAB</strong><span>Research workspace</span></div></div>
        <div className="sidebar-section"><div className="sidebar-label">Workspace</div><nav>{([ ["overview", "Overview", "◈"], ["market", "Market data", "▥"], ["experiments", "Experiments", "⌘"], ["portfolio", "Portfolio", "◒"], ["provenance", "Data & provenance", "⌬"] ] as [ViewId, string, string][]).map(([id, label, icon]) => <button className={activeView === id ? "nav-item active" : "nav-item"} onClick={() => setActiveView(id)} key={id}><span aria-hidden="true">{icon}</span>{label}{id === "experiments" ? <em>run</em> : null}</button>)}</nav></div>
        <div className="sidebar-section sidebar-bottom"><div className="sidebar-label">Safety mode</div><div className="safety-status"><span className="status-dot" /><div><strong>Research only</strong><small>External execution disabled</small></div></div><div className="version-box"><span>Current build</span><strong>V0.6 reference</strong><small>local + Sites UI</small></div></div>
      </aside>
      <div className="main-column">
        <header className="topbar"><div className="mobile-brand"><AppMark /><strong>TradingLAB</strong></div><div className="breadcrumb"><span>TradingLAB</span><b>/</b><strong>{activeView === "overview" ? "Overview" : activeView === "market" ? "Market data" : activeView === "experiments" ? "Experiments" : activeView === "portfolio" ? "Portfolio" : "Data & provenance"}</strong></div><div className="topbar-right"><span className="sync-label"><span className="status-dot" /> {localApiAvailable ? "Snapshot local conectado" : "Evidence local"}</span><button className="avatar" aria-label="Research workspace">IG</button></div></header>
        <div className="content"><div className="filter-strip"><div className="filter-title"><span className="filter-icon">≡</span><strong>View filters</strong><span>{filteredRows.length} rows</span></div><div className="filter-control"><span className="filter-control-label">Strategy</span><select aria-label="Strategy" value={strategy} onChange={(event) => setStrategy(event.target.value)}><option value="ALL">All strategies</option>{STRATEGIES.map((item) => <option key={item} value={item}>{labelForStrategy(item)}</option>)}</select></div><div className="filter-control"><span className="filter-control-label">Asset</span><select aria-label="Asset" value={asset} onChange={(event) => setAsset(event.target.value)}><option value="ALL">All assets</option>{ASSETS.map((item) => <option key={item} value={item}>{item}</option>)}</select></div><div className="filter-control"><span className="filter-control-label">Split</span><select aria-label="Split" value={split} onChange={(event) => setSplit(event.target.value)}><option value="ALL">All splits</option>{SPLITS.map((item) => <option key={item} value={item}>{item}</option>)}</select></div><button className="reset-button" onClick={resetData}>Limpar dados</button></div>{viewContent}</div>
        <footer className="footer"><span>TradingLAB · Quant / Systematic Research Lab</span><span>V0.1 frozen · V0.2 reproduced · V0.6 reference</span></footer>
      </div>
    </main>
  );
}
