const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage();
  const errors=[];page.on('pageerror',err=>errors.push(err.message));
  try {
    for(const state of ['ready','missing','stale']) {
      for(const width of [1440,390]) {
        await page.setViewportSize({width,height:900});
        await page.setContent(fs.readFileSync(`visual-qa/profitability-${state}.html`,'utf8'));
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${state} overflow at ${width}`);
        assert.equal(await page.locator('.pf-metric').count(),3);
        const figures=await page.locator('.pf-metric').allTextContents();
        assert.equal(figures.some(value=>value.includes('R$ 240,00')),state==='ready');
        await page.locator('.pf details summary').click();
        assert.equal(await page.locator('input[name=products]').isVisible(),true);
        assert.equal(await page.locator('input[name=_csrf]').count(),1);
        assert.equal(await page.locator('input[name=confirmed]').isChecked(),false);
        assert.equal(await page.locator('.pf form[method=post]').evaluate(form=>form.checkValidity()),false);
        if(state==='ready')await page.screenshot({path:`visual-qa/profitability-${width}.png`,fullPage:true});
      }
    }
    assert.deepEqual(errors,[]);
    console.log('Profitability: desktop/mobile, unknown/stale values, form confirmation and layout passed.');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1});
