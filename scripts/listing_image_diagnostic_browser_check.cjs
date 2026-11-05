const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();try{const p=await b.newPage();for(const mode of ['initial','findings','empty','catalog','unknown','rate-limit','wrong-role','selection','secondary','variation'])for(const theme of ['dark','light'])for(const width of [1440,390,320]){
 await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/image-diagnostic-${mode}.html`,'utf8'));await p.addStyleTag({content:'*,*::before,*::after{transition:none!important;animation:none!important}'});await p.evaluate(t=>document.documentElement.dataset.theme=t,theme);
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await p.locator('.k-refresh').count(),0);assert.equal(await p.locator('.image-diagnostic form').count(),mode==='selection'?2:1);
 assert.equal(await p.locator('.image-diagnostic form').first().getAttribute('method'),'post');
 assert.equal(await p.locator('.image-diagnostic input[name=_csrf]').first().getAttribute('value'),'csrf-test');
 assert.equal(await p.locator('.image-diagnostic img').count(),0);assert.equal(await p.locator('.image-diagnostic script').count(),0);
 if(mode==='selection'){assert.equal(await p.locator('.id-selection option').count(),3);await p.locator('.id-selection select').selectOption('P2');assert.equal(await p.locator('.id-selection select').inputValue(),'P2');assert.ok(await p.locator('.id-selection form').evaluate(f=>f.checkValidity()));}
 if(mode==='secondary')assert.ok((await p.locator('.id-source').textContent()).includes('Secundária'));
 if(mode==='variation')assert.ok((await p.locator('.id-source').textContent()).includes('Principal de variação'));
 if(mode==='initial')assert.equal(await p.locator('#image-diagnostic-result').count(),0);
 if(['findings','catalog'].includes(mode))assert.equal(await p.locator('.id-finding').count(),1);
 if(mode==='catalog')assert.ok((await p.locator('#image-diagnostic-result').textContent()).includes('Publicação de catálogo'));
 if(mode==='empty')assert.ok((await p.locator('.id-empty').textContent()).includes('Isso não aprova'));
 if(['unknown','rate-limit','wrong-role','selection','secondary','variation'].includes(mode)){assert.equal(await p.locator('.id-empty').count(),0);assert.ok((await p.locator('#image-diagnostic-result [role=status]').textContent()).includes('Sem diagnóstico verificável'));}
 if(theme==='light')assert.equal(await p.locator('.top .sair').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(34, 95, 190)');
 if(theme==='light')assert.ok(await p.locator('.image-diagnostic .pf-hero').evaluate(e=>{
  const rgb=s=>(s.match(/[\d.]+/g)||[]).slice(0,3).map(Number),lum=c=>c.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);
  const bg=lum(rgb(getComputedStyle(e).backgroundColor)),fg=lum(rgb(getComputedStyle(e.querySelector('h2')).color));return (Math.max(bg,fg)+.05)/(Math.min(bg,fg)+.05)>=4.5;
 }));
 if(width===390)await p.screenshot({path:`visual-qa/image-diagnostic-${mode}-${theme}-${width}.png`,fullPage:true});
}console.log('60 official image diagnostic scope/theme/viewport cases passed.');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
