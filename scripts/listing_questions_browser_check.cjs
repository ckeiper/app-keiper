const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{const page=await browser.newPage();
for(const mode of ['empty','ready','limited','page2'])for(const width of [1440,390,320]){
 await page.setViewportSize({width,height:900});await page.setContent(fs.readFileSync(`visual-qa/listing-questions-${mode}.html`,'utf8'));
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await page.locator('.lq-cards article').count(),3);
 assert.equal(await page.locator('.listing-questions').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(16, 34, 56)');
 assert.equal(await page.locator('.listing-questions #perguntas .lq-row').count(),mode==='empty'?0:10);
 assert.equal(await page.locator('.listing-questions #recorrencias .lq-row').count(),mode==='empty'?0:3);
 assert.equal(await page.locator('.listing-questions form[method=post]').count(),0);
 await page.locator('.listing-questions select').selectOption('ANSWERED');
 assert.equal(await page.locator('.listing-questions select').inputValue(),'ANSWERED');
 if(mode==='limited')assert.ok((await page.locator('.listing-questions [role=status]').textContent()).includes('1.000'));
 await page.screenshot({path:`visual-qa/listing-questions-${mode}-${width}.png`,fullPage:true});
}console.log('Question scope, limits, filters and desktop/mobile states passed.');}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
