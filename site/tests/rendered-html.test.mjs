import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const templateRoot = new URL("../", import.meta.url);

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the TradingLAB control room", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /TradingLAB — Pesquisa quantitativa auditável/i);
  assert.match(html, /Quant \/ systematic research lab/i);
  assert.match(html, /Entrar com ChatGPT/i);
  assert.match(html, /Public overview/i);
  assert.match(html, /Local data hidden/i);
  assert.doesNotMatch(html, /Market data/i);
  assert.doesNotMatch(html, /Portfolio controls/i);
  assert.doesNotMatch(html, /Your site is taking shape|codex-preview|react-loading-skeleton/i);
});

test("keeps site assets inside the app source", async () => {
  const [page, client, layout] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/research-lab.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(page, /TRADINGLAB_OWNER_USER_ID/);
  assert.match(page, /isConfiguredOwner/);
  assert.match(client, /all_trials\.csv/);
  assert.match(client, /run-battery/);
  assert.match(client, /api\/candles/);
  assert.match(client, /api\/candles-file/);
  assert.match(client, /api\/run-portfolio/);
  assert.match(client, /tradinglab\/v0\.6-portfolio\/v1/);
  assert.match(client, /Executar replay local/);
  assert.match(client, /Carregar JSON V0\.6/);
  assert.match(client, /Importar CSV/);
  assert.match(client, /browser_file/);
  assert.match(client, /realtime_active/);
  assert.match(client, /latency_ms/);
  assert.match(client, /V1\.0/);
  assert.match(client, /Candles completos/);
  assert.match(client, /Project Holdout/);
  assert.match(layout, /lang="pt-BR"/);
  await assert.rejects(access(new URL("public/_sites-preview", templateRoot)));
});
