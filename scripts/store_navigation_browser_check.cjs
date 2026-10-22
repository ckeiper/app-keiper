const assert=require('node:assert/strict');
const fs=require('node:fs');
const http=require('node:http');
const {chromium}=require('playwright');

(async()=>{
  const server=http.createServer((req,res)=>{
    const section=new URL(req.url,'http://localhost').searchParams.get('section')||'resumo';
    if(!['resumo','ads','custos','anuncios'].includes(section)){res.writeHead(404);return res.end();}
    res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});
    res.end(fs.readFileSync('visual-qa/store-nav-'+section+'.html'));
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const url='http://127.0.0.1:'+server.address().port;
  try{
    for(const [section,route] of [['resumo','/painel/5'],['ads','/ads/5'],['custos','/custos/5'],['anuncios','/anuncios/5']]){
      await page.goto(url+'/?section='+section);
      assert.equal(await page.locator('.ks-store-nav [aria-current=page]').getAttribute('href'),route);
      assert.equal(await page.locator('.ks-nav-group[open]').count(),section==='resumo'?0:1);
      if(section!=='resumo')assert.ok(await page.locator('.ks-nav-group[open] [aria-current=page]').isVisible());
    }
    const expected=['/painel/5','/anuncios/5','/desempenho/5','/promocoes/5','/vendas/5','/full/5','/auditoria-frete/5','/ads/5','/campanhas/5','/prioridades/5','/demandas/5','/custos/5','/atualizar?cid=5','/diagnostico','/excluir/5'];
    const routes=await page.locator('.ks-sidebar a').evaluateAll(a=>a.map(x=>x.getAttribute('href')));
    for(const route of expected)assert.ok(routes.includes(route),'Missing route '+route);
    const publicity=page.locator('.ks-nav-group summary').filter({hasText:'Publicidade'});
    await publicity.click();await page.waitForTimeout(100);
    assert.equal(await page.locator('.ks-nav-group[open]').count(),1);
    assert.ok(await page.locator('.ks-nav-group[open]').innerText().then(x=>x.includes('Publicidade')));
    const sales=page.locator('.ks-nav-group summary').filter({hasText:'Vendas'});
    await sales.focus();await page.keyboard.press('Enter');await page.waitForTimeout(100);
    assert.equal(await page.locator('.ks-nav-group[open]').count(),1);
    assert.ok(await page.locator('.ks-nav-group[open]').innerText().then(x=>x.includes('Full e vendas')));
    await page.screenshot({path:'visual-qa/store-nav-desktop.png',fullPage:true});
    for(const width of [390,320]){
      await page.setViewportSize({width,height:844});
      await page.reload();
      const nav=page.locator('.ks-store-sidebar');
      const closed=await nav.boundingBox();
      assert.ok(closed.x+closed.width<=1,'Closed drawer must be entirely off screen');
      const before=await page.locator('.conteudo').boundingBox();
      assert.ok(before.y<250,'Closed drawer must not create blank vertical space');
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      await page.locator('.ks-mobile-toggle').click();await page.waitForTimeout(300);
      const open=await nav.boundingBox();
      assert.ok(Math.abs(open.x)<1 && Math.abs(open.y)<1,'Drawer must open at left edge');
      assert.equal(await page.locator('.ks-mobile-toggle').getAttribute('aria-expanded'),'true');
      await page.screenshot({path:'visual-qa/store-nav-mobile-'+width+'.png',fullPage:true});
      await page.keyboard.press('Escape');await page.waitForTimeout(300);
      assert.equal(await page.locator('.ks-mobile-toggle').getAttribute('aria-expanded'),'false');
      const after=await page.locator('.conteudo').boundingBox();assert.ok(Math.abs(before.y-after.y)<1);
    }
    assert.deepEqual(errors,[]);
    console.log('Store menu: all routes, current section, single-open submenus, keyboard, 320/390px drawer and blank-space checks passed.');
  }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
