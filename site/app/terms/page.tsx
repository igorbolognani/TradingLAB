import Link from "next/link";

export const dynamic = "force-dynamic";

export default function TermsPage() {
  return (
    <main className="legal-page">
      <p><Link href="/">← TradingLAB</Link></p>
      <h1>Terms of Use</h1>
      <p>TradingLAB é uma ferramenta de análise, visualização e pesquisa. Não é uma corretora, não mantém custódia, não recebe depósitos e não oferece aconselhamento financeiro.</p>
      <h2>Alpaca</h2>
      <p>Quando o usuário conecta sua conta Alpaca, o acesso ocorre por autorização OAuth. A integração inicial é somente leitura e usa o ambiente Paper. O usuário mantém sua conta, suas credenciais e a responsabilidade por suas decisões.</p>
      <h2>Limitações</h2>
      <p>Dados de mercado podem apresentar atraso, indisponibilidade ou diferenças entre provedores. Resultados históricos e simulações não garantem desempenho futuro.</p>
      <h2>Uso proibido</h2>
      <p>Não é permitido tentar contornar controles de acesso, compartilhar tokens, usar a aplicação para atividade ilegal ou interpretar seus resultados como recomendação personalizada.</p>
      <p>Última atualização: 23 de agosto de 2026.</p>
    </main>
  );
}
