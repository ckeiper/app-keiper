const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();try{const p=await b.newPage();for(const mode of ['matched','review','unknown','variation','managed','category-failure','compound'])for(const theme of ['dark','light'])for(const width of [1440,390,320]){
 await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/content-number-${mode}.html`,'utf8'));await p.evaluate(t=>document.documentElement.dataset.theme=t,theme);
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.equal(await p.locator('.content-snapshot form').count(),1);assert.ok(await p.locator('.cs-actions').isVisible());
 if(mode==='matched')assert.ok(await p.locator('[data-number-state=matched]').isVisible());
 if(['review','variation','managed'].includes(mode))assert.ok(await p.locator('[data-number-state=review]').isVisible());
 if(['unknown','compound'].includes(mode))assert.ok(await p.locator('[data-number-state=unknown]').isVisible());
 if(mode==='category-failure')assert.equal(await p.locator('.cs-number-row').count(),0);
 if(mode==='managed')assert.ok((await p.locator('.cs-number-values').innerText()).includes('sem recomendar edição direta'));
 if(width===390&&['matched','review','unknown','variation'].includes(mode)){
  await p.locator('.cs-number-values').screenshot({path:`visual-qa/content-number-${mode}-${theme}-${width}.png`});
 }
}console.log('Numeric text: 42 responsive theme cases passed, including unknowns, variations and managed fields.');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
