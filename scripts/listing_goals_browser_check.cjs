const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{const page=await browser.newPage();
for(const mode of ['empty','alert','met','unknown','scheduled','ended','cancelled'])for(const width of [1440,390,320]){
 await page.setViewportSize({width,height:900});await page.setContent(fs.readFileSync(`visual-qa/listing-goals-${mode}.html`,'utf8'));
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await page.locator('.sg-row').count(),mode==='empty'?0:1);
 assert.equal(await page.locator('.stock-goals').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(16, 34, 56)');
 await page.locator('.stock-goals summary').click();const form=page.locator('.stock-goals details form');
 assert.equal(await form.evaluate(e=>e.checkValidity()),false);
 await form.locator('[name=minimum]').fill('5');await form.locator('[name=start_date]').fill('2026-10-26');await form.locator('[name=end_date]').fill('2026-11-24');await form.locator('[name=responsible]').fill('Equipe');
 assert.equal(await form.evaluate(e=>e.checkValidity()),true);
 for(const f of await page.locator('.stock-goals form').all())assert.equal(await f.locator('[name=_csrf]').count(),1);
 if(mode==='alert')assert.ok(await page.locator('.sg-alert').isVisible());
 if(mode==='cancelled')assert.equal(await page.locator('.sg-row form').count(),0);
 await page.screenshot({path:`visual-qa/listing-goals-${mode}-${width}.png`,fullPage:true});
}console.log('Stock goals states, explicit forms, cancellation and mobile layout passed.');}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
