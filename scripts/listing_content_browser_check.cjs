const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{const page=await browser.newPage();
for(const mode of ['empty','reviewed','error','page2'])for(const width of [1440,390,320]){
 await page.setViewportSize({width,height:900});await page.setContent(fs.readFileSync(`visual-qa/listing-content-${mode}.html`,'utf8'));
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await page.locator('.content-review form').count(),8);
 assert.equal(await page.locator('.cr-counts article').count(),4);
 assert.equal(await page.locator('.content-review').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(16, 34, 56)');
 const details=page.locator('.cr-criterion details').first();if(!await details.evaluate(e=>e.open))await details.locator('summary').click();
 const form=details.locator('form');assert.equal(await form.evaluate(e=>e.checkValidity()),false);
 await form.locator('select').selectOption('revise');await form.locator('textarea').fill('Conferir as especificações nas imagens do produto.');
 assert.equal(await form.evaluate(e=>e.checkValidity()),true);
 for(const f of await page.locator('.content-review form').all())assert.equal(await f.locator('input[name=_csrf]').count(),1);
 if(mode==='error')assert.ok((await page.locator('.content-review [role=status]').textContent()).includes('outra aba'));
 await page.screenshot({path:`visual-qa/listing-content-${mode}-${width}.png`,fullPage:true});
}console.log('Content checklist evidence forms and responsive states passed.');}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
