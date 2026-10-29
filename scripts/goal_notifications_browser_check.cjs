const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();try{const p=await b.newPage();for(const mode of ['off','active','unconfigured','changed','cancelled','uncertain'])for(const theme of ['dark','light'])for(const width of [1440,390,320]){
 await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/goal-notifications-${mode}.html`,'utf8'));await p.evaluate(t=>document.documentElement.dataset.theme=t,theme);
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${mode} ${theme} ${width}`);
 const box=p.locator('.goal-notifications [type=checkbox]');assert.equal(await box.isChecked(),['active','cancelled','uncertain'].includes(mode));
 assert.equal(await box.isDisabled(),mode==='cancelled');assert.equal(await p.locator('.goal-notifications [name=_csrf]').count(),1);
 if(mode==='off'){await box.check();assert.equal(await box.isChecked(),true);await box.uncheck();}
 if(mode==='uncertain')assert.ok(await p.locator('article').getByText('Resultado incerto · sem repetição automática').isVisible());
}console.log('Goal notification consent, states and responsive themes passed (36 cases).');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
