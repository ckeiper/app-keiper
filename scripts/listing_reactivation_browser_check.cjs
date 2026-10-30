const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true});try{const p=await b.newPage();
for(const mode of ['paused','active','stale','tasks','history'])for(const width of [1440,390,320]){
 await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/listing-reactivation-${mode}.html`,'utf8'));
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await p.locator('.rr-task').count(),mode==='tasks'?10:0);
 assert.equal(await p.locator('.rr-event').count(),mode==='history'?1:0);
 await p.locator('.reactivation summary').click();const f=p.locator('.reactivation form');assert.equal(await f.evaluate(e=>e.checkValidity()),false);
 await f.locator('[name=responsible]').fill('Equipe');await f.locator('[name=due_date]').fill('2026-10-26');await f.locator('textarea').fill('Conferir o motivo e a disponibilidade antes de decidir.');assert.equal(await f.evaluate(e=>e.checkValidity()),true);
 assert.equal(await f.locator('[name=_csrf]').count(),1);
 await p.screenshot({path:`visual-qa/listing-reactivation-${mode}-${width}.png`,fullPage:true});
}console.log('Reactivation review forms, observed status and mobile checks passed.');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
