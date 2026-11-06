const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{const page=await browser.newPage();
for(const mode of ['ready','zero','partial','pending','invalid','spike','change','zero-base'])for(const theme of ['dark','light'])for(const width of [1440,390,320]){
 await page.setViewportSize({width,height:900});await page.setContent(fs.readFileSync(`visual-qa/listing-weekly-pattern-${mode}.html`,'utf8'));
 await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await page.locator('.wp progress').getAttribute('value'),mode==='partial'?'46':'56');
 assert.equal(await page.locator('.wp form').count(),0);
 assert.equal(await page.getByRole('link',{name:'Conferir a média no histórico'}).getAttribute('href'),'/anuncios/7/MLB1/conferencia-media');
 const ready=['ready','zero','spike','change','zero-base'].includes(mode);
 assert.equal(await page.locator('.wp-distribution tbody tr').count(),ready?7:0);
 assert.equal(await page.locator('.wp-bar-row').count(),ready?7:0);
 const comparisonLink=page.getByRole('link',{name:'Comparar períodos de quatro semanas'});assert.equal(await comparisonLink.count(),ready?1:0);if(ready)assert.equal(await comparisonLink.getAttribute('href'),'#wp-comparacao');
 assert.equal(await page.locator('.wp-comparison-table tbody tr').count(),ready?7:0);assert.equal(await page.locator('.wp-cmp-series').count(),ready?14:0);
 if(mode==='change'){assert.equal(await page.locator('.wp-comparison-table tbody tr').first().locator('td').nth(3).textContent(),'+100,0%');assert.equal(await page.locator('.wp-comparison-table tbody tr').last().locator('td').nth(3).textContent(),'-100,0%');}
 if(mode==='zero-base')assert.ok((await page.locator('.wp-comparison-table tbody tr').first().textContent()).includes('base zero'));
 if(!ready)assert.ok((await page.locator('.wp [role=status]').textContent()).includes('Análise indisponível'));
 if(mode==='zero')assert.ok((await page.locator('.wp-notice').textContent()).includes('Participação não calculada'));
 if(mode==='ready')assert.equal(await page.locator('.wp-bar-row strong').first().textContent(),'1,0');
 if(mode==='spike')assert.equal(await page.locator('.wp tbody tr').first().locator('td').nth(2).textContent(),'1,0'); // median resists spike
 if(theme==='light'){
  assert.equal(await page.locator('.wp').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(255, 255, 255)');
  if(ready)assert.equal(await page.locator('.wp-stats article').first().evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(242, 246, 251)');
 }else{
  assert.equal(await page.locator('.wp').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(16, 34, 56)');
  assert.equal(await page.locator('.wp h2').evaluate(e=>getComputedStyle(e).color),'rgb(234, 242, 255)');
  if(ready){
   assert.equal(await page.locator('.wp td').first().evaluate(e=>getComputedStyle(e).color),'rgb(234, 242, 255)');
   assert.equal(await page.locator('.wp thead th').first().evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(24, 46, 73)');
   await page.locator('.wp tbody tr').first().hover();
   assert.equal(await page.locator('.wp td').first().evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(28, 53, 79)');
  }
 }
 await page.locator('.wp summary').click();
 assert.equal(await page.locator('.wp-days span').count(),56);
 if(ready && width<650){
  for(const wrap of await page.locator('.wp-table-wrap').all()){assert.ok(await wrap.evaluate(e=>e.scrollWidth>e.clientWidth));await wrap.focus();assert.ok(await wrap.evaluate(e=>document.activeElement===e));}
 }
 await page.screenshot({path:`visual-qa/listing-weekly-pattern-${mode}-${theme}-${width}.png`,fullPage:true});
}console.log('48 weekly pattern states/themes/viewports passed.');}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
