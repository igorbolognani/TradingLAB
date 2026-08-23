"use client";

import { useMemo, useState } from "react";
import type { PointerEvent as ReactPointerEvent, ReactNode } from "react";

/** Small, reusable explanations keep the workspace useful without filling it with help text. */
export function HelpDot({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="help-dot-wrap">
      <button type="button" className="help-dot" aria-label={label}>
        ?
      </button>
      <span className="help-popover" role="tooltip">
        {children}
      </span>
    </span>
  );
}

export function InfoDisclosure({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details className="compact-disclosure">
      <summary>{title}</summary>
      <div className="compact-disclosure-body">{children}</div>
    </details>
  );
}

type AssetDescription = {
  name: string;
  exposure: string;
  role: string;
  watch: string;
};

const ASSET_DESCRIPTIONS: Record<string, AssetDescription> = {
  SPY: {
    name: "SPDR S&P 500 ETF Trust",
    exposure: "um conjunto amplo de ações de grandes empresas dos Estados Unidos",
    role: "referência do mercado acionário americano e benchmark do painel",
    watch: "quedas amplas do mercado, concentração em large caps e efeito dos dividendos na base de preço",
  },
  IWM: {
    name: "iShares Russell 2000 ETF",
    exposure: "empresas americanas de menor capitalização, conhecidas como small caps",
    role: "observar um segmento geralmente mais sensível ao ciclo doméstico e à volatilidade",
    watch: "liquidez, mudanças no ciclo econômico e oscilações maiores que as de um índice de large caps",
  },
  EFA: {
    name: "iShares MSCI EAFE ETF",
    exposure: "ações de mercados desenvolvidos fora dos Estados Unidos e do Canadá, incluindo Europa, Australásia e Extremo Oriente",
    role: "diversificação geográfica em relação ao mercado americano",
    watch: "moedas, horários de negociação diferentes e regimes econômicos internacionais",
  },
  TLT: {
    name: "iShares 20+ Year Treasury Bond ETF",
    exposure: "títulos do Tesouro dos Estados Unidos com vencimento longo",
    role: "acompanhar duration e comportamento de renda fixa em cenários de risco ou mudança de juros",
    watch: "sensibilidade elevada às taxas de juros; o preço do ETF pode cair quando os juros sobem",
  },
  GLD: {
    name: "SPDR Gold Shares",
    exposure: "ouro por meio de uma estrutura de ETF que busca acompanhar o preço do metal",
    role: "observar um ativo real/commodity com dinâmica diferente das ações e dos títulos",
    watch: "dólar, juros reais, demanda por proteção e ausência de fluxo de caixa como o de uma empresa",
  },
};

export function AssetHelp({ symbol, label = "Sobre o ativo" }: { symbol?: string | null; label?: string }) {
  const asset = symbol ? ASSET_DESCRIPTIONS[symbol] : null;
  return (
    <HelpDot label={label}>
      {asset ? (
        <>
          <strong className="help-popover-title">{symbol} · {asset.name}</strong>
          <span className="help-popover-copy">É um ETF: uma cesta negociada em bolsa, não uma ação individual.</span>
          <ul className="help-popover-list">
            <li><b>Exposição:</b> {asset.exposure}.</li>
            <li><b>Por que aparece:</b> {asset.role}.</li>
            <li><b>Observe:</b> {asset.watch}.</li>
          </ul>
          <span className="help-popover-footnote">Descrição educacional do universo do TradingLAB; não é recomendação.</span>
        </>
      ) : (
        <>
          <strong className="help-popover-title">Universo de ativos</strong>
          <span className="help-popover-copy">O painel trabalha com cinco ETFs para comparar exposições econômicas diferentes sem misturar os ativos em uma única série.</span>
          <ul className="help-popover-list">
            {Object.entries(ASSET_DESCRIPTIONS).map(([key, value]) => <li key={key}><b>{key}:</b> {value.role}.</li>)}
          </ul>
          <span className="help-popover-footnote">Escolha um símbolo para ver a explicação específica.</span>
        </>
      )}
    </HelpDot>
  );
}

export type ChartCandle = {
  event_time: string;
  session: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  is_complete?: boolean | null;
};

