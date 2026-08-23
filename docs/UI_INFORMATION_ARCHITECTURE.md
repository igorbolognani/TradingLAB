# TradingLAB — arquitetura de interface V1.0

Este documento descreve a organização visual atual. Ele evita que a landing
pública e o workspace operacional voltem a misturar objetivos.

## Duas superfícies

### Landing pública

É a página compartilhável. Ela apresenta o produto, mostra uma prévia
interativa, resume o valor do workspace e oferece login no início e no final.
Não exibe a barra lateral do aplicativo, snapshots privados, resultados
importados ou comandos técnicos.

O conteúdo de orientação saiu da landing e passou para a página pública
**About & Usage**. A landing vende a ideia rapidamente; About & Usage concentra
o guia completo em uma leitura linear, com fluxo, telas, ativos, gráficos,
métricas, dados, acesso, limites e contato.

### Aplicativo autenticado

Depois do login, a página abre diretamente no dashboard. A barra lateral é a
navegação principal:

| Grupo | Páginas | Acesso |
| --- | --- | --- |
| Workspace | Home, Paper, Market data, Portfolio replay | Paper para usuários conectados; Market e Portfolio para owner |
| Research | Experiments | Somente owner |
| Manage | About & usage, Profile, Settings | About é a única página explicativa |

No mobile, a barra lateral vira um menu deslizante. O conteúdo principal não
repete as abas: a toolbar superior mostra apenas a página atual e as ações
relevantes.

## Regra de conteúdo

- **Workspace** mostra informação para operar a ferramenta: candles, cotações,
  posições, ordens Paper, filtros, métricas e gráficos.
- **About & usage** concentra a explicação completa do produto em uma página
  única, acessível antes e depois do login. Ela também reúne fonte, qualidade,
  horários, limites, contratos, evidências, reprodução e contato.
- Não existem páginas separadas apenas para explicação. Data & trust, Admin/use
  tips e Help & contact foram absorvidos pelo About & usage; as telas de uso
  exibem somente controles, estados e resultados necessários à tarefa.
- Ajuda contextual aparece como um pequeno `?` junto ao campo. O texto abre no
  hover ou foco e pode ser desligado em Settings. Ativos mostram nome, tipo de
  exposição, função no universo e pontos de atenção; os demais campos explicam
  cada opção e a consequência prática da escolha sem alterar o layout principal.

## Gráfico

O gráfico é um workspace, não uma imagem estática. O usuário pode:

- inspecionar OHLCV com cursor;
- usar roda do mouse para zoom sem mover a página;
- arrastar o histórico com a ferramenta Mover;
- adicionar nível, linha de tendência e marcador;
- ligar/desligar SMA20, SMA50, SMA200 e volume;
- ajustar a visualização, desfazer e limpar desenhos;
- salvar ou não as marcações no dispositivo.

No Paper workspace, depois de carregar candles, o mesmo fluxo fica disponível
no celular: a seção Candles completos mostra um gráfico responsivo, botões para
40/90/120 barras e um inspetor OHLCV. Basta tocar em uma vela para selecionar a
barra; o painel não captura o scroll vertical da página.

O gráfico nunca preenche preço ausente com valor inventado. A origem,
completude, idade, latência e estado `realtime_active` permanecem associados à
fonte carregada.

## Preferências locais

Settings controla apenas a apresentação do navegador:

- ajuda contextual;
- modo compacto;
- persistência de marcações;
- ativo padrão;
- fuso preferido para leitura;
- nome local do workspace.

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
