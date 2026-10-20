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
    await Promise.all([page.waitForURL('**status=active**'),page.getByRole('button',{name:'Aplicar filtros'}).click()]);
    assert.equal(await page.locator('select[name=status]').inputValue(),'active');
    assert.equal(await page.locator('select[name=estoque]').inputValue(),'baixo');
    assert.ok(await page.locator('.catalog-table tbody tr').count()<=10);
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Mobile body must not overflow; table scrolls internally');
    await page.screenshot({path:'visual-qa/catalog-mobile.png',fullPage:true});
    assert.deepEqual(errors,[]);
    console.log('Catalog desktop/mobile layout, five-column table, technical disclosure and GET filters passed.');
  }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
