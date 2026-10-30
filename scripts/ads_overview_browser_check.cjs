const fs=require('node:fs'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const chart=await fetch('https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js').then(r=>{assert.ok(r.ok);return r.text()});
 const server=http.createServer((req,res)=>{if(req.url.startsWith('/atualizacoes/')){res.setHeader('Content-Type','application/json');return res.end('{"status":"nenhuma"}')};res.setHeader('Content-Type','text/html; charset=utf-8');const name=req.url.includes('empty')?'ads-overview-empty':req.url.includes('campanha=inexistente')?'ads-overview-filtered':'ads-overview';res.end(fs.readFileSync('visual-qa/'+name+'.html'))});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
 try{
  browser=await chromium.launch(process.env.PLAYWRIGHT_EXECUTABLE_PATH?{executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH}:{});
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('https://cdn.jsdelivr.net/**',r=>r.fulfill({contentType:'text/javascript',body:chart}));
  const base='http://127.0.0.1:'+server.address().port;
  for(const [name,width] of [['desktop',1440],['tablet',820],['mobile',390],['small-mobile',320]]){
   await page.setViewportSize({width,height:1000});await page.goto(base+'/ads/1');
   await page.waitForFunction(()=>typeof Chart!=='undefined'&&Chart.getChart('ads-historico'));
   await page.evaluate(()=>{const c=Chart.getChart('ads-historico');c.stop();c.options.animation=false;c.update('none')});
   const seriesCard=page.locator('.kp-chart-controls button[data-dataset-index="0"]').first();
   await seriesCard.waitFor();
   await seriesCard.click();assert.equal(await page.evaluate(()=>Chart.getChart('ads-historico').isDatasetVisible(0)),false);
   await seriesCard.click();assert.equal(await page.evaluate(()=>Chart.getChart('ads-historico').isDatasetVisible(0)),true);
   assert.equal(await page.locator('.ka-kpis .stat').count(),9);
   assert.equal(await page.locator('.ka-kpis .num').first().textContent(),'R$ 644,00');
   assert.equal(await page.locator('.ka-kpis .num').nth(1).textContent(),'R$ 6.251,00');
   assert.equal(await page.locator('.ka-hero h2').evaluate(e=>getComputedStyle(e).color),'rgb(237, 245, 255)');
   assert.equal(await page.locator('.ka-kpis .num').first().evaluate(e=>getComputedStyle(e).color),'rgb(244, 249, 255)');
   assert.equal(await page.locator('.kc-campaign-name').first().evaluate(e=>getComputedStyle(e).color),'rgb(230, 243, 255)');
   if(width<=640)assert.equal(await page.locator('.kc-campaign-row').first().evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(20, 43, 66)');
   assert.equal(await page.locator('.kc-campaign-row').first().locator('td').count(),8);
   assert.equal(await page.locator('[data-label="Orçamento diário"]').first().textContent(),'R$ 100,00');
   assert.equal(await page.locator('[data-label="ACOS objetivo"]').first().textContent(),'25,00%');
   assert.ok(await page.locator('[data-label="ACOS objetivo"]').first().isVisible());
   assert.equal(await page.locator('.ka-alert').count(),4);
   assert.equal(await page.locator('.ks-sidebar a[aria-current=page]').getAttribute('href'),'/ads/1');
   assert.equal(await page.locator('.ks-sidebar nav a').count(),13);
   assert.equal(await page.locator('.ks-sidebar nav a[href="/ia-keiper/1"]').textContent(),'KEVIA');
   assert.equal(await page.locator('a[href="/campanhas/1"]').count(),0);
   assert.equal(await page.locator('.ka-actions a').getAttribute('href'),'#ka-campaign-list');
   const toggle=page.locator(width<=640?'.ks-mobile-toggle':'.ks-toggle');
   assert.equal(await toggle.getAttribute('aria-expanded'),width<=640?'false':'true');
   await toggle.click();
   if(width<=640){await page.locator('.ks-nav-group summary').filter({hasText:'Vendas'}).click();assert.ok(await page.getByRole('link',{name:'Auditoria de Frete',exact:true}).isVisible());await page.keyboard.press('Escape');assert.equal(await toggle.getAttribute('aria-expanded'),'false');}
   else{assert.equal(await toggle.getAttribute('aria-expanded'),'false');assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await toggle.click();}
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Horizontal overflow: '+width+' '+JSON.stringify(await page.evaluate(()=>[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,10).map(e=>({tag:e.tagName,cls:e.className,right:e.getBoundingClientRect().right})))));
   await page.screenshot({path:'visual-qa/ads-overview-'+name+'.png',fullPage:true});
   await page.screenshot({path:'visual-qa/ads-overview-'+name+'-top.png'});
  }
  await page.setViewportSize({width:1440,height:1000});await page.goto(base+'/ads/1');
  await page.locator('.kc-campaign-row').first().press('Enter');assert.equal(new URL(page.url()).pathname,'/ads/1/campanha/a');
  await page.goto(base+'/ads/1');await page.locator('input[name=campanha]').fill('inexistente');await page.locator('.kc-campaigns button').click();
  await page.getByText('Nenhuma campanha atende aos filtros.').waitFor();assert.equal(new URL(page.url()).searchParams.get('campanha'),'inexistente');
  await page.goto(base+'/empty');assert.equal(await page.locator('.ka-kpis').count(),0);await page.getByText('Sem dados de publicidade para este período').waitFor();
  await page.screenshot({path:'visual-qa/ads-overview-empty.png',fullPage:true});assert.deepEqual(errors,[]);
  console.log('Store sidebar, collapse, mobile, KPIs, escaped names, alerts, campaign links, filters and empty state passed.');
 }finally{if(browser)await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1});
