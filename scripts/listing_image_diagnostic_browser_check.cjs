const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();try{const p=await b.newPage();await p.route('https://http2.mlstatic.com/**',r=>r.request().url().includes('missing.jpg')?r.abort('failed'):r.fulfill({status:200,contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="240" height="180"><rect width="240" height="180" fill="white"/><circle cx="120" cy="90" r="55" fill="navy"/></svg>'}));for(const mode of ['initial','findings','empty','catalog','unknown','rate-limit','wrong-role','selection','secondary','variation','gallery-missing','gallery-broken'])for(const theme of ['dark','light'])for(const width of [1440,390,320]){
 await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/image-diagnostic-${mode}.html`,'utf8'));await p.addStyleTag({content:'*,*::before,*::after{transition:none!important;animation:none!important}'});await p.evaluate(t=>document.documentElement.dataset.theme=t,theme);
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await p.locator('.k-refresh').count(),0);assert.equal(await p.locator('.image-diagnostic form').count(),['selection','gallery-missing','gallery-broken'].includes(mode)?2:1);
 assert.equal(await p.locator('.image-diagnostic form').first().getAttribute('method'),'post');
 assert.equal(await p.locator('.image-diagnostic input[name=_csrf]').first().getAttribute('value'),'csrf-test');
 assert.equal(await p.locator('.image-diagnostic img').count(),mode==='selection'?2:mode==='gallery-broken'?1:0);assert.equal(await p.locator('.image-diagnostic script').count(),0);
 if(['selection','gallery-missing','gallery-broken'].includes(mode)){const radios=p.locator('.id-photo-card input');assert.equal(await radios.count(),3);assert.ok(await radios.nth(0).isVisible());assert.equal(await p.locator('.id-selection form').evaluate(f=>f.checkValidity()),false);await p.locator('.id-photo-card').nth(2).click();assert.equal(await p.locator('input[name=selected_picture]:checked').inputValue(),'P2');assert.ok(await p.locator('.id-selection form').evaluate(f=>f.checkValidity()));assert.equal(await p.locator('.id-picked:visible').count(),1);await radios.nth(0).focus();await p.keyboard.press('ArrowRight');assert.equal(await p.locator('input[name=selected_picture]:checked').inputValue(),'P1');}
 if(mode==='selection'){await p.locator('.id-photo-preview img').first().scrollIntoViewIfNeeded();await p.waitForFunction(()=>document.querySelector('.id-photo-preview img').naturalWidth>0);}
 if(mode==='gallery-broken'){await p.locator('.id-photo-preview img').first().scrollIntoViewIfNeeded();await p.waitForFunction(()=>{const i=document.querySelector('.id-photo-preview img');return i.complete&&i.naturalWidth===0;});}
 if(mode==='secondary')assert.ok((await p.locator('.id-source').textContent()).includes('Secundária'));
 if(mode==='variation')assert.ok((await p.locator('.id-source').textContent()).includes('Principal de variação'));
 if(mode==='initial')assert.equal(await p.locator('#image-diagnostic-result').count(),0);
 if(['findings','catalog'].includes(mode))assert.equal(await p.locator('.id-finding').count(),1);
 if(mode==='catalog')assert.ok((await p.locator('#image-diagnostic-result').textContent()).includes('Publicação de catálogo'));
 if(mode==='empty')assert.ok((await p.locator('.id-empty').textContent()).includes('Isso não aprova'));
 if(['unknown','rate-limit','wrong-role'].includes(mode)){assert.equal(await p.locator('.id-empty').count(),0);assert.ok((await p.locator('#image-diagnostic-result [role=status]').textContent()).includes('Sem diagnóstico verificável'));}
 if(theme==='light')assert.equal(await p.locator('.top .sair').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(34, 95, 190)');
 if(theme==='light')assert.ok(await p.locator('.image-diagnostic .pf-hero').evaluate(e=>{
  const rgb=s=>(s.match(/[\d.]+/g)||[]).slice(0,3).map(Number),lum=c=>c.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);
  const bg=lum(rgb(getComputedStyle(e).backgroundColor)),fg=lum(rgb(getComputedStyle(e.querySelector('h2')).color));return (Math.max(bg,fg)+.05)/(Math.min(bg,fg)+.05)>=4.5;
 }));
 if(width===390)await p.screenshot({path:`visual-qa/image-diagnostic-${mode}-${theme}-${width}.png`,fullPage:true});
}console.log('72 official image diagnostic scope/theme/viewport cases passed.');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
