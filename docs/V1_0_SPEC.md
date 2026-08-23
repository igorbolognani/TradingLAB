# TradingLAB V1.0 — Research operacional

## Definição desta versão

V1.0 significa que o TradingLAB é utilizável como produto privado de pesquisa
quantitativa, com dados históricos reais, fontes substituíveis, interface web,
validação de qualidade, proveniência e reprodução. Não significa que exista
uma estratégia aprovada, um feed realtime ou envio de ordens.

O produto continua dividido em duas pistas:

```text
Research truth
  snapshots, arquivos licenciados, backtests, LEAN, portfólio e relatórios

Execution future gate
  paper e live separados, com credenciais, reconciliação e aprovação humana
```

As duas pistas podem aparecer na mesma interface, mas nenhuma estratégia é
promovida automaticamente e nenhum botão de research envia ordem.

## Entregas V1.0

- V0.1 preservada: yfinance/Yahoo funciona somente no snapshot privado local.
- V0.2 preservada: reprodução independente em LEAN continua separada.
- V0.3–V0.6 preservadas: bridges, replay de paper, TradingView, Forex e
  portfólio continuam broker-neutral.
- Landing page pública compartilhável, separada visualmente do aplicativo e
  sem barra lateral operacional; ela apresenta método, fluxo, métricas e
  limites.
- Aplicativo autenticado com dashboard inicial e navegação em duas áreas:
  **Online workspace** para dashboard, Market data e Portfolio replay; e
  **Offline research** para Experiments e Data & provenance.
- Login nativo do ChatGPT e owner gate; Market data e Portfolio replay ficam
  disponíveis somente para a identidade do proprietário.
- Candles OHLCV completos, volume e indicadores SMA/ATR calculados
  causalmente.
- Endpoint local de candles históricos com manifesto, checksum, timezone,
  calendário, ações corporativas e base de preço.
- Contrato `tradinglab.candle.v1` para CSV de fonte licenciada ou BYOD, sem
  rede e sem dependência de yfinance.
- Servidor local configurável com `--candle-file` para exibir esse arquivo na
  mesma interface.
- Importação de CSV direto no navegador; o arquivo não é enviado ao servidor.
- O aplicativo base não importa yfinance; o conector Yahoo é um extra opcional
  instalado apenas no ambiente privado do proprietário.
- Diagnóstico de duplicidade, ordem, OHLC, completude, idade do dado e
  timestamps de evento/recepção.
- Workspace de candles interativo com crosshair/inspeção OHLCV, zoom, navegação,
  indicadores alternáveis e anotações locais de nível, linha e marcador.
- `realtime_active=false` e `latency_ms=null` quando a fonte não fornece um
  feed ao vivo ou relógios suficientes.
- GitHub público sem snapshots, artefatos, credenciais ou caminho de broker.

## CSV canônico sem Yahoo

O mínimo aceito é:

```text
timestamp_utc,symbol,open,high,low,close,volume
```

`timestamp_utc` precisa conter horário e offset explícito, por exemplo
`2026-08-23T14:30:00Z`. Uma data solta como `2026-08-23` é rejeitada para não
inventar o instante do evento.

Os campos opcionais são:

```text
instrument_id,venue,feed,interval,bar_start_utc,bar_end_utc,
session_date,event_time_utc,receive_time_utc,is_complete,vwap,trade_count,
price_basis,provider,provider_version,sequence,quality_flags
```

O campo `receive_time_utc` permite medir o trecho `event_time → receive_time`.
Isso não é a latência completa do produto: ainda faltam ingestão, cache e
renderização no navegador.

Validação local:

```bash
uv run tradinglab validate-candle-file \
  --path /caminho/para/feed-licenciado.csv \
  --symbol SPY
```

Visualização pelo servidor local:

```bash
uv run tradinglab-dashboard \
  --candle-file /caminho/para/feed-licenciado.csv
```

O caminho privado Yahoo, quando desejado, é instalado separadamente:

```bash
uv sync --all-groups --extra yahoo
```

Esse caminho não baixa dados, não grava o arquivo no Git e não transforma uma
fonte desconhecida em fonte autorizada. A licença e a permissão de uso do
arquivo continuam sendo responsabilidade do proprietário.

## Relógios e frescor

O painel diferencia:

| Campo | Significado |
| --- | --- |
| `event_time` | Quando o mercado ou o agregador marcou o evento. |
| `receive_time` | Quando o fornecedor recebeu/capturou o evento. |
| `observed_at` | Quando o TradingLAB calculou o status. |
| `data_age_seconds` | Tempo desde o último evento até `observed_at`. |
| `latency_ms` | Mediana de `receive_time - event_time`, quando possível. |
| `latency_scope` | Explica qual trecho foi medido. |
| `realtime_active` | Só pode ser `true` com adaptador live explícito e saudável. |
| `is_complete` | Distingue barra fechada de barra em formação. |

Um valor ausente permanece ausente. O sistema não troca `null` por zero nem
chama um snapshot histórico de realtime.

## Provedores e caminho de migração

O contrato do aplicativo é independente do fornecedor:

```text
adapter do provedor
  → evento bruto privado
  → normalização de relógio/sessão
  → quality gate + checksum
  → archive de research e/ou cache licenciado
  → interface
```

O próximo adaptador recomendado é Databento para pesquisa privada com
timestamps de evento/recepção e histórico/live separados. Polygon/Massive é a
alternativa para ações americanas com REST/WebSocket. Nasdaq Data Link é uma
alternativa contratual para dados delayed/realtime. yfinance permanece apenas
como fonte pessoal histórica. A decisão final depende do plano, da bolsa, do
uso pessoal/profissional e da permissão de display/cache.

## O que fica para depois

### Realtime e baixa latência

Não está ativado na V1.0. A implementação posterior deverá acrescentar:

1. adaptador WebSocket ou equivalente do provedor escolhido;
2. agregação de trades/quotes em candles;
3. marcação de barra em formação e encerramento;
4. reconexão, heartbeat, gap, duplicata e mensagens fora de ordem;
5. `event_time`, `receive_time`, `ingest_time` e `display_time`;
6. medição ponta a ponta e orçamento de latência;
7. cache privado com política de expiração;
8. replay de eventos reais para testar a interface sem ordens.

### Paper

O próximo passo seguro é observar sinais aprovados em um simulador/reconciliador
por um período previamente definido. Uma futura conta paper exige adapter
separado, segredo fora do Git, idempotência, fills parciais, rejeições, rate
limits, kill switch e comparação entre intenção e execução.

### Live

Live permanece fora do repositório de research. Só poderia existir depois de
revisão humana, reconciliação paper, contas separadas, credenciais separadas,
limites de posição/perda, desligamento manual e revisão da licença dos dados.

## Possibilidades de uso

- pesquisa pessoal privada com snapshot Yahoo;
- pesquisa com arquivo exportado de um provedor contratado;
- dashboard atrasado para dados cuja licença autorize display;
- publicação apenas de métricas derivadas, quando o contrato permitir;
- dois provedores em modo sentinela para alertar divergências;
- replay de uma fita realtime gravada para testar reconnect e latência;
- comparação entre o mesmo sinal em Python, LEAN, portfólio e Forex;
- workspace Research e um futuro workspace Execution, com permissões e
  fingerprints diferentes.

Nenhuma dessas possibilidades transforma evidência histórica em promessa de
rentabilidade.
