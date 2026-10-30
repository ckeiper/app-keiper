const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{const page=await browser.newPage();
for(const mode of ['empty','active','future','late','done'])for(const width of [1440,390,320]){
 await page.setViewportSize({width,height:900});await page.setContent(fs.readFileSync(`visual-qa/listing-onboarding-${mode}.html`,'utf8'));
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await page.locator('.ob-stage').count(),4);
 assert.equal(await page.locator('.onboarding').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(16, 34, 56)');
 if(mode==='empty'){
 const form=page.locator('.onboarding form');assert.equal(await form.evaluate(e=>e.checkValidity()),false);
 await form.locator('[name=start_date]').fill('2026-10-26');await form.locator('[name=responsible]').fill('Equipe');
 assert.equal(await form.evaluate(e=>e.checkValidity()),true);assert.equal(await form.locator('[name=_csrf]').count(),1);
 }else{
 assert.equal(await page.locator('.onboarding form').count(),0);
 assert.equal(await page.locator('.ob-progress').getAttribute('value'),mode==='done'?'4':'0');
 assert.equal(await page.locator('.ob-stage a').count(),4);
 }
 await page.screenshot({path:`visual-qa/listing-onboarding-${mode}-${width}.png`,fullPage:true});
}console.log('Onboarding stages, explicit scheduling, progress and mobile states passed.');}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
