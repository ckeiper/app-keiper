const fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});const page=await browser.newPage();
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 try {
  for(const width of [1440,390,320]) {
   for(const kind of ['ready','partial','missing','failed','pending','client']) {
    await page.setViewportSize({width,height:950});
    await page.emulateMedia({reducedMotion:'reduce'});
    await page.setContent(fs.readFileSync(`visual-qa/kevia-finance-${kind}.html`,'utf8'));
    assert.equal(await page.getByRole('heading',{name:'KEVIA',exact:true}).count(),1);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${kind} overflow at ${width}`);
    assert.equal(await page.locator('#ky-finance').count(),kind==='client'?0:1);
    assert.equal(await page.locator('a[href="#ky-finance"]').count(),kind==='client'?0:1);
    if(kind==='client') {
     assert.ok(!(await page.locator('body').textContent()).includes('R$ -80,00'));
     assert.equal(await page.locator('.ky-finance-finding').count(),0);continue;
    }
    assert.equal(await page.locator('#ky-finance h2').evaluate(el=>getComputedStyle(el).color),'rgb(232, 238, 251)');
    const ready=['ready','partial'].includes(kind);
    assert.equal(await page.locator('.ky-finance-stat').count(),ready?3:0);
    assert.equal(await page.locator('.ky-finance-finding').count(),ready?1:0);
    if(ready) {
     const text=await page.locator('#ky-finance').textContent();
     assert.ok(text.includes('R$ -80,00'));
     assert.ok(text.includes('alterações posteriores não estão incluídas'));
     assert.ok(text.includes(kind==='partial'?'1 de 2':'1 de 1'));
     assert.ok(text.includes('não é o resultado total da loja'));
     const link=page.locator('.ky-finance-finding a').first();
     assert.equal(await link.getAttribute('href'),'/anuncios/42/MLB100/rentabilidade?inicio=2026-10-17&fim=2026-10-23');
     await link.focus();assert.equal(await page.locator(':focus').getAttribute('href'),await link.getAttribute('href'));
    }
    if(kind==='ready') {
     await page.evaluate(()=>window.scrollTo(0,0));
     await page.screenshot({path:`visual-qa/kevia-finance-${width}.png`,fullPage:true});
    }
   }
  }
  assert.deepEqual(errors,[]);
  console.log('KEVIA finance: admin/client isolation, unknown/failed states, partial coverage, sources, keyboard and responsive layout passed.');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
