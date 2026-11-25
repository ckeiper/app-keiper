// Browser checks use only synthetic HTML, with no production login or account data.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const http=require('node:http');
const {chromium}=require('playwright');

(async()=>{
  const html=fs.readFileSync('visual-qa/management-preview.html');
  const server=http.createServer((req,res)=>{
    if(req.url==='/logo.png'){
      res.writeHead(200,{'Content-Type':'image/png'});
      res.end(fs.readFileSync('logo_Keiper_Consultoria.png'));
      return;
    }
    res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});
    if(req.url.startsWith('/ranking-anuncios/')){
      res.end('<section class="kp-queue"><h2>Anúncios que precisam de atenção</h2><p>Dados de teste</p></section>');
      return;
    }
    res.end(html);
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({headless:true,executablePath:process.env.KEIPER_BROWSER_EXECUTABLE});
  const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  try{
    await page.goto('http://127.0.0.1:'+server.address().port+'/management-preview.html');
    assert.equal(await page.locator('#mgmt-panel-overview').isVisible(),true);
    await page.locator('#mgmt-auto-priorities .kp-queue').waitFor();
    assert.equal(await page.locator('#mgmt-panel-overview').count(),1);
    assert.equal(await page.locator('#mgmt-panel-actions').isVisible(),false);
    assert.equal(await page.locator('#mgmt-panel-analysis').isVisible(),false);
    assert.equal(await page.locator('.mgmt-preview-card').count(),3);
    assert.equal(await page.locator('.mgmt-preview-card[href]').count(),3);
    assert.equal(await page.locator('.mgmt-shortcut').count(),5);
    assert.ok((await page.locator('.mgmt-shortcut').first().getAttribute('href')).startsWith('/vendas/1?'));
    assert.equal(await page.locator('.mgmt-dashboard .card').first().evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(17, 36, 58)');
    assert.equal(await page.locator('.mgmt-header h2').evaluate(el=>getComputedStyle(el).color),'rgb(237, 245, 255)');
    assert.equal(await page.locator('.mgmt-kpis .stat .num').first().evaluate(el=>getComputedStyle(el).color),'rgb(244, 249, 255)');
    assert.equal(await page.locator('.mgmt-header').textContent().then(t=>t.includes('Resultados, oportunidades e próximos passos')),false);
    assert.ok(await page.locator('.mgmt-variation-down').count());
    assert.equal(await page.locator('.mgmt-variation-down').first().evaluate(el=>getComputedStyle(el).color),'rgb(255, 177, 184)');
    assert.ok(await page.locator('.mgmt-variation-up').count());
    assert.equal(await page.locator('.mgmt-variation-up').first().evaluate(el=>getComputedStyle(el).color),'rgb(128, 240, 183)');
    assert.ok(await page.locator('[data-chart-panel=daily] svg').isVisible());
    assert.equal(await page.locator('.mgmt-sparkline:visible').count(),4);
    const revenue=page.locator('[data-chart-panel=daily]');
    const plot=revenue.locator('.mgmt-chart-interaction');
    const tooltip=plot.locator('.mgmt-chart-tooltip');
    const firstRevenue=await revenue.locator('tbody tr').first().locator('td').nth(1).textContent();
    const lastRevenue=await revenue.locator('tbody tr').last().locator('td').nth(1).textContent();
    await plot.hover({position:{x:1,y:30}});
    assert.match(await tooltip.locator('span').first().textContent(),/^Atual · \d{2}\/\d{2} · R\$/);
    assert.match(await revenue.locator('.mgmt-chart-x span').first().textContent(),/^\d{2}\/\d{2}$/);
    assert.ok((await tooltip.locator('span').first().textContent()).endsWith(firstRevenue));
    assert.ok((await tooltip.locator('span').last().textContent()).startsWith('Anterior'));
    await plot.press('End');
    assert.ok((await tooltip.locator('span').first().textContent()).endsWith(lastRevenue));
    await plot.press('Escape');
    assert.equal(await tooltip.isVisible(),false);
    const chartBox=await page.locator('[data-chart-panel=daily] .mgmt-chart').boundingBox();
    assert.ok(chartBox.y<800,'Revenue chart should be prominent in the first desktop screen');
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await page.locator('[data-chart-choice=daily_orders]').click();
    assert.equal(await page.locator('[data-chart-panel=daily_orders]').isVisible(),true);
    assert.equal(await page.locator('[data-chart-panel=daily]').isVisible(),false);
    await page.locator('[data-chart-choice=daily]').click();
    await page.locator('.mgmt-leaders [data-product-open]').first().click();
    assert.equal(await page.locator('dialog[open]').count(),1);
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('dialog[open]').count(),0);
    assert.equal(new URL(page.url()).searchParams.get('aba'),null);
    await page.screenshot({path:'visual-qa/desktop.png',fullPage:true});
    await page.locator('.kt-settings > summary').click();
    await page.getByRole('switch',{name:'Tema escuro'}).click();
    assert.equal(await page.locator('html').getAttribute('data-theme'),'light');
    assert.equal(await page.locator('.mgmt-sparkline:visible').count(),4);
    assert.ok(await page.locator('.ks-brand-logo').evaluate(el=>el.complete && el.naturalWidth>0));
    assert.equal(await page.locator('.ks-sidebar').evaluate(el=>getComputedStyle(el).backgroundImage.includes('gradient')),true);
    const responsivePage=await browser.newPage({viewport:{width:1752,height:897},hasTouch:true});
    await responsivePage.addInitScript(()=>localStorage.setItem('keiper-theme','light'));
    await responsivePage.goto(page.url());
    await responsivePage.locator('.mgmt-sparkline').first().waitFor();
    await responsivePage.screenshot({path:'visual-qa/corporativo-desktop.png'});
    for(const width of [390,320]){
      await responsivePage.setViewportSize({width,height:844});
      assert.ok(await responsivePage.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Light theme overflows');
    }
    await responsivePage.setViewportSize({width:390,height:844});
    await responsivePage.screenshot({path:'visual-qa/corporativo-mobile.png'});
    await responsivePage.locator('[data-chart-panel=daily] .mgmt-chart-interaction').tap({position:{x:1,y:30}});
    assert.ok(await responsivePage.locator('[data-chart-panel=daily] .mgmt-chart-tooltip').isVisible());
    await responsivePage.locator('.ks-mobile-toggle').click();
    assert.equal(await responsivePage.locator('.ks-mobile-toggle').getAttribute('aria-expanded'),'true');
    await responsivePage.keyboard.press('Escape');
    assert.equal(await responsivePage.locator('.ks-mobile-toggle').getAttribute('aria-expanded'),'false');
    const customizePeriod=responsivePage.locator('.mgmt-period-dates summary');
    assert.equal(await customizePeriod.textContent(),'Personalizar');
    assert.match(await responsivePage.locator('.mgmt-period + .muted').textContent(),
      /^\d{2}\/\d{2}\/\d{4} a \d{2}\/\d{2}\/\d{4}\. Horário de Brasília\.$/);
    await customizePeriod.click();
    assert.ok(await responsivePage.getByLabel('Início',{exact:true}).isVisible());
    await responsivePage.close();
    await page.getByRole('switch',{name:'Tema escuro'}).click();
    await page.locator('.kt-settings > summary').click();
    assert.equal(await page.locator('.mgmt-sparkline:visible').count(),4);
    await page.locator('#mgmt-tab-actions').click();
    assert.equal(await page.locator('#mgmt-panel-actions').isVisible(),true);
    assert.equal(new URL(page.url()).searchParams.get('aba'),'actions');
    await page.locator('#mgmt-tab-actions').press('End');
    assert.equal(await page.locator('#mgmt-panel-analysis').isVisible(),true);
    assert.equal(await page.locator('#mgmt-panel-analysis input[name=aba]').inputValue(),'analysis');
    await page.screenshot({path:'visual-qa/analysis.png',fullPage:true});
    await page.locator('#mgmt-tab-analysis').press('Home');
    assert.equal(await page.locator('#mgmt-panel-overview').isVisible(),true);
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Mobile page overflows');
    await page.setViewportSize({width:320,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Small mobile page overflows');
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:'visual-qa/mobile.png',fullPage:true});
    await page.getByText('Ver todas as oportunidades').click();
    assert.equal(await page.locator('#mgmt-panel-actions').isVisible(),true);
    assert.equal(await page.locator('#mgmt-tab-actions').getAttribute('aria-selected'),'true');
    for(const width of [1440,390,320]) {
      await page.setViewportSize({width,height:900});
      await page.setContent(fs.readFileSync('visual-qa/ledger-preview.html','utf8'));
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      assert.equal(await page.locator('.ledger-check .frete-metrica').count(),3);
      assert.equal(await page.locator('.ledger-groups tbody tr').count(),2);
      await page.locator('.ledger-check details summary').click();
      assert.ok((await page.locator('.ledger-check details').innerText()).includes('Linha 6'));
      assert.equal(await page.locator('.ledger-groups th').first().evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(24, 46, 73)');
      assert.deepEqual(await page.locator('.ledger-check h3').evaluateAll(els=>els.map(el=>getComputedStyle(el).color)),['rgb(234, 242, 255)','rgb(234, 242, 255)']);
      assert.ok((await page.locator('.ledger-check').innerText()).includes('1 com diferença'));
      await page.screenshot({path:`visual-qa/ledger-${width}.png`,fullPage:true});
    }
    assert.deepEqual(errors,[]);
    console.log('Desktop/mobile width, tabs, keyboard navigation, filter state and priority shortcuts passed.');
  }finally{
    await browser.close();
    await new Promise(resolve=>server.close(resolve));
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
