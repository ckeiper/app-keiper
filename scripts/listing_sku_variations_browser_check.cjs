const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch();try{const page=await browser.newPage();
for(const mode of ['empty','groups','limited','stale','partial','unknown'])for(const theme of ['dark','light'])for(const width of [1440,390,320]){
 await page.setViewportSize({width,height:900});await page.setContent(fs.readFileSync(`visual-qa/sku-variations-${mode}.html`,'utf8'));
 await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await page.locator('.sv-cards article').count(),4);
 assert.equal(await page.locator('.sv-item').count(),['empty','unknown'].includes(mode)?0:1);
 assert.equal(await page.locator('.sku-variations form[method=post]').count(),0);
 if(mode==='stale')assert.ok((await page.locator('.sv-item').textContent()).includes('atualidade não verificada'));
 if(mode==='partial')assert.ok((await page.locator('.sv-item').textContent()).includes('cobertura parcial'));
 if(mode==='limited')assert.equal(await page.locator('.sku-variations nav a').count(),2);
 if(['groups','partial','unknown'].includes(mode)&&width===390)await page.screenshot({path:`visual-qa/sku-variations-${mode}-${theme}.png`,fullPage:true});
}console.log('Official SKU variations: 36 responsive theme cases passed.');}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
