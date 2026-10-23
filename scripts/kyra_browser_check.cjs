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
 await page.getByRole('heading',{name:'KYRA',exact:true}).waitFor();
 assert.equal(await page.locator('.ky-chart-pick').count(),3);
 await page.locator('[data-series-toggle=spend]').click();assert.equal(await page.locator('[data-series=spend]').isVisible(),false);
 await page.locator('[data-series-toggle=spend]').click();assert.equal(await page.locator('[data-series=spend]').isVisible(),true);
 await page.locator('.ky-plot').scrollIntoViewIfNeeded();
 await page.waitForFunction(()=>document.querySelector('.ky-plot').classList.contains('ky-visible'));
 await page.locator('.ky-hit').first().focus();await page.locator('.ky-chart-tip').waitFor({state:'visible'});
 assert.ok((await page.locator('.ky-chart-tip').innerText()).includes('Receita Ads'));
 await page.locator('[data-ky-filter=quality]').click();assert.equal(await page.locator('.ky-finding:visible').count(),0);await page.locator('[data-filter-empty]').waitFor({state:'visible'});
 await page.locator('[data-ky-filter=all]').click();assert.equal(await page.locator('.ky-finding:visible').count(),3);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Overflow at '+width);
 await page.locator('body').press('Control+Home');
 await page.waitForFunction(()=>document.getAnimations().filter(a=>a.effect.getTiming().iterations!==Infinity).every(a=>a.playState==='finished'));
 await page.screenshot({path:'visual-qa/kyra-'+width+'.png',fullPage:true});
}
for(const kind of ['empty','quality','clean']){await page.goto(base+'/'+kind);assert.ok(await page.locator('.kyra').isVisible());assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
await page.emulateMedia({reducedMotion:'reduce'});await page.goto(base);assert.equal(await page.locator('.ky-line').first().evaluate(el=>getComputedStyle(el).animationName),'none');
assert.deepEqual(errors,[]);console.log('KYRA: responsive layouts, series cards, keyboard tooltips, first-view animation, filters, missing data and reduced motion passed.');
}finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);process.exitCode=1});
