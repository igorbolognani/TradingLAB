# TradingLAB Research Control Room

Interface local-first para visualizar resultados, candles e controles do
TradingLAB. O site mantém o research offline separado do workspace online e
possui uma ponte Alpaca Paper opcional, privada e bloqueada por padrão. O
site não contém dados Yahoo distribuídos, não oferece live trading e não
substitui os contratos Python.

## Camadas de acesso

A página inicial é pública e compartilhável, com um layout próprio de
apresentação e sem a barra lateral do aplicativo. Ela explica o método, as
vantagens, as métricas e o fluxo de pesquisa sem expor snapshots de mercado.
Depois do login nativo **Entrar com ChatGPT**, a pessoa entra no aplicativo e
recebe o dashboard, a navegação e as ferramentas correspondentes à sua
permissão.

No servidor, a conta do proprietário é comparada com `TRADINGLAB_OWNER_EMAIL`
ou `TRADINGLAB_OWNER_USER_ID`. Somente essa identidade recebe as páginas
**Market data**, **Portfolio replay** e **Paper monitor**. Visitantes públicos
e outras contas autenticadas não recebem a camada privada de dados, conta,
posições ou ordens. A barra lateral do aplicativo é dividida em **Online
workspace** e **Offline research**.

O Paper monitor consulta a Alpaca no servidor: o navegador recebe apenas
valores normalizados, estado, origem, idade dos dados e reconciliação. A chave
nunca é enviada ao celular ou ao computador do visitante. O OAuth Alpaca
continua separado, com escopo de dados e aprovação Connect pendente; ele não é
uma autorização implícita para enviar ordens.

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

O site hospedado é público na apresentação e privado por identidade nas
rotas de dados/execução; o motor de pesquisa e seus artefatos continuam no
checkout local. Para o Paper monitor funcionar no site publicado, as variáveis
secretas precisam ser configuradas no ambiente de produção do Sites. O
`.env.local` serve apenas ao desenvolvimento local.

Quando o site privado hospedado for aberto no mesmo computador do checkout,
inicie `uv run tradinglab-dashboard` localmente para que o navegador possa
consultar os candles validados e as ações de Development/Validation. O serviço
local aceita apenas as origens localhost e o domínio privado do Sites; ele não
se torna um endpoint público de dados ou de ordens.

Para usar uma fonte que não seja Yahoo/yfinance, configure um CSV próprio ou
licenciado no servidor local:

```bash
uv run tradinglab-dashboard --candle-file /caminho/feed-licenciado.csv
```

Também é possível usar **Importar CSV** na tela Market data. Nesse modo o
arquivo permanece no navegador. A interface mostra `realtime_active=false`
para o snapshot histórico; o Paper monitor identifica separadamente o
transporte real da Alpaca e não mistura os dois datasets.

## Market data local

Na navegação **Market data**, o painel consulta o snapshot validado pelo
servidor local e mostra candles completos, volume, SMA20/SMA50/SMA200, ATR14,
qualidade, origem, versão, horários e hashes. A resposta informa
`realtime_active=false` porque o snapshot histórico não é um feed ao vivo.

O gráfico do workspace privado é interativo: o cursor mostra OHLCV da barra,
a roda do mouse aproxima ou afasta o histórico, **Mover** permite navegar pelas
barras, e **Nível**, **Linha** e **Marcar** permitem anotações visuais. SMA20,
SMA50, SMA200 e volume podem ser ligados ou desligados. As marcações ficam
somente no armazenamento local do navegador e não alteram o dataset, o
backtest ou qualquer ordem.

Endpoints usados pelo navegador:

```text
GET /api/health
GET /api/datasets
GET /api/candles?dataset_id=<id>&symbol=SPY&limit=240
```

Não há números demonstrativos no estado inicial. Sem um snapshot real e
validado, a tela permanece vazia.

## Alpaca Paper monitor

O **Paper monitor**, visível somente ao proprietário, fornece:

- status da conta, equity, cash e buying power;
- cotações IEX com origem, horário do evento, horário de recebimento,
  transporte, latência medida e idade do dado;
- candles OHLCV reais da Alpaca e cálculos básicos;
- posições atuais e ordens abertas;
- IDs do broker e uma visão de reconciliação;
- cancelamento de uma ordem ou de todas as ordens abertas;
- formulário de ordem Paper protegido por allowlist, quantidade inteira,
  limite financeiro, cotação recente, venda long-only e kill switch.

O envio de novas ordens permanece desativado por padrão:

```text
TRADINGLAB_EXECUTION_ENABLED=false
TRADINGLAB_PAPER_ENABLED=false
TRADINGLAB_KILL_SWITCH=true
```

Mesmo quando esses três controles forem liberados conscientemente, o backend
continua sem endpoint live. O contrato completo está em
`docs/ALPACA_PAPER_BRIDGE.md`.

## Portfolio V0.6

Na navegação **Portfolio**, o navegador pode chamar a API local e executar o
replay de referência do V0.6 com o snapshot real validado. O usuário escolhe
Development ou Validation OOS, uma das duas alocações declaradas (peso igual
ou inverso da volatilidade) e uma fricção pré-definida de 0, 5, 10 ou 25 bps.

O resultado mostra patrimônio líquido, CAGR, Sharpe, drawdown, custos,
decisões de fechamento, fills no próximo open, posições finais e proveniência.
O Holdout, otimização automática, paper trading, live trading e envio de
ordens continuam bloqueados. Também é possível carregar no navegador o JSON
produzido por `uv run tradinglab run-portfolio`.
