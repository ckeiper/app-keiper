const assert=require('node:assert/strict');
const fs=require('node:fs');
const http=require('node:http');
const {chromium}=require('playwright');
(async()=>{
 let failed=false,posts=0,readBeforeComplete=false,completed=new Set();
 const server=http.createServer((req,res)=>{
  res.setHeader('Content-Type','application/json');
  const url=new URL(req.url,'http://local');
  const refresh=url.pathname.match(/^\/atualizacoes\/(\d+)\/ads$/);
  if(refresh){
   assert.equal(url.searchParams.get('de'),url.searchParams.get('ate'));
   const id=refresh[1];
   if(req.method==='POST'){posts++;return res.end(JSON.stringify({id:'job'+id,status:'aguardando'}));}
   if(failed)return res.end(JSON.stringify({id:'job'+id,status:'falhou'}));
   completed.add(id);return res.end(JSON.stringify({id:'job'+id,status:'concluida',fim_em:Math.floor(Date.now()/1000)}));
  }
  const alerts=url.pathname.match(/^\/painel\/alertas\/(\d+)$/);
  if(alerts){const id=alerts[1];if(!completed.has(id))readBeforeComplete=true;
   return res.end(JSON.stringify({known:true,url:'/painel/alertas/'+id+'/detalhes',alerts:id==='1'?
    [{code:'budget',severity:'critical',label:'3 campanhas sem orçamento disponível'},
     {code:'forecast',severity:'warning',label:'2 campanhas podem esgotar o orçamento em 1 hora'}]:[]}));}
  if(url.pathname==='/painel/tendencias')return res.end('{}');
  res.setHeader('Content-Type','text/html; charset=utf-8');res.end(fs.readFileSync('visual-qa/home-alerts.html'));
 });
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch(process.env.PLAYWRIGHT_EXECUTABLE_PATH?{executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH}:{});
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const url='http://127.0.0.1:'+server.address().port;
 try{
  for(const width of [1440,390,320]){
   posts=0;completed.clear();await page.setViewportSize({width,height:850});await page.goto(url);
   await page.getByText('Atualizando Ads…').first().waitFor();
   await page.getByText('3 campanhas sem orçamento disponível',{exact:true}).waitFor();
   assert.equal(posts,2);assert.equal(readBeforeComplete,false);
   assert.equal(await page.getByText('+1 alerta',{exact:true}).getAttribute('href'),'/painel/alertas/1/detalhes');
   assert.equal(await page.getByText('Ads atualizados às',{exact:false}).count(),2);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await page.screenshot({path:'visual-qa/home-alerts-'+width+'.png',fullPage:true});
  }
  failed=true;await page.goto(url);await page.getByRole('button',{name:'Falha ao atualizar Ads · tentar novamente'}).first().waitFor();
  assert.equal(await page.getByText('3 campanhas sem orçamento disponível',{exact:true}).count(),0);
  assert.deepEqual(errors,[]);console.log('Home alerts: refresh before reads, failure state, desktop and mobile passed');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exit(1);});
