const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();try{const p=await b.newPage();for(const mode of ['account','item','description','category','conditional','sheet','normal'])for(const theme of ['dark','light'])for(const width of [1440,390,320]){
 await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/content-rate-${mode}.html`,'utf8'));await p.evaluate(t=>document.documentElement.dataset.theme=t,theme);
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await p.locator('.content-snapshot form').count(),1);
 const partial=['description','category','conditional','sheet'].includes(mode);
 assert.equal(await p.locator('.cs-rate-limit').count(),partial?1:0);
 assert.equal(await p.locator('.content-snapshot .pf-metric').count(),['account','item'].includes(mode)?0:3);
 if(partial){assert.ok((await p.locator('.cs-rate-limit').textContent()).includes('dados já obtidos foram preservados'));assert.ok((await p.locator('.cs-technical').textContent()).includes('Limite de consultas'));}
 if(['account','item'].includes(mode))assert.ok((await p.locator('#content-snapshot-result').textContent()).includes('Sem leitura verificável'));
 if(mode==='description'){assert.ok((await p.locator('#content-snapshot-result').textContent()).includes('Descrição não verificada'));assert.equal(await p.locator('.cs-requirement').count(),0);}
 if(mode==='conditional')assert.ok((await p.locator('.cs-required').textContent()).includes('aplicabilidade não avaliada'));
 if(width===390&&['description','conditional','normal'].includes(mode))await p.screenshot({path:`visual-qa/content-rate-${mode}-${theme}-${width}.png`,fullPage:true});
}console.log('42 content rate-limit boundary/theme/viewport cases passed, preserving prior evidence.');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
