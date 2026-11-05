const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true});try{const p=await b.newPage();
for(const mode of ['paused','active','stale','tasks','history','official','unknown','empty','error','moderation','moderation-empty','moderation-error','moderation-partial'])for(const width of [1440,390,320])for(const theme of ['dark','light']){
 await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/listing-reactivation-${mode}.html`,'utf8'));
 await p.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
 assert.equal(await p.locator('.rr-official button[value=consultar_motivos]').textContent(),'Consultar motivos atuais');
 if(mode==='official'){assert.ok((await p.locator('.rr-official').textContent()).includes('Falta de estoque'));assert.equal(await p.locator('.rr-official script').count(),0);}
 assert.equal(await p.locator('.rr-official button[value=consultar_moderacao]').textContent(),'Consultar motivos e moderação');
 if(mode==='moderation'){assert.ok((await p.locator('.rr-moderation').textContent()).includes('Confira o preço.'));assert.equal(await p.locator('.rr-moderation script').count(),0);}
 if(mode==='moderation-error')assert.ok((await p.locator('.rr-moderation').textContent()).includes('Moderação não verificada'));
 if(mode==='moderation-empty')assert.ok((await p.locator('.rr-moderation').textContent()).includes('Nenhuma moderação retornada'));
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await p.locator('.rr-task').count(),mode==='tasks'?10:0);
 assert.equal(await p.locator('.rr-event').count(),mode==='history'?1:0);
 await p.locator('.reactivation summary').click();const f=p.locator('.reactivation details form');assert.equal(await f.evaluate(e=>e.checkValidity()),false);
 await f.locator('[name=responsible]').fill('Equipe');await f.locator('[name=due_date]').fill('2026-10-26');await f.locator('textarea').fill('Conferir o motivo e a disponibilidade antes de decidir.');assert.equal(await f.evaluate(e=>e.checkValidity()),true);
 assert.equal(await f.locator('[name=_csrf]').count(),1);
 await p.screenshot({path:`visual-qa/listing-reactivation-${mode}-${width}-${theme}.png`,fullPage:true});
}console.log('Reactivation review forms, observed status and mobile checks passed.');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
