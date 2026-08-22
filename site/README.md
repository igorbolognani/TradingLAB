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