function chartNumber(value: number | null | undefined, digits = 2): string {
  return value == null ? "—" : value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** A touch-friendly candle view for the Paper workspace, with no page-scroll hijacking. */
export function PaperCandleChart({ candles, symbol, timeframe }: { candles: ChartCandle[]; symbol: string; timeframe: string }) {
  const valid = useMemo(() => candles.filter((candle) => candle.high != null && candle.low != null), [candles]);
  const [range, setRange] = useState(90);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const visible = useMemo(() => valid.slice(-Math.min(range, valid.length)), [range, valid]);
  const startIndex = valid.length - visible.length;
  const selected = selectedIndex == null ? valid.at(-1) : valid[selectedIndex];
  const selectedIsVisible = selectedIndex == null || selectedIndex >= startIndex;
  const plot = { left: 56, right: 14, top: 18, priceBottom: 226, volumeTop: 244, volumeBottom: 304, width: 720, height: 330 };
  const prices = visible.flatMap((candle) => [candle.high ?? 0, candle.low ?? 0]);
  const maximum = Math.max(...prices, 1);
  const minimum = Math.min(...prices, maximum);
  const priceRange = Math.max(maximum - minimum, Math.abs(maximum) * 0.002, 0.000001);
  const volumes = visible.map((candle) => candle.volume ?? 0);
  const maximumVolume = Math.max(...volumes, 1);
  const chartWidth = plot.width - plot.left - plot.right;
  const slot = chartWidth / Math.max(visible.length, 1);
  const bodyWidth = Math.max(2, Math.min(11, slot * 0.62));
  const x = (index: number) => plot.left + index * slot + slot / 2;
  const y = (price: number) => plot.top + ((maximum - price) / priceRange) * (plot.priceBottom - plot.top);

  function selectCandle(event: ReactPointerEvent<SVGSVGElement>) {
    if (!visible.length) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const localX = Math.max(0, Math.min(rect.width, event.clientX - rect.left));
    const localIndex = Math.max(0, Math.min(visible.length - 1, Math.floor((localX / rect.width) * visible.length)));
    setSelectedIndex(startIndex + localIndex);
  }

  return (
    <div className="paper-candle-chart">
      <div className="paper-chart-toolbar" role="toolbar" aria-label={`Visualização de candles ${symbol}`}>
        <span className="paper-chart-hint">Toque em uma vela para ver OHLCV</span>
        <div className="paper-chart-range" aria-label="Quantidade de barras visíveis">
          {[40, 90, 120].map((value) => <button key={value} type="button" className={range === value ? "active" : ""} onClick={() => { setRange(value); setSelectedIndex(null); }} disabled={valid.length < value}>{value}</button>)}
          <button type="button" onClick={() => { setRange(Math.min(90, valid.length)); setSelectedIndex(null); }}>Ajustar</button>
        </div>
      </div>
      {visible.length ? (
        <>
          <div className="paper-chart-canvas-wrap">
            <svg className="paper-chart-canvas" viewBox={`0 0 ${plot.width} ${plot.height}`} role="img" aria-label={`Gráfico de candles de ${symbol} em ${timeframe}`} onPointerDown={selectCandle}>
              {[0, 1, 2, 3, 4].map((step) => {
                const gridY = plot.top + ((plot.priceBottom - plot.top) * step) / 4;
                return <g key={step}><line x1={plot.left} x2={plot.width - plot.right} y1={gridY} y2={gridY} className="paper-chart-grid" /><text x="5" y={gridY + 4} className="paper-chart-axis">{chartNumber(maximum - (priceRange * step) / 4)}</text></g>;
              })}
              <text x={plot.left} y={plot.volumeBottom + 20} className="paper-chart-axis">volume</text>
              {visible.map((candle, index) => {
                const open = candle.open ?? candle.close ?? 0;
                const close = candle.close ?? open;
                const high = candle.high ?? Math.max(open, close);
                const low = candle.low ?? Math.min(open, close);
                const rising = close >= open;
                const candleColor = rising ? "#19a974" : "#e36d5c";
                const volumeHeight = ((candle.volume ?? 0) / maximumVolume) * (plot.volumeBottom - plot.volumeTop);
                const globalIndex = startIndex + index;
                const isSelected = selectedIndex === globalIndex;
                return <g key={`${candle.event_time}-${index}`}><line x1={x(index)} x2={x(index)} y1={y(high)} y2={y(low)} stroke={candleColor} strokeWidth="1.2" /><rect x={x(index) - bodyWidth / 2} y={Math.min(y(open), y(close))} width={bodyWidth} height={Math.max(1, Math.abs(y(open) - y(close)))} fill={candleColor} opacity="0.95" /><rect x={x(index) - bodyWidth / 2} y={plot.volumeBottom - volumeHeight} width={bodyWidth} height={volumeHeight} fill={candleColor} opacity="0.28" />{isSelected ? <line x1={x(index)} x2={x(index)} y1={plot.top} y2={plot.volumeBottom} className="paper-chart-selection" /> : null}</g>;
              })}
              {[0, Math.floor((visible.length - 1) / 2), visible.length - 1].map((index) => <text key={index} x={Math.max(plot.left, x(index) - 30)} y={plot.height - 7} className="paper-chart-axis">{visible[index].session}</text>)}
            </svg>
          </div>
          <div className="paper-chart-inspector" aria-live="polite">
            <div><span>Barra selecionada</span><strong>{selectedIsVisible && selected ? selected.session : "—"}</strong></div>
            <div><span>Open</span><strong>{selectedIsVisible ? chartNumber(selected?.open) : "—"}</strong></div>
            <div><span>High</span><strong>{selectedIsVisible ? chartNumber(selected?.high) : "—"}</strong></div>
            <div><span>Low</span><strong>{selectedIsVisible ? chartNumber(selected?.low) : "—"}</strong></div>
            <div><span>Close</span><strong>{selectedIsVisible ? chartNumber(selected?.close) : "—"}</strong></div>
            <div><span>Volume</span><strong>{selectedIsVisible ? chartNumber(selected?.volume, 0) : "—"}</strong></div>
          </div>
        </>
      ) : <div className="paper-empty">Nenhuma barra válida para desenhar.</div>}
      <div className="chart-footnote">{symbol} · {timeframe} · dados recebidos do Paper. O gráfico é informativo; a última vela pode estar em formação.</div>
    </div>
  );
}
