const assert=require('node:assert/strict');
const fs=require('node:fs');
const http=require('node:http');
const {chromium}=require('playwright');
(async()=>{
 const server=http.createServer((req,res)=>{
  const args=new URL(req.url,'http://localhost').searchParams;
  const file=args.get('vazio')==='1'?'interventions-empty':args.get('pagina')==='2'?'interventions-page2':'interventions-history';
  res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(fs.readFileSync('visual-qa/'+file+'.html'));
 });
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto('http://127.0.0.1:'+server.address().port+'/anuncios/1/MLB100/acoes');
  assert.ok(await page.getByRole('heading',{name:'Ações e acompanhamento',exact:true}).isVisible());
  assert.equal(await page.locator('[aria-label="Histórico de ações"] article').count(),10);
  assert.ok(await page.getByText('+ R$ 700,00',{exact:true}).isVisible());
  assert.ok(await page.getByText('11 outra(s) ação(ões) registrada(s) neste intervalo. Os resultados se sobrepõem.',{exact:true}).isVisible());
  await page.getByLabel('Tipo',{exact:true}).selectOption('full');
  await page.getByLabel('O que foi alterado',{exact:true}).fill('Reposição de estoque concluída no Full.');
  assert.equal(await page.getByLabel('O que foi alterado',{exact:true}).inputValue(),'Reposição de estoque concluída no Full.');
  assert.equal(await page.locator('input[name=event_date]').getAttribute('max'),'2026-10-20');
  await page.screenshot({path:'visual-qa/interventions-desktop.png',fullPage:true});
  await Promise.all([page.waitForURL(u=>u.searchParams.get('pagina')==='2'),page.getByRole('link',{name:'Próxima',exact:true}).click()]);
  assert.equal(await page.locator('[aria-label="Histórico de ações"] article').count(),2);
  await page.setViewportSize({width:390,height:844});
  await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth+1);
  assert.ok(await page.locator('.iv-scroll').evaluate(el=>el.scrollWidth>el.clientWidth));
  await page.locator('.iv-scroll').evaluate(el=>{el.scrollLeft=el.scrollWidth;});
  assert.ok(await page.locator('.iv-scroll').evaluate(el=>el.scrollLeft>0));
  await page.locator('.iv-scroll').evaluate(el=>{el.scrollLeft=0;});
  await page.screenshot({path:'visual-qa/interventions-mobile.png',fullPage:true});
  await page.goto('http://127.0.0.1:'+server.address().port+'/anuncios/1/MLB100/acoes?vazio=1');
  assert.ok(await page.getByText('Nenhuma ação registrada para este anúncio.',{exact:true}).isVisible());
  assert.deepEqual(errors,[]);
  console.log('Action form, comparison, overlap notice, pagination, empty state and mobile layout passed.');
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
