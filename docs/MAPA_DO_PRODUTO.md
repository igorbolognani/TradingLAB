# TradingLAB — mapa do produto em linguagem simples

## A ideia em uma frase

O TradingLAB é um laboratório para descobrir se uma ideia de investimento tem
evidência histórica suficiente para merecer o próximo teste. Ele não é uma
máquina que garante lucro e não transforma automaticamente um backtest em uma
ordem real.

Uma comparação simples:

- **Research** é o laboratório: fazemos experiências, registramos o que foi
  testado e tentamos encontrar erros.
- **Paper** é o simulador: acompanhamos o mercado como se houvesse uma conta,
  mas sem dinheiro real.
- **Live** é a operação: uma camada separada, com dinheiro e risco reais.

Os três podem aparecer na mesma interface web, mas não devem compartilhar o
mesmo caminho técnico de execução.

## O caminho completo

```text
ideia
  ↓
regra escrita de forma objetiva
  ↓
teste local com dados congelados
  ↓
testes de estabilidade, custos e períodos diferentes
  ↓
reprodução em outra engine
  ↓
painel privado de acompanhamento
  ↓
paper trading com aprovação humana
  ↓
revisão de segurança
  ↓
live trading separado e desabilitado por padrão
```

O resultado de uma etapa é autorização para investigar a etapa seguinte; não é
uma promessa de que a estratégia funciona no futuro.

## O que cada palavra quer dizer

| Termo | Explicação sem jargão |
| --- | --- |
| **Estratégia** | Uma regra repetível, por exemplo: comprar quando o preço estiver acima da média de 200 dias. |
| **Script** | Um programa que executa essa regra. Ele é instrução; não é prova de que a regra é boa. |
| **Engine** | O motor que percorre as datas, simula compras e vendas e calcula o resultado. |
| **Dataset** | O conjunto de preços usado no teste. Se ele mudar, o resultado pode mudar. |
| **Snapshot** | Uma cópia identificada do dataset, guardada para que o mesmo teste possa ser repetido. |
| **Benchmark** | Um comparador. Buy & Hold responde: “teria sido melhor simplesmente manter o ativo?”. |
| **Holdout** | Um período reservado para ser visto apenas depois das decisões principais. Depois que é visto, deixa de ser intocado. |
| **Fricção** | Uma estimativa de custos, spread e slippage. Ela reduz o resultado simulado. |
| **Adapter** | Uma ponte entre a regra principal e uma engine específica. A regra não fica presa a uma ferramenta só. |
| **Frontend** | A tela que vemos e usamos no navegador. |
| **Backend** | O serviço que lê dados, executa tarefas e conversa com provedores. Segredos nunca devem ficar no frontend. |
| **API** | Uma porta organizada para dois programas conversarem. |
| **Credential/secret** | Chave privada que autoriza acesso a um provedor ou conta. Não pode ir para GitHub nem para o navegador. |

## O que já existe

- **V0.1:** laboratório local com dados separados, regras causais, custos,
  métricas, artefatos e holdout controlado.
- **V0.2:** reprodução independente em LEAN para verificar se os sinais e os
  fills continuam iguais em outro motor.
- **V0.3–V0.5:** pontes de pesquisa para paper, TradingView e Forex, sem
  conexão de broker nem envio de ordem.
- **V0.6:** replay de portfólio com dados reais do snapshot validado, caixa
  compartilhado, fills, curva de patrimônio e pesos declarados, sem otimização
  automática ou acesso ao holdout.
- **V1.0:** research operacional privado com interface Sites, candles
  provider-neutral, BYOD/arquivo licenciado, diagnóstico de frescor e separação
  explícita dos gates realtime/paper/live.
- **Interface:** painel Sites/local para filtros, importação de resultados e
  execução local Development/Validation; ele começa vazio para não inventar
  números.

## Como Research e Execution ficam na mesma interface

Antes das funções futuras de Execution, o produto já separa duas experiências
para não confundir apresentação com operação:

- **Landing pública:** primeira tela compartilhável, sem barra lateral e sem
  dados operacionais. Explica o que o laboratório faz e como interpretar seus
  resultados.
- **Aplicativo autenticado:** dashboard e ferramentas de uso. A navegação é
  dividida em **Workspace** (dashboard, Paper, Market data e Portfolio),
  **Research** (Experiments e o resumo Data & trust) e **Manage** (Profile,
  Settings, Help e Admin para o proprietário). O status `LIVE DESATIVADO` fica
  visível porque replay e Paper controlado não são execução live.

Isso permite que outra pessoa conheça o produto sem receber o snapshot Yahoo ou
os controles privados, enquanto o proprietário trabalha no mesmo endereço com
permissões diferentes.

Na tela, a pessoa pode enxergar dois espaços:

### Research workspace

Pode conter:

- estratégias e versões;
- dados e sua origem;
- backtests;
- gráficos e comparações;
- relatórios de risco;
- parâmetros congelados;
- decisões humanas.

O workspace de pesquisa deve ser privado para o proprietário e colaboradores
autorizados; a landing e a explicação pública podem ser acessadas por qualquer
visitante.

### Execution workspace

Pode conter, em uma fase posterior:

- estado da conta paper ou live;
- sinais aprovados;
- ordens pretendidas;
- ordens aceitas ou rejeitadas;
- fills parciais;
- posição e caixa;
- reconciliação entre o que foi planejado e o que ocorreu.

Esse workspace não deve executar qualquer estratégia encontrada no Research.
Ele só recebe uma versão explicitamente aprovada, com identidade e permissões
verificáveis.

## Por que os dados são uma decisão de produto

O código pode baixar preços de uma fonte pessoal para pesquisa local. Publicar
esses preços em um site é outra coisa: é redistribuição ou exibição para
terceiros. Por isso, antes de preencher o Sites com dados reais, precisamos
escolher uma fonte cujo contrato permita o uso pretendido e registrar:

1. quais campos podem ser exibidos;
2. por quanto tempo podem ficar armazenados;
3. se podemos mostrar linhas OHLC completas ou apenas resultados derivados;
4. como atualizar e identificar cada versão dos dados;
5. quais usuários podem ver esses dados.

Até essa decisão, o caminho correto é importar localmente um relatório real ou
usar uma fonte contratada. Valores gerados apenas para preencher a tela não são
evidência e não devem aparecer como se fossem resultados do TradingLAB.

## Quando o live poderá existir

O live não deve ser uma opção escondida no mesmo botão do paper. A evolução
segura é:

1. research aprovado;
2. paper com credencial e endpoint separados;
3. observação por um período definido;
4. reconciliação e revisão humana;
5. ambiente live separado, com credencial própria;
6. ativação manual, limites rígidos e desligamento imediato possível.

Mesmo com tudo isso, o live continua sendo uma decisão do proprietário e um
risco financeiro. O sistema pode tornar a operação mais controlável; não pode
eliminar o risco.
