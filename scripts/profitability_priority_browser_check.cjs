const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});const page=await browser.newPage();
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 try {
  for(const width of [1440,390]) {
   await page.setViewportSize({width,height:900});
   await page.setContent(fs.readFileSync('visual-qa/profitability-priorities.html','utf8'));
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   const cards=page.locator('.kp-item');assert.equal(await cards.count(),3);
   assert.equal(await page.locator('.kp-queue h2').evaluate(el=>getComputedStyle(el).color),'rgb(255, 255, 255)');
   assert.ok((await cards.nth(0).textContent()).includes('Contribuição documentada negativa: R$ -80,00'));
   assert.ok((await cards.nth(0).textContent()).includes('70,00% para -80,00%'));
   for(const index of [1,2]) {
    assert.ok(!(await cards.nth(index).textContent()).includes('Contribuição documentada'));
    assert.ok(!(await cards.nth(index).textContent()).includes('Margem documentada caiu'));
    assert.ok((await cards.nth(index).textContent()).includes('margem'));
   }
   assert.equal(await cards.nth(0).getAttribute('href'),'/diagnostico/42/MLB100');
   await cards.nth(0).focus();assert.equal(await page.locator(':focus').getAttribute('href'),'/diagnostico/42/MLB100');
   await page.evaluate(()=>window.scrollTo(0,0));
   await page.screenshot({path:`visual-qa/profitability-priorities-${width}.png`,fullPage:true});
  }
  assert.deepEqual(errors,[]);console.log('Financial priority cards: verified negative evidence, stale/missing suppression, desktop/mobile and keyboard passed.');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
