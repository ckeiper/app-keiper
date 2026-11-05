const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{const page=await browser.newPage();
for(const mode of ['ready','zero','partial','pending','invalid','spike'])for(const theme of ['dark','light'])for(const width of [1440,390,320]){
 await page.setViewportSize({width,height:900});await page.setContent(fs.readFileSync(`visual-qa/listing-weekly-pattern-${mode}.html`,'utf8'));
 await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await page.locator('.wp progress').getAttribute('value'),mode==='partial'?'46':'56');
 assert.equal(await page.locator('.wp form').count(),0);
 const ready=['ready','zero','spike'].includes(mode);
 assert.equal(await page.locator('.wp tbody tr').count(),ready?7:0);
 assert.equal(await page.locator('.wp-bar-row').count(),ready?7:0);
 if(!ready)assert.ok((await page.locator('.wp [role=status]').textContent()).includes('Análise indisponível'));
 if(mode==='zero')assert.ok((await page.locator('.wp-notice').textContent()).includes('Participação não calculada'));
 if(mode==='ready')assert.equal(await page.locator('.wp-bar-row strong').first().textContent(),'1,0');
 if(mode==='spike')assert.equal(await page.locator('.wp tbody tr').first().locator('td').nth(2).textContent(),'1,0'); // median resists spike
 if(theme==='light'){
  assert.equal(await page.locator('.wp').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(255, 255, 255)');
  if(ready)assert.equal(await page.locator('.wp-stats article').first().evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(242, 246, 251)');
 }else assert.equal(await page.locator('.wp').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(16, 34, 56)');
 await page.locator('.wp summary').click();
 assert.equal(await page.locator('.wp-days span').count(),56);
 if(ready && width<650){
  const wrap=page.locator('.wp-table-wrap');assert.ok(await wrap.evaluate(e=>e.scrollWidth>e.clientWidth));
  await wrap.focus();assert.ok(await wrap.evaluate(e=>document.activeElement===e));
 }
 await page.screenshot({path:`visual-qa/listing-weekly-pattern-${mode}-${theme}-${width}.png`,fullPage:true});
}console.log('36 weekly pattern states/themes/viewports passed.');}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
