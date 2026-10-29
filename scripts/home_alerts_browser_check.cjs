const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const {chromium} = require('playwright');
(async () => {
 const failed = new Set(), posts = new Map(), reads = new Map(), completed = new Set();
 let documents = 0, readBeforeComplete = false;
 const server = http.createServer((req, res) => {
  res.setHeader('Content-Type', 'application/json');
  const url = new URL(req.url, 'http://local');
  const refresh = url.pathname.match(/^\/atualizacoes\/(\d+)\/ads$/);
  if (refresh) {
   assert.equal(url.searchParams.get('de'), url.searchParams.get('ate'));
   const id = refresh[1];
   if (req.method === 'POST') {
    posts.set(id, (posts.get(id) || 0) + 1);
    completed.delete(id);
    return res.end(JSON.stringify({id: 'job' + id, status: 'aguardando'}));
   }
   if (failed.has(id)) return res.end(JSON.stringify({id: 'job' + id, status: 'falhou'}));
   completed.add(id);
   return res.end(JSON.stringify({id: 'job' + id, status: 'concluida', fim_em: Math.floor(Date.now() / 1000)}));
  }
  const alerts = url.pathname.match(/^\/painel\/alertas\/(\d+)$/);
  if (alerts) {
   const id = alerts[1];
   reads.set(id, (reads.get(id) || 0) + 1);
   if (!completed.has(id)) readBeforeComplete = true;
   return res.end(JSON.stringify({known: true, url: '/painel/alertas/' + id + '/detalhes', alerts: id === '1' ?
    [{code: 'budget', severity: 'critical', label: '3 campanhas sem orçamento disponível'},
     {code: 'forecast', severity: 'warning', label: '2 campanhas podem esgotar o orçamento em 1 hora'}] : []}));
  }
  if (url.pathname === '/painel/tendencias') return res.end('{}');
  documents++;
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.end(fs.readFileSync('visual-qa/home-alerts.html'));
 });
 await new Promise(r => server.listen(0, '127.0.0.1', r));
 const browser = await chromium.launch(process.env.PLAYWRIGHT_EXECUTABLE_PATH ? {executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH} : {});
 const page = await browser.newPage(), errors = [];
 page.on('pageerror', e => errors.push(e.message));
 const url = 'http://127.0.0.1:' + server.address().port;
 try {
  for (const width of [1440, 390, 320]) {
   posts.clear(); reads.clear(); completed.clear(); failed.clear();
   await page.setViewportSize({width, height: 850}); await page.goto(url);
   await page.getByText('3 campanhas sem orçamento disponível', {exact: true}).waitFor();
   await page.getByText('Ads atualizados às', {exact: false}).waitFor();
   assert.deepEqual([...posts.entries()].sort(), [['1', 1], ['2', 1]]);
   assert.equal(readBeforeComplete, false);
   assert.equal(await page.getByText('+1 alerta', {exact: true}).getAttribute('href'), '/painel/alertas/1/detalhes');
   assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
   await page.screenshot({path: 'visual-qa/home-alerts-' + width + '.png', fullPage: true});

   failed.add('2'); posts.clear(); reads.clear(); completed.clear(); await page.goto(url);
   const card = page.locator('.kh-store[data-id="2"]');
   const retry = card.getByRole('button', {name: 'Falha ao atualizar Ads · tentar novamente'});
   await retry.waitFor(); await page.getByText('Ads atualizados parcialmente às', {exact: false}).waitFor();
   await page.evaluate(() => { window.untouchedCard = document.querySelector('.kh-store[data-id="1"]'); window.untouchedAlerts = window.untouchedCard.querySelector('.kh-alerts').innerHTML; });
   const baseline = documents;
   // A repeated failure must remain local, and fast repeated clicks must enqueue only once.
   await retry.evaluate(button => { button.click(); button.click(); });
   await card.getByRole('button', {name: 'Atualizando Ads…', exact: true}).waitFor();
   assert.equal(await card.getAttribute('data-id'), '2');
   assert.equal(await card.locator('.kh-alerts').getAttribute('aria-busy'), 'true');
   await retry.waitFor();
   assert.equal(posts.get('2'), 2); assert.equal(posts.get('1'), 1); assert.equal(documents, baseline);
   failed.delete('2'); await retry.click();
   await card.getByText('Nenhum alerta nos dados disponíveis', {exact: true}).waitFor();
   await page.getByText('Ads atualizados às', {exact: false}).waitFor();
   assert.equal(posts.get('2'), 3); assert.equal(posts.get('1'), 1);
   assert.equal(reads.get('1'), 1); assert.equal(reads.get('2'), 1); assert.equal(documents, baseline);
   assert.equal(await page.evaluate(() => window.untouchedCard === document.querySelector('.kh-store[data-id="1"]') && window.untouchedAlerts === window.untouchedCard.querySelector('.kh-alerts').innerHTML), true);
   assert.equal(await card.locator('.kh-alerts').getAttribute('aria-busy'), 'false');
  }
  assert.deepEqual(errors, []);
  console.log('Home alerts: bounded initial refresh, store-only retries, duplicate-click guard, recovery status and untouched cards at 1440/390/320 passed.');
 } finally { await browser.close(); server.close(); }
})().catch(e => { console.error(e); process.exit(1); });
