import Link from "next/link";

export const dynamic = "force-dynamic";

export default function PrivacyPage() {
  return (
    <main className="legal-page">
      <p><Link href="/">← TradingLAB</Link></p>
      <h1>Privacy Policy</h1>
      <p>TradingLAB usa a identidade fornecida pelo ambiente ChatGPT para controlar acesso ao workspace. O e-mail é usado para identificação e autorização da conta, não para vender publicidade.</p>
      <h2>Conexão Alpaca</h2>
      <p>Quando o usuário autoriza a conexão, recebemos um token OAuth da Alpaca. O token é armazenado em cookie HttpOnly criptografado no piloto e não é enviado ao navegador como texto visível. A integração inicial solicita somente leitura no ambiente Paper.</p>
      <h2>Dados de mercado</h2>
      <p>Eventos, preços e status exibidos podem ser processados para apresentar gráficos e métricas. Não redistribuímos dados de mercado fora dos direitos concedidos pelo respectivo provedor.</p>
      <h2>Segurança e exclusão</h2>
      <p>Nunca compartilhe sua API Secret. Para desconectar a Alpaca, revogue a autorização no provedor. O piloto será migrado para armazenamento server-side dedicado antes de uso multiusuário ou live.</p>
      <p>Última atualização: 23 de agosto de 2026.</p>
    </main>
  );
}
