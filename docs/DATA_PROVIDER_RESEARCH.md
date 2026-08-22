# Pesquisa de dados, qualidade e atualização

## Decisão curta

Não existe uma fonte “melhor” para todos os usos. O fornecedor precisa ser
escolhido junto com o direito de uso:

| Uso | Requisito mínimo | Candidato inicial | Observação |
| --- | --- | --- | --- |
| Pesquisa histórica local | OHLCV completo, ações corporativas, histórico identificável | yfinance enquanto o uso for pessoal | Continua fora do GitHub e do Sites; é um conector de pesquisa, não uma licença de redistribuição. |
| Pesquisa histórica de maior fidelidade | Dados point-in-time, referência de instrumentos, timestamps e ações | Databento | Tem histórico e live separados, timestamp de evento/recebimento e regras de licença por dataset/venue. |
| Dashboard privado com ações dos EUA | REST, WebSocket, agregados, histórico e contrato de display | Polygon/Massive ou Databento | A escolha depende do plano e do status non-professional/professional. |
| API com barras oficiais/atrasadas e onboarding institucional | Barras, trades, quotes e referência | Nasdaq Data Link | O acesso real-time/delayed é contratado; não assumir que a documentação gratuita implica redistribuição livre. |
| Protótipo multiativo de baixa latência | WebSocket de trades/quotes, Forex e crypto | EODHD ou Twelve Data | Bons candidatos de integração, mas a licença e a completude precisam ser confirmadas para o caso de uso. |

Essa tabela é uma triagem técnica, não uma autorização legal. Antes de exibir
OHLC em um Site para qualquer pessoa além do proprietário, o contrato do
dataset e da bolsa precisa responder explicitamente: display, armazenamento,
cache, distribuição, usuários, atraso mínimo e uso derivado.

## O que a pesquisa oficial confirma

