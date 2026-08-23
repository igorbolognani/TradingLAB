# TradingLAB Research Control Room

Interface local-first para visualizar os resultados do laboratório, filtrar
estratégia/ativo/período, carregar `all_trials.csv` ou JSON e preparar uma
execução reprodutível. O site não contém dados Yahoo, não executa ordens e não
substitui os contratos Python.

## Camadas de acesso

A página inicial é pública e compartilhável, com um layout próprio de
apresentação e sem a barra lateral do aplicativo. Ela explica o método, as
vantagens, as métricas e o fluxo de pesquisa sem expor snapshots de mercado.
Depois do login nativo **Entrar com ChatGPT**, a pessoa entra no aplicativo e
recebe o dashboard, a navegação e as ferramentas correspondentes à sua
permissão.

No servidor, a conta do proprietário é comparada com o segredo de ambiente
`TRADINGLAB_OWNER_USER_ID` configurado no Sites. Somente essa identidade recebe
as páginas **Market data** e **Portfolio replay**, que dependem do snapshot
local e da API em `127.0.0.1`. Outras contas autenticadas entram no dashboard e
recebem Experiments e Data & provenance, mas não recebem a camada privada de
dados e portfólio. A barra lateral do aplicativo é dividida em **Online
workspace** e **Offline research**. O código não adiciona OAuth externo;
um novo provedor só deve entrar depois de uma decisão explícita sobre
identidade, consentimento e credenciais.

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

Para usar uma fonte que não seja Yahoo/yfinance, configure um CSV próprio ou
licenciado no servidor local:

```bash
uv run tradinglab-dashboard --candle-file /caminho/feed-licenciado.csv
```

Também é possível usar **Importar CSV** na tela Market data. Nesse modo o
arquivo permanece no navegador. A interface mostra `realtime_active=false`
até que um adaptador live licenciado seja implementado.

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
