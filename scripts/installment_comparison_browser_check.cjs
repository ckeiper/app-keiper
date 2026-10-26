const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true});try{const p=await b.newPage();
for(const mode of ['blank','ready','negative','error','three'])for(const width of [1440,390,320]){
 await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/installments-${mode}.html`,'utf8'));
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await p.locator('.ic-options fieldset').count(),3);
 assert.equal(await p.locator('.pf-hero').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(16, 34, 56)');
 if(['ready','negative','three'].includes(mode)){
  assert.equal(await p.locator('#installment-results tbody tr').count(),mode==='three'?3:2);
  await p.locator('#installment-results summary').click();
  assert.ok(await p.locator('#installment-results details').evaluate(e=>e.open));
  if(width===320)assert.ok(await p.locator('#installment-results .pf-table').evaluate(e=>e.scrollWidth>e.clientWidth));
 }else assert.equal(await p.locator('#installment-results').count(),0);
 if(mode==='error')assert.equal(await p.locator('.installment-comparison [role=alert]').count(),1);
 await p.screenshot({path:`visual-qa/installments-${mode}-${width}.png`,fullPage:true});
}console.log('Installment scenarios, pending costs, responsive forms and results passed.');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
