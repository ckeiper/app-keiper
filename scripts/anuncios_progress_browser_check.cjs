const assert=require('node:assert/strict');
const fs=require('node:fs');
const http=require('node:http');
const {chromium}=require('playwright');
(async()=>{
 const server=http.createServer((req,res)=>{
  const chart=req.url.includes('/grafico');res.writeHead(200,{'Content-Type':chart?'application/json':'text/html; charset=utf-8'});
  res.end(fs.readFileSync(chart?'visual-qa/anuncios-progress-refresh.json':'visual-qa/anuncios-progress-current.html','utf8'));
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const expected=JSON.parse(fs.readFileSync('visual-qa/anuncios-progress-refresh.json','utf8'));
 const browser=await chromium.launch({headless:true});const page=await browser.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  for(const state of ['current','history'])for(const width of [1440,390,320]){
   await page.setViewportSize({width,height:900});
   await page.setContent(fs.readFileSync(`visual-qa/anuncios-progress-${state}.html`,'utf8'));
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   assert.equal(await page.locator('.ap-progress svg').count(),1);
   assert.ok(await page.locator('.ap-delivery-stage').isVisible());
   assert.ok((await page.locator('.ap-delivery-stage').textContent()).includes('Etapa da entrega'));
   assert.equal(await page.locator('.ap-progress a,.ap-progress form,.ap-progress table,.ap-progress ul,.ap-progress ol').count(),0);
   assert.equal(await page.locator('.ap-progress .ap-column').count(),state==='current'?1:2);
   assert.equal(await page.locator('.ap-progress polyline').count(),0);
   assert.equal(await page.locator('.ap-chart-card').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(16, 34, 56)');
   const labels=page.locator('.ap-chart svg text'),count=await labels.count();
   const dateBox=await labels.nth(count-2).boundingBox(),axisBox=await labels.last().boundingBox();
   assert.ok(dateBox.y+dateBox.height<=axisBox.y,'Chart date and axis labels must not overlap');
   assert.ok((await page.locator('.ap-scope').textContent()).includes('90 sugestões'));
   assert.ok((await page.locator('.ap-chart-head').textContent()).includes(String(expected.expected_total)+expected.expected_label));
   assert.equal(await page.locator('.ks-sidebar a[aria-current=page]').getAttribute('href'),'/evolucao-anuncios');
   if(width<641){
    await page.locator('.ks-toggle').click();
    assert.ok(await page.locator('.ks-sidebar a[aria-current=page]').isVisible());
    await page.keyboard.press('Escape');
   }
   await page.screenshot({path:`visual-qa/anuncios-progress-${state}-${width}.png`,fullPage:true});
  }
  await page.goto('http://127.0.0.1:'+server.address().port+'/evolucao-anuncios');
  await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));
  await page.waitForFunction(value=>document.querySelector('.ap-chart-head strong')?.textContent===String(value),expected.expected_done);
  assert.equal(await page.locator('.ap-progress .ap-column').count(),2);
  assert.equal(await page.locator('.ap-progress a,.ap-progress table,.ap-progress form').count(),0);
  assert.deepEqual(errors,[]);console.log('Progress chart only, accessible title, live counts and mobile navigation passed.');
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);process.exitCode=1;});
