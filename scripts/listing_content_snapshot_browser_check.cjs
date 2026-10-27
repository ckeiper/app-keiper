const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{const page=await browser.newPage();
for(const mode of ['blank','read','empty','partial','unknown','requirements','variants','conditional','category-failure'])for(const width of [1440,390,320]){
 await page.setViewportSize({width,height:900});await page.setContent(fs.readFileSync(`visual-qa/content-snapshot-${mode}.html`,'utf8'));
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await page.locator('.content-snapshot form[method=post]').count(),1);
 assert.equal(await page.locator('.content-snapshot input[name=_csrf]').count(),1);
 assert.equal(await page.locator('.content-snapshot img').count(),0);
 if(['read','empty','partial','requirements','variants','conditional','category-failure'].includes(mode))assert.equal(await page.locator('.content-snapshot .pf-metric').count(),3);
 else assert.equal(await page.locator('.content-snapshot .pf-metric').count(),0);
 if(mode==='read'){
  await page.locator('#content-snapshot-result summary').click();
  assert.ok((await page.locator('#content-snapshot-result .cs-text').last().textContent()).includes('Medidas e conteúdo'));
  assert.ok((await page.locator('.cs-attributes').textContent()).includes('Marca fictícia'));
 }
 if(mode==='partial')assert.ok((await page.locator('#content-snapshot-result').textContent()).includes('Descrição não verificada'));
 if(mode==='empty')assert.ok((await page.locator('#content-snapshot-result').textContent()).includes('Descrição vazia'));
 if(mode==='blank')assert.equal(await page.locator('#content-snapshot-result').count(),0);
 if(['requirements','variants'].includes(mode)){
  assert.equal(await page.locator('.cs-requirement').count(),3);
  assert.ok((await page.locator('.cs-required').textContent()).includes('aplicabilidade não avaliada'));
  assert.ok((await page.locator('.cs-required').textContent()).includes('MLB200'));
 }
 if(mode==='variants'){
  assert.ok((await page.locator('.cs-requirement').first().textContent()).includes('1 de 2'));
  const details=page.locator('.cs-required details').first();
  await details.locator('summary').click();
  assert.ok((await details.textContent()).includes('Variação 1: Valor informado'));
  assert.ok((await details.textContent()).includes('Variação 2: Sem valor identificado'));
  assert.ok((await details.textContent()).includes('não comprova erro'));
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 }
 if(mode==='conditional')assert.ok((await page.locator('.cs-required').textContent()).includes('Obrigatório na consulta condicional do Mercado Livre'));
 if(mode==='category-failure'){
  assert.equal(await page.locator('.cs-requirement').count(),0);
  assert.ok((await page.locator('.cs-required [role=status]').textContent()).includes('Requisitos não verificados'));
 }
 await page.screenshot({path:`visual-qa/content-snapshot-${mode}-${width}.png`,fullPage:true});
}console.log('Read-only content, unknown/empty separation and responsive checks passed.');}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
