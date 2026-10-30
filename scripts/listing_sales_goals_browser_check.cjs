const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();try{const p=await b.newPage();
for(const mode of ['empty','unknown','alert','met','progress','cancelled'])for(const theme of ['dark','light'])for(const width of [1440,390,320]){
 await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/listing-sales-goals-${mode}.html`,'utf8'));
 await p.evaluate(t=>document.documentElement.dataset.theme=t,theme);
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${mode} ${theme} ${width}`);
 await p.locator('.sales-goals summary').click();const f=p.locator('.sales-goals details form');
 assert.equal(await f.locator('select option').count(),3);assert.equal(await f.evaluate(e=>e.checkValidity()),false);
 await f.locator('[name=target]').fill('10');await f.locator('[name=start_date]').fill('2026-10-20');await f.locator('[name=end_date]').fill('2026-10-28');await f.locator('[name=responsible]').fill('Equipe');assert.equal(await f.evaluate(e=>e.checkValidity()),true);
 if(mode==='unknown')assert.equal(await p.locator('text=Apurado:').count(),0);
 if(mode==='cancelled')assert.equal(await p.locator('.sales-goals article form').count(),0);
 if(mode==='alert')assert.ok(await p.locator('.goal-alert').isVisible());
}console.log('Sales goal forms, states and responsive themes passed (36 cases).');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
