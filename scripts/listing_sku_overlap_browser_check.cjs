const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true});try{const p=await b.newPage();
for(const mode of ['empty','groups','limited','stale'])for(const width of [1440,390,320]){
 await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/listing-sku-overlap-${mode}.html`,'utf8'));
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await p.locator('.sku-cards article').count(),4);assert.equal(await p.locator('.sku-item').count(),mode==='empty'?0:1);
 assert.equal(await p.locator('.sku-overlap').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(16, 34, 56)');
 assert.equal(await p.locator('.sku-overlap form[method=post]').count(),0);
 await p.locator('.sku-overlap input').fill('ABC');assert.equal(await p.locator('.sku-overlap input').inputValue(),'ABC');
 if(mode==='stale')assert.ok((await p.locator('.sku-item').textContent()).includes('não verificado'));
 if(mode==='limited')assert.equal(await p.locator('.sku-overlap nav a').count(),2);
 await p.screenshot({path:`visual-qa/listing-sku-overlap-${mode}-${width}.png`,fullPage:true});
}console.log('SKU overlap exact filter, cards, limits and mobile checks passed.');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
