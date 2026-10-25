const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  for(const mode of ['ready','partial','empty','page2','variations']){
   for(const width of [1440,390,320]){
    await page.setViewportSize({width,height:900});
    await page.setContent(fs.readFileSync(`visual-qa/full-report-${mode}.html`,'utf8'));
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    assert.equal(await page.locator('.full-report').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(16, 34, 56)');
    assert.equal(await page.locator('.full-summary article').count(),4);
    assert.equal(await page.locator('.full-days-scroll tbody tr').count(),mode==='page2'?10:20);
    assert.ok((await page.locator('.full-summary').textContent()).includes('30/30'));
    if(!await page.locator('.full-variations').evaluate(el=>el.open)){
     await page.locator('.full-variations summary').focus();await page.keyboard.press('Enter');
    }
    const variations=page.locator('.full-variations tbody tr');
    assert.equal(await variations.count(),mode==='empty'?0:mode==='variations'?20:2);
    if(mode==='ready')assert.equal(await variations.first().locator('td').nth(1).textContent(),'0');
    if(mode==='partial')assert.equal(await variations.last().locator('td').nth(1).textContent(),'Indisponível');
    if(mode==='variations')assert.ok((await page.locator('.full-variations nav').textContent()).includes('Página 2 de 3'));
    if(!await page.locator('.full-reads').evaluate(el=>el.open)){
     await page.locator('.full-reads summary').focus();await page.keyboard.press('Enter');
    }
    assert.equal(await page.locator('.full-reads tbody tr').count(),mode==='empty'?0:mode==='page2'?10:30);
    await page.locator('.full-chart-scroll').focus();assert.equal(await page.locator(':focus').getAttribute('role'),'region');
    if(width<700){
     for(const selector of ['.full-days-scroll','.full-chart-scroll'])assert.ok(await page.locator(selector).evaluate(el=>el.scrollWidth>el.clientWidth));
    }
    assert.ok((await page.locator('.full-report th,.full-report td').evaluateAll(els=>els.map(el=>getComputedStyle(el).backgroundColor))).every(color=>color==='rgb(24, 46, 73)'));
    await page.screenshot({path:`visual-qa/full-report-${mode}-${width}.png`,fullPage:true});
   }
  }
  for(const mode of ['ready','gap','switched','shared','page2','limited']){
   for(const width of [1440,390,320]){
    await page.setViewportSize({width,height:900});
    await page.setContent(fs.readFileSync(`visual-qa/full-variation-history-${mode}.html`,'utf8'));
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    const panel=page.locator('.full-variation-history');
    assert.equal(await panel.locator('input[name=full_variacao]').inputValue(),'1');
    assert.equal(await panel.locator('form').getAttribute('action'),'/full/1#full-historico-variacao');
    assert.equal(await panel.locator('tbody tr').count(),['page2','limited'].includes(mode)?20:3);
    const cells=panel.locator('tbody tr').first().locator('td');
    if(mode==='ready')assert.equal(await cells.nth(2).textContent(),'+3 unidades');
    if(['gap','switched'].includes(mode))assert.equal(await cells.nth(2).textContent(),'Sem par consecutivo comparável');
    if(mode==='shared')assert.equal(await cells.nth(1).textContent(),'Indisponível');
    if(mode==='limited')assert.ok((await panel.textContent()).includes('Recorte limitado às 500'));
    if(mode==='page2')assert.ok((await panel.locator('nav').textContent()).includes('Página 2 de 3'));
    await panel.locator('summary').focus();await page.keyboard.press('Enter');
    assert.ok(!await panel.locator('table').isVisible());await page.keyboard.press('Enter');
    await panel.locator('.full-variation-history-scroll').focus();assert.equal(await page.locator(':focus').getAttribute('role'),'region');
    if(width<700)assert.ok(await panel.locator('.full-variation-history-scroll').evaluate(el=>el.scrollWidth>el.clientWidth));
    await page.screenshot({path:`visual-qa/full-variation-history-${mode}-${width}.png`,fullPage:true});
   }
  }
  assert.deepEqual(errors,[]);console.log('Full stock, variant evidence, coverage and pagination checks passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
