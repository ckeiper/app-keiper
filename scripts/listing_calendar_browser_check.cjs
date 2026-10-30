const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{
 const page=await browser.newPage();
 for(const mode of ['empty','ready','page2'])for(const width of [1440,390,320]){
 await page.setViewportSize({width,height:900});await page.setContent(fs.readFileSync(`visual-qa/listing-calendar-${mode}.html`,'utf8'));
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await page.locator('.lc-day').count(),31);
 assert.equal(await page.locator('.lc-task').count(),mode==='empty'?0:10);
 assert.equal(await page.locator('.lc').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(16, 34, 56)');
 assert.equal(await page.locator('.lc form[method=post]').count(),0);
 await page.locator('.lc input').fill('2026-11');assert.equal(await page.locator('.lc input').inputValue(),'2026-11');
 await page.screenshot({path:`visual-qa/listing-calendar-${mode}-${width}.png`,fullPage:true});
 }
 console.log('Calendar desktop/mobile and empty/paginated states passed.');
 }finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
