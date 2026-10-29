const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();try{const p=await b.newPage();for(const mode of ['matched','review','unknown','variation','managed','category-failure'])for(const theme of ['dark','light'])for(const width of [1440,390,320]){
 await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/content-boolean-${mode}.html`,'utf8'));await p.evaluate(t=>document.documentElement.dataset.theme=t,theme);
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.equal(await p.locator('.content-snapshot form').count(),1);
 if(mode==='matched')assert.ok(await p.locator('[data-value-state=matched]').isVisible());
 if(['review','variation','managed'].includes(mode))assert.ok(await p.locator('[data-value-state=review]').isVisible());
 if(mode==='unknown')assert.ok(await p.locator('[data-value-state=unknown]').isVisible());
 if(mode==='category-failure')assert.equal(await p.locator('.cs-bool-row').count(),0);
}console.log('Boolean attributes: 36 responsive theme cases passed.');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
