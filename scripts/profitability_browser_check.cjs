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
        assert.equal(await page.locator('.pf-grid > .pf-metric').count(),3);
        assert.equal(await page.locator('#pf-recuperacao').count(),1);
        assert.equal(await page.locator('#pf-recuperacao .pf-metric').count(),state==='ready'?3:0);
        assert.ok((await page.locator('#pf-recuperacao').textContent()).includes(state==='ready'?'não comprova lucro líquido':'custos'));
        assert.equal(await page.locator('.pf-hero h2').evaluate(el=>getComputedStyle(el).color),'rgb(239, 245, 255)');
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
    for(const state of ['ready','negative','missing','stale']) {
      for(const width of [1440,390]) {
        await page.setViewportSize({width,height:900});
        await page.setContent(fs.readFileSync(`visual-qa/profitability-comparison-${state}.html`,'utf8'));
        const available=['ready','negative'].includes(state);
        assert.equal(await page.locator('#pf-unidades').count(),1);
        assert.equal(await page.locator('.pf-unit-table tbody tr').count(),available?8:0);
        if(available)assert.ok((await page.locator('#pf-unidades').textContent()).includes('Médias históricas'));
        assert.equal(await page.locator('#pf-recuperacao').count(),1);
        if(state==='negative')assert.ok((await page.locator('#pf-recuperacao').textContent()).includes('Déficit de contribuição documentada'));
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Comparison ${state} body overflow at ${width}`);
        assert.equal(await page.locator('.pf-comparison-table').count(),available?1:0);
        assert.equal(await page.locator('.pf-delta').count(),available?3:0);
        assert.equal(await page.locator('.pf-source-link').getAttribute('href'),'?inicio=2026-10-10&fim=2026-10-16');
        assert.equal(await page.locator('#pf-comparacao').getByText('Margem documentada menor',{exact:true}).count(),available?1:0);
        if(available)assert.equal(await page.locator('.pf-comparison-table tbody tr').count(),8);
        if(state==='ready') {
          assert.ok((await page.locator('.pf-deltas').textContent()).includes('+ R$ 10,00'));
          assert.ok((await page.locator('.pf-deltas').textContent()).includes('-20,00 p.p.'));
          if(width===390)assert.ok(await page.locator('.pf-table').first().evaluate(el=>el.scrollWidth>el.clientWidth));
          await page.screenshot({path:`visual-qa/profitability-comparison-${width}.png`,fullPage:true});
        }
      }
    }
    for(const state of ['blank','ready','error']) {
      for(const width of [1440,390,320]) {
        await page.setViewportSize({width,height:900});
        await page.setContent(fs.readFileSync(`visual-qa/profitability-scenario-${state}.html`,'utf8'));
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Scenario ${state} overflow ${width}`);
        assert.equal(await page.locator('input[name=price]').count(),1);
        assert.ok((await page.locator('.scenario-tiers tbody td').evaluateAll(els=>els.map(el=>getComputedStyle(el).backgroundColor))).every(color=>color==='rgb(16, 34, 56)'));
        assert.equal(await page.locator('input[name=_csrf]').count(),1);
        assert.equal(await page.locator('input[name=assumptions]').isChecked(),state!=='blank');
        assert.equal(await page.locator('#discount-results').count(),state==='ready'?1:0);
        if(state==='ready') {
          assert.ok((await page.locator('#discount-results').textContent()).includes('R$ 89,50'));
          assert.ok((await page.locator('.scenario-target').textContent()).includes('R$ 18,50'));
          assert.ok((await page.locator('.scenario-target').textContent()).includes('abaixo da meta'));
          assert.equal(await page.locator('form').evaluate(form=>form.checkValidity()),true);
          await page.screenshot({path:`visual-qa/discount-scenarios-${width}.png`,fullPage:true});
        }
        if(state==='blank')assert.equal(await page.locator('form').evaluate(form=>form.checkValidity()),false);
        if(state==='error')assert.equal(await page.getByRole('alert').count(),1);
      }
    }
    assert.deepEqual(errors,[]);
    console.log('Profitability: desktop/mobile, unknown/stale values, form confirmation and layout passed.');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1});
