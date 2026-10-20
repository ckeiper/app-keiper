// Browser checks use only synthetic HTML, with no production login or account data.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const http=require('node:http');
const {chromium}=require('playwright');

(async()=>{
  const html=fs.readFileSync('visual-qa/management-preview.html');
  const server=http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(html);});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  try{
    await page.goto('http://127.0.0.1:'+server.address().port+'/management-preview.html');
    assert.equal(await page.locator('#mgmt-panel-overview').isVisible(),true);
    assert.equal(await page.locator('#mgmt-panel-actions').isVisible(),false);
    assert.equal(await page.locator('#mgmt-panel-analysis').isVisible(),false);
    assert.equal(await page.locator('.mgmt-preview-card').count(),3);
    assert.ok(await page.locator('.mgmt-chart svg').isVisible());
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
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
    assert.deepEqual(errors,[]);
    console.log('Desktop/mobile width, tabs, keyboard navigation, filter state and priority shortcuts passed.');
  }finally{
    await browser.close();
    await new Promise(resolve=>server.close(resolve));
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
