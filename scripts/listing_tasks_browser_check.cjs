const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({locale:'pt-BR'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  for(const mode of ['open','empty','history','error','page2']){
   for(const width of [1440,390,320]){
    await page.setViewportSize({width,height:900});
    await page.setContent(fs.readFileSync(`visual-qa/listing-tasks-${mode}.html`,'utf8'));
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    assert.equal(await page.locator('.listing-tasks').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(16, 34, 56)');
    assert.equal(await page.locator('.lt-cards article').count(),4);
    assert.equal(await page.locator('.lt-cards a[href*=overdue]').count(),1);
    assert.equal(await page.locator('.listing-tasks>div.lt-scroll tbody tr').count(),mode==='empty'?0:mode==='page2'?5:10);
    for(const form of await page.locator('form[method=post]').all())assert.equal(await form.locator('input[name=_csrf]').count(),1);
    if(!await page.locator('.lt-create').evaluate(el=>el.open)){
     await page.locator('.lt-create summary').focus();await page.keyboard.press('Enter');
    }
    await page.locator('.lt-form input[name=title]').fill('Revisar estoque Full');
    await page.locator('.lt-form input[name=responsible]').fill('Equipe responsável');
    await page.locator('.lt-form input[name=due_date]').fill('2026-10-25');
    assert.ok(await page.locator('.lt-form').evaluate(el=>el.checkValidity()));
    assert.equal(await page.locator('.lt-form textarea').getAttribute('maxlength'),'1500');
    if(mode==='history'){
     assert.equal(await page.locator('.lt-history tbody tr').count(),2);
     assert.ok((await page.locator('.lt-history').textContent()).includes('Aberta → Concluída'));
    }
    if(mode==='error')assert.ok(await page.locator('.lt-notice').isVisible());
    if(mode!=='empty'){
     await page.locator('.listing-tasks>div.lt-scroll').focus();assert.equal(await page.locator(':focus').getAttribute('role'),'region');
     if(width<700)assert.ok(await page.locator('.listing-tasks>div.lt-scroll').evaluate(el=>el.scrollWidth>el.clientWidth));
    }
    assert.ok((await page.locator('.listing-tasks th,.listing-tasks td').evaluateAll(els=>els.map(el=>getComputedStyle(el).backgroundColor))).every(color=>color==='rgb(24, 46, 73)'));
    await page.screenshot({path:`visual-qa/listing-tasks-${mode}-${width}.png`,fullPage:true});
   }
  }
  assert.deepEqual(errors,[]);console.log('Listing tasks forms, history, filters and mobile layout passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
