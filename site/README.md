# TradingLAB Research Control Room

Interface local-first para visualizar os resultados do laboratório, filtrar
estratégia/ativo/período, carregar `all_trials.csv` ou JSON e preparar uma
execução reprodutível. O site não contém dados Yahoo, não executa ordens e não
substitui os contratos Python.

## Usar

```bash
npm install
npm run dev
```

Abra `http://localhost:3000/`. Sem a API local, a interface funciona em modo de
visualização e aceita um relatório exportado pelo seletor de arquivo. Para
habilitar a bateria Development/Validation local sem holdout, em outro terminal
na raiz do repositório execute:

```bash
uv run tradinglab-dashboard
```

O site hospedado é uma camada de leitura privada; o motor de pesquisa e seus
artefatos continuam no checkout local.

Quando o site privado hospedado for aberto no mesmo computador do checkout,
inicie `uv run tradinglab-dashboard` localmente para que o navegador possa
consultar os candles validados e as ações de Development/Validation. O serviço
local aceita apenas as origens localhost e o domínio privado do Sites; ele não
se torna um endpoint público de dados ou de ordens.

## Market data local

Na navegação **Market data**, o painel consulta o snapshot validado pelo
servidor local e mostra candles completos, volume, SMA20/SMA50/SMA200, ATR14,
qualidade, origem, versão, horários e hashes. A resposta informa
`realtime_active=false` porque o snapshot histórico não é um feed ao vivo.

Endpoints usados pelo navegador:

```text
GET /api/health
GET /api/datasets
GET /api/candles?dataset_id=<id>&symbol=SPY&limit=240
```

Não há números demonstrativos no estado inicial. Sem um snapshot real e
validado, a tela permanece vazia.
