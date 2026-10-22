const fs=require('node:fs');
const http=require('node:http');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const chart=await fetch('https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js').then(r=>{assert.ok(r.ok);return r.text()});
 const server=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html; charset=utf-8');res.end(fs.readFileSync('visual-qa/ads-chart.html'))});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 let browser;
 try{
  browser=await chromium.launch(process.env.PLAYWRIGHT_EXECUTABLE_PATH?{executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH}:{});
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('https://cdn.jsdelivr.net/**',route=>route.fulfill({contentType:'text/javascript',body:chart}));
  for(const [name,width] of [['desktop',1200],['mobile',390],['small-mobile',320]]){
   await page.setViewportSize({width,height:1000});await page.goto('http://127.0.0.1:'+server.address().port);
   await page.waitForFunction(()=>typeof Chart!=='undefined'&&Chart.getChart('kc-daily-chart'));
   await page.evaluate(()=>Chart.getChart('kc-daily-chart').update('none'));
   const values=await page.evaluate(()=>{const c=Chart.getChart('kc-daily-chart');return {labels:c.data.labels,data:c.data.datasets[0].data,money:c.options.plugins.tooltip.callbacks.label({dataset:{label:'Vendas Ads'},parsed:{y:683.64}})}});
   assert.deepEqual(values.labels,['16/10','17/10','18/10','19/10','20/10','21/10','22/10']);assert.equal(values.data.at(-2),683.64);assert.match(values.money,/683,64/);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   const canvas=page.locator('#kc-daily-chart');await canvas.scrollIntoViewIfNeeded();
   await page.evaluate(()=>{const c=Chart.getChart('kc-daily-chart');const e=c.getDatasetMeta(0).data[5];c.tooltip.setActiveElements([{datasetIndex:0,index:5},{datasetIndex:1,index:5},{datasetIndex:2,index:5}],{x:e.x,y:e.y});c.update('none')});
   await canvas.locator('..').screenshot({path:'visual-qa/ads-chart-'+name+'.png'});
  }
  assert.deepEqual(errors,[]);console.log('Ads chart: DD/MM labels, BRL tooltip, unchanged values and responsive desktop/mobile passed.');
 }finally{if(browser)await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1});
