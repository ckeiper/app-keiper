const fs=require('node:fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch();try{const page=await browser.newPage();for(const width of [1440,390,320]){
 await page.setViewportSize({width,height:900});await page.setContent(fs.readFileSync('visual-qa/sales-theme.html','utf8'));
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await page.locator('body').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(8, 20, 38)');
 assert.equal(await page.locator('.conteudo .stat .num').first().evaluate(e=>getComputedStyle(e).color),'rgb(237, 245, 255)');
 assert.equal(await page.locator('.conteudo table th').first().evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(27, 52, 78)');
 assert.equal(await page.locator('select[name=periodo]').count(),1);
 await page.screenshot({path:`visual-qa/sales-theme-${width}.png`,fullPage:true});
}console.log('Sales theme: contrast and responsive layouts passed.');}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
