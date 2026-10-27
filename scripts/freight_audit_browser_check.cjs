const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{const page=await browser.newPage();
for(const mode of ['empty','saved','result','client','duplicate'])for(const width of [1440,390,320]){
 await page.setViewportSize({width,height:1000});await page.setContent(fs.readFileSync(`visual-qa/freight-audit-${mode}.html`,'utf8'));
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${mode}/${width} overflows`);
 const form=page.locator('#frete-upload-form');assert.equal(await form.count(),1);
 assert.equal(await form.locator('input[name=csrf_token]').count(),1);
 assert.equal(await form.locator('input[type=file]').getAttribute('accept'),'.xlsx,.csv');
 assert.equal(await form.locator('button[value=importar]').count(),mode==='client'?0:1);
 assert.equal(await form.locator('button[value=consolidar]').count(),mode==='client'?0:1);
 if(['saved','result','duplicate'].includes(mode))await page.locator('.fa-upload-toggle>summary').click();
 if(mode!=='client'){
  assert.equal(await page.locator('.fa-upload .fa-advanced').evaluate(e=>e.open),false);
  await page.locator('.fa-upload .fa-advanced summary').click();
  assert.equal(await page.locator('input[name=completo]').isChecked(),false);
  await page.locator('input[name=periodo_inicio]').fill('2026-09-17');
  await page.locator('input[name=periodo_fim]').fill('2026-10-17');
  assert.equal(await page.locator('.fa-day').count(),30);
  await page.locator('.fa-upload .fa-advanced summary').click();
 }
 if(['saved','result','duplicate'].includes(mode)){
  await page.locator('.fa-upload-toggle>summary').click();
  assert.equal(await page.locator('.fa-order-table tbody tr').count(),1);
  assert.ok((await page.locator('.fa-order-table').textContent()).includes('1001'));
  assert.equal(await page.locator('select[name=direcao]').inputValue(),'above');
  assert.ok((await page.locator('.fa-export').getAttribute('href')).includes('diferencas.csv'));
 }
 if(mode==='saved')assert.equal(await page.locator('.fa-day.is-covered').count(),12);
 if(mode==='empty')assert.ok((await page.locator('#fa-coverage').textContent()).includes('Sem cobertura'));
 if(mode==='result'){
  assert.ok((await page.locator('#fa-results').textContent()).includes('Indicadores importados.'));
  assert.equal(await page.locator('.ledger-groups').count(),1);
 }
 const colors=await page.locator('.fa-hero').evaluate(e=>getComputedStyle(e).backgroundImage);assert.ok(colors.includes('rgb(16, 36, 58)'));
 assert.equal(await page.locator('.fa-hero h2').evaluate(e=>getComputedStyle(e).color),'rgb(233, 242, 252)');
 if(mode==='saved')assert.equal(await page.locator('.fa-order-table thead th').first().evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(20, 46, 72)');
 await page.evaluate(()=>window.scrollTo(0,0));
 await page.screenshot({path:`visual-qa/freight-audit-${mode}-${width}.png`,fullPage:true});
}console.log('Freight audit empty/history/results, scoped actions and responsive checks passed.');}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
