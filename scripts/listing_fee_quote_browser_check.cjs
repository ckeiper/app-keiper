const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true});try{const p=await b.newPage();
for(const mode of ['blank','quoted','zero','unknown','missing'])for(const width of [1440,390,320]){
 await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/fee-quote-${mode}.html`,'utf8'));
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await p.locator('.fee-quote form[method=post]').count(),1);
 assert.ok((await p.locator('.fee-quote .pf-hero').evaluate(e=>getComputedStyle(e).backgroundImage)).includes('rgb(16, 31, 53)'));
 if(['quoted','zero','missing'].includes(mode)){
  assert.equal(await p.locator('.fee-quote .pf-metric').count(),3);
  await p.locator('#fee-quote-result summary').click();
  assert.ok((await p.locator('#fee-quote-result details').textContent()).includes('quantidade 1'));
  if(mode==='zero')assert.ok((await p.locator('.fee-quote .pf-metric').nth(1).textContent()).includes('R$ 0,00'));
  if(mode==='missing')assert.ok((await p.locator('.fee-quote .pf-metric').nth(2).textContent()).includes('Não informado'));
 }else assert.equal(await p.locator('.fee-quote .pf-metric').count(),0);
 if(mode==='blank')assert.equal(await p.locator('#fee-quote-result').count(),0);
 if(mode==='unknown')assert.ok((await p.locator('.fee-quote [role=status]').textContent()).includes('Sem cotação verificável'));
 await p.screenshot({path:`visual-qa/fee-quote-${mode}-${width}.png`,fullPage:true});
}console.log('Official quote, unknown/zero separation and responsive checks passed.');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
