const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true});try{const p=await b.newPage();
for(const mode of ['alert','normal','stale','sparse','missing'])for(const width of [1440,390,320]){
 await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/price-deviation-${mode}.html`,'utf8'));
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await p.locator('.price-deviation').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(16, 34, 56)');
 if(mode==='alert'||mode==='normal'){
  assert.equal(await p.locator('.pd-cards article').count(),3);await p.locator('.price-deviation summary').click();
  assert.ok((await p.locator('.pd-state').textContent()).includes(mode==='alert'?'conferir o preço':'Regra não acionada'));
 }else assert.equal(await p.locator('.pd-cards article').count(),0);
 await p.screenshot({path:`visual-qa/price-deviation-${mode}-${width}.png`,fullPage:true});
}console.log('Price deviation rule, pending evidence and responsive checks passed.');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