- O [yfinance](https://ranaroussi.github.io/yfinance/index.html) é uma
  ferramenta para pesquisa/educação e depende das condições de uso do Yahoo.
  Por isso continua adequado apenas ao snapshot local pessoal do V0.1.
- O [Databento separa o serviço histórico do live](https://databento.com/docs/getting-started/build-first-app),
  oferece OHLCV, trades, quotes, instrument definitions e ações corporativas,
  e registra timestamps de evento e de recebimento. A documentação de
  [licenciamento](https://databento.com/docs/portal) distingue display,
  non-display e distribuição externa; a permissão depende do dataset e da
  venue.
- O [Polygon/Massive](https://polygon.io/docs/rest/stocks/overview) documenta
  REST, WebSocket e flat files, com dados SIP consolidados para as bolsas dos
  EUA. A própria documentação informa que timestamps são UTC e que pre/post
  market são sessões diferentes; isso deve ser preservado no modelo de dados.
- A [Alpaca diferencia IEX de SIP](https://docs.alpaca.markets/us/docs/market-data-faq):
  o acesso gratuito de market data ao vivo é IEX, uma única bolsa, enquanto o
  feed SIP é um produto diferente. Portanto, Alpaca não deve ser assumida como
  fonte-mestre de pesquisa somente porque será um possível broker futuro.
- A [Nasdaq Data Link](https://docs.data.nasdaq.com/docs/api-for-real-time-or-delayed-data)
  oferece endpoints de last sale, quote, snapshot e bars em modo real-time ou
  delayed, mas o acesso exige credenciais e contratação do produto.
- A [EODHD documenta WebSockets de trades e quotes](https://eodhd.com/financial-apis/new-real-time-data-api-websockets)
  e informa latência de transporte inferior a 50 ms no gateway em seus planos;
  isso não é a mesma coisa que latência ponta a ponta nem garante completude
  de uma fita consolidada.
- A documentação do [Twelve Data](https://twelvedata.com/docs) oferece séries
  históricas e WebSocket, mas a própria FAQ informa que o WebSocket não entrega
  OHLC pronto. O TradingLAB teria de agregar trades e validar o resultado antes
  de tratá-lo como candle.

## Contrato canônico de um candle

Um candle é um resumo de todos os negócios em uma janela. Para uma barra de
cinco minutos, por exemplo, `Open` é o primeiro preço, `High` o maior, `Low` o
menor, `Close` o último e `Volume` a quantidade negociada. O sistema não deve
confundir um candle em formação com um candle encerrado.

Cada registro normalizado deve carregar, no mínimo:

```text
instrument_id       identificador estável do instrumento, não apenas ticker
symbol               símbolo exibido
venue/feed           bolsa, consolidator ou feed usado
interval             1d, 5m, 1m etc.
bar_start_utc        início da janela em UTC
bar_end_utc          final da janela em UTC
session_date         data de negociação na timezone da bolsa
event_time_utc       quando o mercado produziu o evento
receive_time_utc     quando o fornecedor recebeu/entregou o evento
is_complete          se a barra está encerrada
open/high/low/close  OHLC completo
volume/vwap/count    volume, preço médio ponderado e número de negócios
price_basis          raw, adjusted ou total-return, explicitamente
provider/version     origem e versão do cliente/endpoint
sequence             ordem do feed, quando disponível
quality_flags        gaps, correção, atraso, out-of-order, cancelamento
```

No V0.1, o snapshot diário já possui a parte histórica do contrato: origem,
versão, query, timezone, calendário, ações corporativas, hash e basis de preço.
O novo endpoint local expõe essa proveniência e os candles sem alterar os
arquivos congelados.

## Horários e latência

O relógio deve ser dividido em três partes:

```text
event_time   → quando o negócio/barra ocorreu no mercado
receive_time → quando o fornecedor recebeu o evento
display_time → quando o usuário o viu no navegador
```

“Latência de 50 ms” normalmente descreve apenas um trecho entre o gateway e o
cliente. A latência real do produto é:

```text
mercado → fornecedor → nosso backend → cache/banco → navegador
```

O painel deve mostrar `unknown` quando um dos relógios não existir. Nunca deve
transformar um timestamp ausente em “tempo real”.

Para o mercado de ações dos EUA, a aplicação deve também distinguir:

- pré-mercado;
- sessão regular;
- pós-mercado;
- barra em formação;
- barra encerrada;
- feriado ou sessão encurtada.

O contrato V0.1 continua restrito à sessão regular XNYS e ao próximo open
válido. Intraday e live precisam de um contrato novo, não de uma alteração
silenciosa no dataset antigo.

## Arquitetura recomendada sem lock-in

```text
provider adapter
    ↓
raw event journal (privado, imutável)
    ↓
normalizer + clock/session mapper
    ↓
quality gate + checksum + manifest
    ├── research archive (T+1, canônico)
    ├── dashboard cache (licensed display)
    └── stream/cache privado (live ou delayed)
             ↓
        sinais e métricas
             ↓
        aprovação humana
             ↓
   execução separada (futuro)
```

O painel não deve falar diretamente com um fornecedor nem carregar uma chave.
O backend é o único lugar possível para credencial futura, e o repositório
público nunca recebe essa credencial.

## Alternativas criativas e seguras

1. **BYOD — bring your own data.** O usuário fornece sua própria conexão ao
   fornecedor; o serviço guarda apenas a referência e produz métricas. É uma
   forma de evitar redistribuição, mas não resolve sozinho segurança,
   isolamento e limites do contrato.
2. **Display atrasado.** Para uma interface pública, usar somente dados com
   atraso contratual e mostrar o horário de corte. Isso reduz custo de licença
   e risco de distribuição, mas não é adequado para uma decisão intraday.
3. **Derived-only public.** Publicar apenas métricas, sinais agregados e hashes,
   sem permitir reconstruir o OHLC. Isso ainda precisa ser avaliado no contrato
   porque alguns fornecedores tratam derivados como dados de mercado.
4. **Dois fornecedores em modo sentinela.** Um feed é canônico e outro é
   apenas verificador. Se preço, timestamp ou volume divergirem acima do limite
   definido, o sistema mostra alerta e suspende o resultado; não escolhe
   silenciosamente o valor “mais conveniente”.
5. **Replay de fita real.** Gravar eventos recebidos com timestamp e reproduzi-
   los localmente em velocidade real ou acelerada. Isso permite testar interface
   e latência sem enviar ordens e sem fingir que replay é live.

## Gates antes de usar dinheiro real

O caminho completo ainda precisa de uma camada privada de execução. Antes dela,
o TradingLAB deve conseguir demonstrar:

1. candles completos e encerrados por uma fonte contratada;
2. reconexão e detecção de gap/duplicata/out-of-order;
3. latência observável por trecho;
4. reconciliação entre sinal pretendido, ordem, fill e posição;
5. idempotência (repetir uma mensagem não cria duas ordens);
6. kill switch testado;
7. contas paper/live e credenciais fisicamente separadas;
8. logs imutáveis e revisão humana;
9. período de paper previamente definido;
10. revisão legal/licença e aprovação explícita do proprietário.

Até esses gates, qualquer botão de execução no TradingLAB significa apenas
replay ou backtest local. Isso não reduz a utilidade do produto; impede que a
interface de pesquisa seja confundida com autorização financeira.
