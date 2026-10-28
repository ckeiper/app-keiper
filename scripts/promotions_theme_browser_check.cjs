const fs=require('node:fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const b=await chromium.launch();try{const p=await b.newPage();for(const mode of ['ready','empty'])for(const width of [1440,390,320]){
 await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/promotions-theme-${mode}.html`,'utf8'));
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await p.locator('body').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(8, 20, 38)');
 assert.equal(await p.locator('.conteudo h2').first().evaluate(e=>getComputedStyle(e).color),'rgb(237, 245, 255)');
 assert.equal(await p.locator('input[name=mc_meta]').count(),1);
 if(mode==='ready'){
  assert.ok((await p.locator('.promo-item').textContent()).includes('Produto de teste'));
  assert.equal(await p.locator('.promo-item th').first().evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(27, 52, 78)');
  if(width<400)assert.ok(await p.locator('.promo-item').evaluate(e=>e.scrollWidth>e.clientWidth));
 }
 await p.screenshot({path:`visual-qa/promotions-${mode}-${width}.png`,fullPage:true});
}console.log('Promotions: contrast, forms, empty state and responsive table passed.');}finally{await b.close()}})().catch(e=>{console.error(e);process.exitCode=1});
