const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();try{const p=await b.newPage();for(const mode of ['read','partial','unknown','empty','managed','variations'])for(const theme of ['dark','light'])for(const width of [1440,390,320]){
 await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/content-technical-${mode}.html`,'utf8'));await p.evaluate(t=>document.documentElement.dataset.theme=t,theme);
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.equal(await p.locator('[name=ficha_tecnica][value="1"]').count(),1);assert.equal(await p.locator('.content-snapshot form').count(),1);
 if(mode==='read'){assert.equal(await p.locator('.cs-tech-row').count(),3);assert.ok((await p.locator('.cs-technical').textContent()).includes('não confirma impedimento'));}
 if(mode==='unknown')assert.equal(await p.locator('.cs-tech-row').count(),0);
 if(mode==='partial')assert.equal(await p.locator('.cs-tech-row[data-presence=unknown]').count(),3);
 if(mode==='variations'){const details=p.locator('.cs-tech-row details').first();await details.locator('summary').click();assert.ok((await details.textContent()).includes('Variação 2: Sem valor identificado'));}
}console.log('Technical sheet diagnostics: 36 responsive theme cases passed.');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
