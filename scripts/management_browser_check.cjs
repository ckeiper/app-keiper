// Browser checks use only synthetic HTML, with no production login or account data.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const http=require('node:http');
const {chromium}=require('playwright');

(async()=>{
  const html=fs.readFileSync('visual-qa/management-preview.html');
  const server=http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});if(req.url.startsWith('/ranking-anuncios/')){res.end('<section class="kp-queue"><h2>Anúncios que precisam de atenção</h2><p>Dados de teste</p></section>');return;}res.end(html);});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({headless:true});
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
    assert.ok(await page.locator('[data-chart-panel=daily] svg').isVisible());
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
    await page.screenshot({path:'visual-qa/mobile.png',fullPage:true});
    await page.getByText('Ver todas as oportunidades').click();
    assert.equal(await page.locator('#mgmt-panel-actions').isVisible(),true);
    assert.equal(await page.locator('#mgmt-tab-actions').getAttribute('aria-selected'),'true');
    for(const width of [1440,390,320]) {
      await page.setViewportSize({width,height:900});
      await page.setContent(fs.readFileSync('visual-qa/ledger-preview.html','utf8'));
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      assert.equal(await page.locator('.ledger-check .frete-metrica').count(),3);
      assert.equal(await page.locator('.ledger-check h3').evaluate(el=>getComputedStyle(el).color),'rgb(234, 242, 255)');
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
