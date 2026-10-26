const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true});try{const p=await b.newPage();
for(const mode of ['ready','empty','gaps','changes','limited'])for(const width of [1440,390,320]){
 await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/price-stability-${mode}.html`,'utf8'));
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await p.locator('.price-stability').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(16, 34, 56)');
 if(mode==='limited')assert.equal(await p.locator('.ps-cards article').count(),0);
 else{
  assert.equal(await p.locator('.ps-cards article').count(),2);await p.locator('.price-stability summary').click();
  assert.equal(await p.locator('.ps-scroll tbody tr').count(),7);
  await p.locator('.ps-scroll').focus();assert.equal(await p.locator(':focus').getAttribute('role'),'region');
  if(width<700)assert.ok(await p.locator('.ps-scroll').evaluate(e=>e.scrollWidth>e.clientWidth));
 }
 await p.screenshot({path:`visual-qa/price-stability-${mode}-${width}.png`,fullPage:true});
}console.log('Price constancy coverage gates, amplitude, daily evidence and mobile checks passed.');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
