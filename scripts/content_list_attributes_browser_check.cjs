const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();try{const p=await b.newPage();for(const mode of ['matched','review','unknown','variation','managed','category-failure','compound','limited'])for(const theme of ['dark','light'])for(const width of [1440,390,320]){
 await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/content-list-${mode}.html`,'utf8'));await p.evaluate(t=>document.documentElement.dataset.theme=t,theme);
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.equal(await p.locator('.content-snapshot form').count(),1);
 assert.ok(await p.locator('.cs-actions').isVisible());
 if(mode==='matched')assert.ok(await p.locator('[data-list-state=matched]').isVisible());
 if(['review','variation','managed'].includes(mode))assert.ok(await p.locator('[data-list-state=review]').isVisible());
 if(['unknown','compound'].includes(mode))assert.ok(await p.locator('[data-list-state=unknown]').isVisible());
 if(mode==='category-failure')assert.equal(await p.locator('.cs-list-row').count(),0);
 if(mode==='limited'){assert.equal(await p.locator('.cs-list-row').count(),100);assert.ok((await p.locator('.cs-list-values').innerText()).includes('100 resultados'));}
 if(mode==='managed')assert.ok((await p.locator('.cs-list-values').innerText()).includes('sem recomendar edição direta'));
 if(theme==='light')assert.ok(await p.locator('.content-snapshot .pf-hero').evaluate(e=>{
   const rgb=s=>(s.match(/[\d.]+/g)||[]).slice(0,3).map(Number),lum=c=>c.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);
   const bg=lum(rgb(getComputedStyle(e).backgroundColor)),fg=lum(rgb(getComputedStyle(e.querySelector('h2')).color));return (Math.max(bg,fg)+.05)/(Math.min(bg,fg)+.05)>=4.5;
 }));
 if(width===390&&['matched','review','variation','unknown'].includes(mode))await p.screenshot({path:`visual-qa/content-list-${mode}-${theme}-${width}.png`,fullPage:true});
}console.log('List IDs: 48 responsive theme cases passed, including custom text, unknowns, variations and bounds.');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
