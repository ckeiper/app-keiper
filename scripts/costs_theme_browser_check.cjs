const fs=require('node:fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch();try{const page=await browser.newPage();for(const mode of ['ready','empty'])for(const width of [1440,390,320]){
 await page.setViewportSize({width,height:900});await page.setContent(fs.readFileSync(`visual-qa/costs-theme-${mode}.html`,'utf8'));
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await page.locator('body').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(8, 20, 38)');
 assert.equal(await page.locator('.conteudo .stat .num').first().evaluate(e=>getComputedStyle(e).color),'rgb(237, 245, 255)');
 assert.equal(await page.locator('input[name=arquivo]').getAttribute('accept'),'.xlsx');
 if(mode==='ready')assert.equal(await page.locator('.conteudo table th').first().evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(27, 52, 78)');
 await page.screenshot({path:`visual-qa/costs-theme-${mode}-${width}.png`,fullPage:true});
}console.log('Costs theme, inputs, empty state and responsive layout passed.');}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
