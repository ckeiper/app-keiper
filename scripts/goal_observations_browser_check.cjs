const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true});try{const p=await b.newPage();
for(const mode of ['empty','history','page2'])for(const width of [1440,390,320]){
 await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/goal-observations-${mode}.html`,'utf8'));
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await p.locator('.goal-history article').count(),mode==='empty'?0:mode==='page2'?3:10);
 assert.equal(await p.locator('.goal-history form').count(),0);
 assert.equal(await p.locator('.goal-history').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(16, 34, 56)');
 if(mode!=='empty')assert.ok((await p.locator('.goal-history').textContent()).includes('Não verificado'));
 await p.screenshot({path:`visual-qa/goal-observations-${mode}-${width}.png`,fullPage:true});
}console.log('Goal evaluation history, unknown values and pagination mobile checks passed.');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
