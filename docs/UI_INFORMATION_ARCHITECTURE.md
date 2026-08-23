# TradingLAB — arquitetura de interface V1.0

Este documento descreve a organização visual atual. Ele evita que a landing
pública e o workspace operacional voltem a misturar objetivos.

## Duas superfícies

### Landing pública

É a página compartilhável. Ela apresenta o produto, mostra uma prévia
interativa, resume o fluxo de trabalho e oferece login no início e no final.
Não exibe a barra lateral do aplicativo, snapshots privados, resultados
importados ou comandos técnicos.

As explicações detalhadas ficam em tópicos recolhíveis. O objetivo é permitir
que uma pessoa entenda o valor do produto sem transformar a primeira tela em um
manual.

### Aplicativo autenticado

Depois do login, a página abre diretamente no dashboard. A barra lateral é a
navegação principal:

| Grupo | Páginas | Acesso |
| --- | --- | --- |
| Workspace | Home, Paper, Market data, Portfolio replay | Paper para usuários conectados; Market e Portfolio para owner |
| Research | Experiments, Data & trust | Experiments para owner; resumo de dados para usuários |
| Manage | Profile, Settings, Help & contact, Admin/use tips | Admin somente owner |

No mobile, a barra lateral vira um menu deslizante. O conteúdo principal não
repete as abas: a toolbar superior mostra apenas a página atual e as ações
relevantes.

## Regra de conteúdo

- **Workspace** mostra informação para operar a ferramenta: candles, cotações,
  posições, ordens Paper, filtros, métricas e gráficos.
- **Data & trust** mostra somente um resumo compreensível de fonte, qualidade,
  horário, completude e estado histórico/realtime.
- **Admin/use tips** concentra manifestos, hashes, contratos, parâmetros fixos,
  mapa do produto, status de evidência e comandos de reprodução.
- Ajuda contextual aparece como um pequeno `?` junto ao campo. O texto é curto,
  aparece no hover ou foco e pode ser desligado em Settings.

## Gráfico

O gráfico é um workspace, não uma imagem estática. O usuário pode:

- inspecionar OHLCV com cursor;
- usar roda do mouse para zoom sem mover a página;
- arrastar o histórico com a ferramenta Mover;
- adicionar nível, linha de tendência e marcador;
- ligar/desligar SMA20, SMA50, SMA200 e volume;
- ajustar a visualização, desfazer e limpar desenhos;
- salvar ou não as marcações no dispositivo.

O gráfico nunca preenche preço ausente com valor inventado. A origem,
completude, idade, latência e estado `realtime_active` permanecem associados à
fonte carregada.

## Preferências locais

Settings controla apenas a apresentação do navegador:

- ajuda contextual;
- modo compacto;
- persistência de marcações.

Essas opções não alteram dados, cálculos, estratégias, permissões ou gates de
Paper/Live.

## Limites preservados

A reorganização visual não muda contratos de execução, dados ou segurança:

- Yahoo continua privado/local e não é redistribuído;
- o Paper continua explicitamente separado e limitado;
- Live, custódia, depósitos e pagamentos continuam fora do produto;
- o Project Holdout continua protegido;
- credenciais nunca entram no frontend;
- Admin é uma visão do proprietário, não um caminho alternativo para executar
  o holdout ou liberar Live.
