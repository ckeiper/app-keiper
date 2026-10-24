const fs=require('node:fs'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
const server=http.createServer((req,res)=>{const kind=['empty','quality','clean'].find(k=>req.url.includes(k))||'ready';res.setHeader('Content-Type','text/html; charset=utf-8');res.end(fs.readFileSync('visual-qa/kyra-'+kind+'.html'))});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let browser;
try{
browser=await chromium.launch(process.env.PLAYWRIGHT_EXECUTABLE_PATH?{executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH}:{});
const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
const base='http://127.0.0.1:'+server.address().port;
for(const width of [1440,820,390,320]){
 await page.setViewportSize({width,height:1000});await page.goto(base);
 await page.getByRole('heading',{name:'KEVIA',exact:true}).waitFor();
 assert.ok(await page.locator('.ky-wordmark').evaluate(el=>parseFloat(getComputedStyle(el).fontSize)>=56),'Wordmark must keep its size in the store shell');
 assert.equal(await page.locator('.ky-wordmark').evaluate(el=>getComputedStyle(el).color),'rgb(246, 240, 255)');
 await page.waitForFunction(()=>document.querySelector('.kyra').dataset.kyraReady==='true');
 assert.equal(await page.locator('.ky-chart-pick').count(),3);
 assert.equal(await page.locator('.ky-campaign-card').count(),3);
 assert.equal(await page.locator('.ky-sale-efficiency').count(),3);
 assert.equal(await page.locator('.ky-sale-efficiency th').first().evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(27, 43, 68)');
 assert.ok((await page.locator('.ky-sale-efficiency').first().innerText()).includes('Não é custo de aquisição'));
 assert.equal(await page.locator('.ky-sale-efficiency table tbody tr').count(),6);
 assert.ok((await page.locator('.ky-campaign-card').first().innerText()).includes('Investigar gasto sem receita atribuída'));
 assert.equal(await page.locator('.ky-campaign-card a').first().getAttribute('href'),'/ads/1/campanha/waste');

 await page.locator('[data-series-toggle=spend]').click();await page.waitForFunction(()=>getComputedStyle(document.querySelector('[data-series=spend]')).display==='none');assert.equal(await page.locator('[data-series-toggle=spend]').getAttribute('aria-pressed'),'false');
 await page.locator('[data-series-toggle=spend]').click();await page.waitForFunction(()=>getComputedStyle(document.querySelector('[data-series=spend]')).display!=='none');assert.equal(await page.locator('[data-series-toggle=spend]').getAttribute('aria-pressed'),'true');
 await page.locator('.ky-plot').first().scrollIntoViewIfNeeded();
 await page.waitForFunction(()=>document.querySelector('.ky-plot').classList.contains('ky-visible'));
 await page.locator('.ky-hit').first().focus();await page.locator('.ky-chart-tip').waitFor({state:'visible'});
 assert.ok((await page.locator('.ky-chart-tip').innerText()).includes('Receita Ads'));
 await page.locator('[data-ky-filter=quality]').click();assert.equal(await page.locator('.ky-finding:visible').count(),0);await page.locator('[data-filter-empty]').waitFor({state:'visible'});
 await page.locator('[data-ky-filter=all]').click();assert.equal(await page.locator('.ky-finding:visible').count(),3);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Overflow at '+width);
 if(width===1440){
  await page.locator('.ky-camp-bars').first().scrollIntoViewIfNeeded();
  await page.waitForFunction(()=>document.querySelector('.ky-camp-bars').classList.contains('ky-visible'));
  await page.waitForFunction(()=>document.getAnimations().filter(a=>a.effect.getTiming().iterations!==Infinity).every(a=>a.playState==='finished'));
  await page.locator('.ky-campaign-card').first().screenshot({path:'visual-qa/kyra-campaign-detail.png'});
 }
 await page.locator('body').press('Control+Home');
 await page.waitForFunction(()=>document.getAnimations().filter(a=>a.effect.getTiming().iterations!==Infinity).every(a=>a.playState==='finished'));
 await page.screenshot({path:'visual-qa/kyra-'+width+'.png',fullPage:true});
}
for(const kind of ['empty','quality','clean']){await page.goto(base+'/'+kind);assert.ok(await page.locator('.kyra').isVisible());assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
await page.emulateMedia({reducedMotion:'reduce'});await page.goto(base);assert.equal(await page.locator('.ky-line').first().evaluate(el=>getComputedStyle(el).animationName),'none');
assert.deepEqual(errors,[]);console.log('KYRA: responsive layouts, series cards, keyboard tooltips, first-view animation, filters, missing data and reduced motion passed.');
}finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);process.exitCode=1});
