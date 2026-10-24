// Real renderers, synthetic data only; no production authentication.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const http=require('node:http');
const {chromium}=require('playwright');
(async()=>{
 let state='populated';
 const server=http.createServer((req,res)=>{
  if(req.url==='/painel/tendencias'){res.writeHead(200,{'Content-Type':'application/json'});return res.end('{"1":"up","2":"down"}');}
  if(req.url==='/crm/resumo'){
   res.writeHead(state==='error'?503:200,{'Content-Type':'text/html; charset=utf-8'});
   return res.end(state==='error'?'Unavailable':fs.readFileSync('visual-qa/crm-'+state+'.html'));
  }
  res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(fs.readFileSync('visual-qa/crm-home.html'));
 });
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch(process.env.PLAYWRIGHT_EXECUTABLE_PATH?{executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH}:{});const page=await browser.newPage();const errors=[];
 page.on('pageerror',e=>errors.push(e.message));const url='http://127.0.0.1:'+server.address().port;
 try{
  for(const [name,width,height] of [['desktop',1440,1050],['mobile',390,844],['small-mobile',320,780]]){
   await page.setViewportSize({width,height});await page.goto(url);
   await page.locator('.kc-panel[aria-busy=false]').waitFor();
   assert.equal(await page.locator('input[type=search]').count(),0);
   assert.equal(await page.evaluate(()=>getComputedStyle(document.body).backgroundColor),'rgb(11, 20, 38)');
   const toggle=page.locator('.ks-toggle');
   assert.equal(await toggle.getAttribute('aria-expanded'),width<=640?'false':'true');
   await toggle.click();
   assert.equal(await toggle.getAttribute('aria-expanded'),width<=640?'true':'false');
   if(width<=640)await toggle.click();
   else{await toggle.click();assert.equal(await toggle.getAttribute('aria-expanded'),'true');}
   assert.equal(await page.locator('.ks-foot a').getAttribute('href'),'/seguranca');
   assert.equal(await page.locator('.top a[href="/seguranca"]').count(),0);
   assert.equal(await page.locator('.kh-store-main').first().getAttribute('href'),'/painel/1');
   assert.deepEqual(await page.locator('.kh-client-label').allTextContents(),['ABM VEDAÇÕES','Copas Ind']);
   await page.locator('.kh-more').first().click();
   assert.equal(await page.locator('.kh-menu').first().isVisible(),true);
   await page.keyboard.press('Escape');
   assert.equal(await page.locator('.kc-lead').count(),3);
   assert.equal(await page.locator('.kc-stat strong').allTextContents().then(x=>x.join(',')),'2,1,4');
   assert.equal(await page.locator('.kc-lead-name').last().textContent(),'Ana <Loja Exemplo>');
   assert.equal(await page.locator('.kc-lead').last().getAttribute('href'),'/crm/13');
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Horizontal overflow at '+width);
   const shops=await page.locator('#kh-grid').boundingBox(),crm=await page.locator('.kc-wrap').boundingBox();
   assert.ok(crm.y>=shops.y+shops.height,'CRM must remain below stores');
   await page.locator('.kc-panel').screenshot({path:'visual-qa/crm-'+name+'.png'});
   await page.screenshot({path:'visual-qa/home-navy-'+name+'.png',fullPage:true});
  }
  state='empty';await page.goto(url);await page.locator('.kc-empty').waitFor();
  assert.equal(await page.locator('.kc-lead').count(),0);
  assert.deepEqual(await page.locator('.kc-stat strong').allTextContents(),['0','0','0']);
  await page.locator('.kc-panel').screenshot({path:'visual-qa/crm-empty.png'});
  state='error';await page.goto(url);await page.getByText('Não foi possível carregar os acompanhamentos. Abra o CRM para consultar.').waitFor();
  assert.deepEqual(await page.locator('.kc-stat strong').allTextContents(),['—','—','—']);
  assert.equal(await page.locator('.kc-primary').getAttribute('href'),'/crm');
  assert.equal(await page.locator('.kc-panel').getAttribute('aria-busy'),'false');
  assert.deepEqual(errors,[]);
  console.log('CRM desktop/mobile, loaded/empty/error states, escaped names and store order passed.');
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
