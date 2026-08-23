import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const templateRoot = new URL("../", import.meta.url);

async function render(headers = {}) {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("https://tradinglab-public.example/", { headers: { accept: "text/html", ...headers } }),
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
  assert.match(html, /TradingLAB — Ferramentas de trading com clareza e controle/i);
  assert.match(html, /Trading tools · decisão com controle/i);
  assert.match(html, /Trading workflow/i);
  assert.match(html, /Gráficos completos/i);
  assert.match(html, /Gráfico de mercado/i);
  assert.match(html, /Entrar com ChatGPT/i);
  assert.match(html, /public-shell/i);
  assert.match(html, /Comece pela experiência pública/i);
  assert.doesNotMatch(html, /Research loop|Quant \/ systematic research lab|Pesquisa auditável|Um laboratório/i);
  assert.doesNotMatch(html, /class="sidebar"/i);
  assert.doesNotMatch(html, /Home \/ dashboard/i);
  assert.doesNotMatch(html, /Market data/i);
  assert.doesNotMatch(html, /Portfolio controls/i);
  assert.doesNotMatch(html, /Your site is taking shape|codex-preview|react-loading-skeleton/i);
});

test("authenticated visitors enter the app without private owner navigation", async () => {
  const response = await render({
    "oai-authenticated-user-id": "viewer-test",
    "oai-authenticated-user-email": "viewer@example.test",
    "oai-authenticated-user-full-name": "Viewer",
  });
  const html = await response.text();
  assert.match(html, /class="sidebar"/i);
  assert.match(html, /Home \/ dashboard/i);
  assert.match(html, /Offline research/i);
  assert.doesNotMatch(html, /Portfolio replay/i);
  assert.doesNotMatch(html, /Market data/i);
});

test("the configured owner enters the app with private navigation", async () => {
  const previousOwnerId = process.env.TRADINGLAB_OWNER_USER_ID;
  process.env.TRADINGLAB_OWNER_USER_ID = "owner-test";
  try {
    const response = await render({
      "oai-authenticated-user-id": "owner-test",
      "oai-authenticated-user-email": "owner@example.test",
      "oai-authenticated-user-full-name": "Owner",
    });
    const html = await response.text();
    assert.match(html, /class="sidebar"/i);
    assert.match(html, /Market data/i);
    assert.match(html, /Portfolio replay/i);
    assert.match(html, /live execution disabled/i);
  } finally {
    if (previousOwnerId === undefined) delete process.env.TRADINGLAB_OWNER_USER_ID;
    else process.env.TRADINGLAB_OWNER_USER_ID = previousOwnerId;
  }
});

test("keeps site assets inside the app source", async () => {
  const [page, client, layout] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/research-lab.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(page, /TRADINGLAB_OWNER_USER_ID/);
  assert.match(page, /isConfiguredOwner/);
  assert.match(page, /initialView/);
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
  assert.match(client, /Paper monitor/);
  assert.match(client, /api\/alpaca\/direct\/status/);
  assert.match(client, /Candles completos/);
  assert.match(client, /Project Holdout/);
  assert.match(client, /public-shell/);
  assert.match(client, /Online workspace/);
  assert.match(client, /Offline research/);
  assert.match(client, /interactive-chart-shell/);
  assert.match(client, /onWheel/);
  assert.match(client, /addEventListener\("wheel"/);
  assert.match(client, /workspace-tabbar/);
  assert.match(client, /Inserir candles/);
  assert.match(client, /localStorage/);
  assert.match(client, /Linha/);
  assert.match(client, /Desfazer/);
  const paper = await readFile(new URL("../app/paper-control.tsx", import.meta.url), "utf8");
  assert.match(paper, /data_age_seconds/);
  assert.match(paper, /Paper conectado/);
  assert.match(paper, /Cancelar todas/);
  assert.match(paper, /kill_switch/);
  assert.match(paper, /setInterval\(\(\) => void refresh\(\), 15000\)/);
  assert.match(layout, /lang="pt-BR"/);
  await assert.rejects(access(new URL("public/_sites-preview", templateRoot)));
});

test("keeps the OAuth Paper pilot and Live execution gates server-side", async () => {
  const [oauth, user, status, schema] = await Promise.all([
    readFile(new URL("../app/alpaca-oauth.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/alpaca-user.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/api/alpaca/user/status/route.ts", import.meta.url), "utf8"),
    readFile(new URL("../db/trading-store.ts", import.meta.url), "utf8"),
  ]);
  assert.match(oauth, /scope: mode === "trade" \? "data trading" : "data"/);
  assert.match(oauth, /live_connect_disabled/);
  assert.match(user, /paper_pilot_allowlist_required/);
  assert.match(user, /paper_execution_disabled/);
  assert.match(user, /liveExecutionEnabled: booleanEnv/);
  assert.match(status, /live_execution_enabled: false/);
  assert.match(schema, /appendExecutionEvent/);
  assert.match(schema, /encrypted_token/);
});
