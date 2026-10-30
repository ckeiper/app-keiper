const assert=require('node:assert/strict');
const fs=require('node:fs');
const http=require('node:http');
const {chromium}=require('playwright');
(async()=>{
  const server=http.createServer((req,res)=>{const filtered=new URL(req.url,'http://localhost').searchParams.get('status')==='active';res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(fs.readFileSync('visual-qa/'+(filtered?'catalog-filtered':'catalog')+'.html'));});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.route('https://http2.mlstatic.com/**',route=>route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56"><rect x="10" y="5" width="36" height="46" rx="8" fill="#97a7e9"/></svg>'}));
  try{
    await page.goto('http://127.0.0.1:'+server.address().port+'/anuncios/1');
    assert.equal(await page.locator('.catalog-summary .stat').count(),4);
    assert.equal(await page.locator('select[name=leitura]').count(),1);
    assert.equal(await page.locator('select[name=campanhas]').count(),1);
    assert.ok((await page.locator('.catalog-table').textContent()).includes('Campanhas:'));
    assert.equal(await page.locator('.catalog-dashboard').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(16, 34, 56)');
    assert.ok((await page.locator('.catalog-table th,.catalog-table td').evaluateAll(els=>els.map(el=>getComputedStyle(el).backgroundColor))).every(c=>c==='rgb(20, 41, 64)'));
    assert.equal(await page.locator('.catalog-table tbody tr').count(),20);
    assert.equal(await page.locator('.catalog-table th').count(),5);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await page.screenshot({path:'visual-qa/catalog-desktop.png',fullPage:true});
    await page.locator('.catalog-table .catalog-details summary').first().click();
    assert.equal(await page.locator('.catalog-table .catalog-details[open]').count(),1);
    assert.ok(await page.getByText('Peso cadastrado · PACKAGE_WEIGHT').first().isVisible());
    await page.locator('select[name=status]').selectOption('active');
    await page.locator('select[name=estoque]').selectOption('baixo');
    await page.locator('select[name=por_pagina]').selectOption('10');
    await Promise.all([page.waitForURL(url=>url.searchParams.get('status')==='active'),page.getByRole('button',{name:'Aplicar filtros'}).click()]);
    assert.equal(await page.locator('select[name=status]').inputValue(),'active');
    assert.equal(await page.locator('select[name=estoque]').inputValue(),'baixo');
    assert.ok(await page.locator('.catalog-table tbody tr').count()<=10);
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Mobile body must not overflow; table scrolls internally');
    // Reload to apply the shared sidebar's initial mobile state.
    await page.reload();
    assert.equal(await page.locator('.ks-mobile-toggle').getAttribute('aria-expanded'),'false');
    await page.locator('.ks-mobile-toggle').click();
    assert.equal(await page.locator('.ks-mobile-toggle').getAttribute('aria-expanded'),'true');
    assert.ok(await page.locator('.ks-sidebar a[aria-current=page]').isVisible());
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('.ks-mobile-toggle').getAttribute('aria-expanded'),'false');
    await page.screenshot({path:'visual-qa/catalog-mobile.png',fullPage:true});
    for(const width of [1440,390,320]){
      await page.setViewportSize({width,height:900});
      await page.setContent(fs.readFileSync('visual-qa/diagnostic-navy.html','utf8'));
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      assert.equal(await page.locator('#diag-acoes').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(16, 34, 56)');
      assert.equal(await page.locator('.diag-action').first().evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(20, 41, 64)');
      assert.equal(await page.locator('.diag-action h3').first().evaluate(el=>getComputedStyle(el).color),'rgb(234, 242, 255)');
      await page.locator('.diag-summary a').first().focus();
      assert.equal(await page.locator(':focus').getAttribute('href'),'#diag-acoes');
      await page.screenshot({path:`visual-qa/diagnostic-navy-${width}.png`,fullPage:true});
    }
    await page.setContent(fs.readFileSync('visual-qa/catalog-price-sort.html','utf8'));
    assert.deepEqual(await page.locator('.catalog-price').allTextContents(),['R$ 100,00','R$ 80,00']);
    assert.equal(await page.locator('select[name=ordem]').inputValue(),'preco');
    for(const mode of ['two','four','pending','partial','zero']) {
      for(const width of [1440,390,320]) {
        await page.setViewportSize({width,height:900});
        await page.setContent(fs.readFileSync(`visual-qa/listing-comparison-${mode}.html`,'utf8'));
        assert.equal(await page.locator('.lc-form input').count(),4);
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
        assert.equal(await page.locator('.lc').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(16, 34, 56)');
        assert.equal(await page.locator('.lc table').count(),mode==='pending'?0:3);
        if(mode!=='pending') {
          assert.equal(await page.locator('.lc-main-scroll thead th').count(),mode==='two'?3:5);
          assert.equal(await page.locator('.lc-main-scroll tbody tr').count(),8);
          assert.ok((await page.locator('.lc-main-scroll tbody').textContent()).includes('R$ 200,00 → R$ 100,00'));
          const efficiency=await page.locator('.lc-main-scroll tbody tr').last().locator('td').first().textContent();
          if(['partial','zero'].includes(mode))assert.ok(efficiency.includes('Indisponível'));
          else assert.equal(efficiency,'1,43% → 1,43%');
          if(mode==='partial')assert.ok((await page.locator('.lc-main-scroll tbody tr').nth(6).textContent()).includes('7/7 → 6/7 dias válidos'));
          if(width<700)assert.ok(await page.locator('.lc-main-scroll').evaluate(el=>el.scrollWidth>el.clientWidth));
          await page.locator('.lc-main-scroll').focus();assert.equal(await page.locator(':focus').getAttribute('role'),'region');
          await page.locator('.lc-daily:not(.lc-stock) summary').focus();await page.keyboard.press('Enter');
          assert.ok(await page.locator('.lc-daily:not(.lc-stock) tbody tr').first().isVisible());
          assert.equal(await page.locator('.lc-daily:not(.lc-stock) tbody tr').count(),7);
          assert.ok((await page.locator('.lc-daily:not(.lc-stock) tbody tr').first().textContent()).includes('23/10/2026'));
          if(mode==='partial')assert.equal(await page.locator('.lc-daily:not(.lc-stock) tbody tr').first().locator('td').first().textContent(),'Sem dado válido');
          if(mode==='zero')assert.equal(await page.locator('.lc-daily:not(.lc-stock) tbody tr').first().locator('td').first().textContent(),'0');
          if(width<700)assert.ok(await page.locator('.lc-daily-scroll').evaluate(el=>el.scrollWidth>el.clientWidth));
          await page.locator('.lc-stock summary').focus();await page.keyboard.press('Enter');
          assert.equal(await page.locator('.lc-stock tbody tr').count(),4);
          assert.equal(await page.locator('.lc-stock tbody tr').first().locator('td').first().textContent(),mode==='partial'?'Indisponível':mode==='zero'?'0 unidades':'12 unidades');
          assert.ok((await page.locator('.lc-stock').textContent()).includes('sem previsão de demanda'));
          if(width<700)assert.ok(await page.locator('.lc-stock-scroll').evaluate(el=>el.scrollWidth>el.clientWidth));

        }
        await page.screenshot({path:`visual-qa/listing-comparison-${mode}-${width}.png`,fullPage:true});
      }
    }
    for(const mode of ['all','filtered','pending','zero','second']) {
      for(const width of [1440,390,320]) {
        await page.setViewportSize({width,height:900});
        await page.setContent(fs.readFileSync(`visual-qa/listing-abc-${mode}.html`,'utf8'));
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
        assert.equal(await page.locator('.abc').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(16, 34, 56)');
        if(mode==='pending') {
          assert.equal(await page.locator('.abc table').count(),0);
          assert.ok((await page.locator('.abc').textContent()).includes('Dados incompletos não são zero'));
        } else {
          assert.equal(await page.locator('.abc-card').count(),4);
          assert.equal(await page.locator('.abc tbody tr').count(),mode==='filtered'?1:mode==='second'?8:20);
          assert.equal(await page.locator('.abc-form select').inputValue(),mode==='filtered'?'C':'todos');
          if(mode==='zero')assert.ok((await page.locator('.abc').textContent()).includes('Sem base percentual'));
          if(mode==='second')assert.ok((await page.locator('.abc-pages').textContent()).includes('Página 2 de 2'));
          if(width<700)assert.ok(await page.locator('.abc-scroll').evaluate(el=>el.scrollWidth>el.clientWidth));
          await page.locator('.abc-scroll').focus();assert.equal(await page.locator(':focus').getAttribute('role'),'region');
          await page.locator('.abc summary').focus();await page.keyboard.press('Enter');
          assert.ok(await page.locator('.abc details p').isVisible());
        }
        await page.screenshot({path:`visual-qa/listing-abc-${mode}-${width}.png`,fullPage:true});
      }
    }
    assert.deepEqual(errors,[]);
    console.log('Catalog desktop/mobile layout, five-column table, technical disclosure and GET filters passed.');
  }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
