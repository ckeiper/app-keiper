const {setTheme}=require('./theme_control.cjs');
const fs=require('node:fs'),http=require('node:http'),assert=require('node:assert/strict');const {chromium}=require('playwright');
const MODES=['ready','empty','unknown','naive','removed','coincident','mixed','limited','conflict'];
(async()=>{const server=http.createServer((req,res)=>{
 if(req.url.startsWith('/atualizacoes/')){res.setHeader('Content-Type','application/json');return res.end('{"status":"nenhuma"}')};
 const mode=MODES.find(x=>new URL(req.url,'http://localhost').pathname==='/'+x)||'ready';
 res.setHeader('Content-Type','text/html;charset=utf-8');res.end(fs.readFileSync('visual-qa/promotion-comparison-'+mode+'.html'));
});await new Promise(r=>server.listen(0,'127.0.0.1',r));const b=await chromium.launch();try{
 const p=await b.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));const base='http://127.0.0.1:'+server.address().port;
 for(const mode of MODES)for(const width of [1440,390,320])for(const theme of ['dark','light']){
  await p.setViewportSize({width,height:1000});await p.goto(base+'/'+mode);await setTheme(p,theme);
  assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  const comparable=['ready','coincident','mixed','limited','conflict'].includes(mode);
  assert.equal(await p.locator('.pc-overlap').count(),comparable?1:0);
  if(comparable){
   await p.getByText('Comparação descritiva por calendário informado',{exact:true}).waitFor();
   await p.getByText('R$ 640,00',{exact:true}).waitFor();
   assert.equal(await p.locator('.pc-overlap h3').evaluate(e=>getComputedStyle(e).color),theme==='dark'?'rgb(234, 242, 255)':'rgb(23, 45, 71)');
   if(['coincident','mixed'].includes(mode)){
    assert.equal(await p.locator('.pc-overlap tbody tr').count(),4);
    if(theme==='dark'){await p.locator('.pc-overlap tbody tr').first().hover();assert.equal(await p.locator('.pc-overlap tbody td').first().evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(27, 52, 78)');}
    assert.ok((await p.locator('.pc-overlap').textContent()).includes('Antes · coincidências verificadas: 2'));
    assert.ok((await p.locator('.pc-overlap').textContent()).includes('Dentro do calendário · coincidências verificadas: 2'));
    if(width<650){const wrap=p.locator('.pc-overlap .pc-scroll');assert.ok(await wrap.evaluate(e=>e.scrollWidth>e.clientWidth));await wrap.focus();assert.ok(await wrap.evaluate(e=>document.activeElement===e));}
   }
   if(mode==='mixed'){
    await p.locator('.pc-overlap summary').click();
    assert.ok((await p.locator('.pc-overlap details').textContent()).includes('insuficientes/conflitantes: 2'));
    assert.ok((await p.locator('.pc-overlap details').textContent()).includes('idênticas agrupadas: 1'));
   }
   if(mode==='limited'){assert.equal(await p.locator('.pc-overlap tbody tr').count(),20);assert.ok((await p.locator('.pc-overlap [role=status]').textContent()).includes('20 interseções de 199'));}
   if(mode==='conflict'){assert.equal(await p.locator('.pc-overlap table').count(),0);assert.equal(await p.locator('.pc-overlap [role=status]').count(),2);}
   if(mode==='ready')assert.equal(await p.locator('.pc-overlap table').count(),0);
  }else assert.equal(await p.locator('h3').filter({hasText:'Comparação descritiva'}).count(),0);
  await p.screenshot({path:`visual-qa/promotion-comparison-${mode}-${theme}-${width}.png`,fullPage:true});
 }
 await p.goto(base);await p.locator('select[name=dias]').selectOption('30');await p.getByRole('button',{name:'Comparar',exact:true}).click();assert.equal(new URL(p.url()).searchParams.get('dias'),'30');
 for(const [mode,text] of [['empty','O histórico começa nas próximas'],['unknown','Consulta indisponível.'],['naive','Datas sem fuso explícito.'],['removed','Item removido não comprova']]){await p.goto(base+'/'+mode);await p.getByText(text,{exact:false}).waitFor();}
 assert.deepEqual(errors,[]);console.log('54 promotion comparison states/themes/viewports passed; overlap, exclusions and calendar scopes verified.');
}finally{await b.close();await new Promise(r=>server.close(r));}})().catch(e=>{console.error(e);process.exitCode=1});
