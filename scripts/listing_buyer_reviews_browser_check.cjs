const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{const page=await browser.newPage();
for(const mode of ['initial','ready','catalog','empty','unknown','incomplete','page2'])for(const theme of ['dark','light'])for(const width of [1440,390,320]){
 await page.setViewportSize({width,height:900});await page.setContent(fs.readFileSync(`visual-qa/buyer-reviews-${mode}.html`,'utf8'));
 await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await page.locator('.k-refresh').count(),0);
 assert.equal(await page.locator('.buyer-reviews form').first().getAttribute('method'),'post');
 assert.equal(await page.locator('.buyer-reviews input[name=_csrf]').first().getAttribute('value'),'csrf-test');
 assert.equal(await page.locator('.buyer-reviews img').count(),0);
 const read=!['initial','unknown'].includes(mode);
 assert.equal(await page.locator('.buyer-reviews .pf-metric').count(),read?3:0);
 if(mode==='catalog')assert.ok((await page.locator('.br-scope').textContent()).includes('outros vendedores'));
 if(mode==='unknown')assert.ok((await page.locator('[role=status]').textContent()).includes('Sem leitura verificável'));
 if(mode==='empty')assert.ok((await page.locator('#buyer-review-result').textContent()).includes('não comprova ausência'));
 if(mode==='incomplete')assert.ok((await page.locator('.pf-grid').textContent()).includes('Não verificado'));
 if(mode==='page2')assert.equal(await page.getByRole('button',{name:'Página anterior'}).count(),1);
 if(read){await page.locator('summary').first().click();assert.ok(await page.locator('.br-levels').isVisible());}
 await page.screenshot({path:`visual-qa/buyer-reviews-${mode}-${theme}-${width}.png`,fullPage:true});
}console.log('42 review states/themes/viewports passed; scope, forms, unknown states and pagination verified.');}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
