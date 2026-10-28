const fs=require('node:fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const b=await chromium.launch();try{const p=await b.newPage();for(const mode of ['candidates','empty','confirm'])for(const width of [1440,390,320]){
 await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/promotion-participation-${mode}.html`,'utf8'));
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await p.locator('body').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(8, 20, 38)');
 if(mode==='confirm'){
  assert.equal(await p.locator('input[name=confirmar]').isChecked(),false);
  assert.equal(await p.locator('input[name=confirmar]').getAttribute('required'),'');
  assert.ok((await p.locator('.conteudo').textContent()).includes('adesão real'));
 }else{
  assert.equal(await p.locator('[aria-label="Candidatos à promoção"]').getAttribute('tabindex'),'0');
  if(width<400)assert.ok(await p.locator('[aria-label="Candidatos à promoção"]').evaluate(e=>e.scrollWidth>e.clientWidth));
 }
 await p.screenshot({path:`visual-qa/promotion-participation-${mode}-${width}.png`,fullPage:true});
}console.log('Promotions: candidate table and explicit confirmation passed.');}finally{await b.close()}})().catch(e=>{console.error(e);process.exitCode=1});
