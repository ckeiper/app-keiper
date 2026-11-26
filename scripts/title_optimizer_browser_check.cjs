// Local development server only. Controlled records verify UI behavior, never live collection.
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async () => {
 const browser = await chromium.launch({headless:true});
 const page = await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 try {
  await page.goto('http://127.0.0.1:8765/otimizador-titulos/1');
  await page.getByLabel('Título original',{exact:true}).fill('Travesseiro Fibrasca Grafeno Macio');
  await page.getByLabel('Produto e quantidade',{exact:true}).fill('Travesseiro');
  await page.getByLabel('Marca',{exact:true}).fill('Fibrasca');
  await page.getByLabel('Modelo',{exact:true}).fill('Grafeno');
  await page.getByRole('button',{name:'Buscar concorrentes',exact:true}).click();
  assert.match(await page.locator('#title-status').innerText(),/Instale ou atualize/);
  // Controlled extension messages in the local preview, never in production.
  await page.addInitScript(() => {
   let connected = false;
   window.addEventListener('load', () => { connected = true; window.postMessage({type:'keiper-title-connected'}, location.origin); });
   window.addEventListener('message',event=> {
    if(connected && event.data?.type==='keiper-title-ping') window.postMessage({type:'keiper-title-ready',id:event.data.id,ready:true,version:'0.2.0'},location.origin);
    if(event.data?.type==='keiper-title-search') window.postMessage({type:'keiper-title-results',id:event.data.id,records:Array.from({length:35},(_,i)=>({title:'Travesseiro Fibrasca Grafeno Macio Lavável <img src=x onerror=alert(1)>',url:`https://produto.mercadolivre.com.br/MLB-${1000000+i}-produto`})),pages:1,excludedSponsored:2,collectedAt:'2026-11-26T19:00:00Z',query:event.data.query},location.origin);
   });
  });
  await page.reload();
  await page.getByLabel('Título original',{exact:true}).fill('Travesseiro Fibrasca Grafeno Macio');
  await page.getByLabel('Produto e quantidade',{exact:true}).fill('Travesseiro');
  await page.getByLabel('Marca',{exact:true}).fill('Fibrasca');
  await page.getByLabel('Modelo',{exact:true}).fill('Grafeno');
  await page.getByRole('button',{name:'Buscar concorrentes',exact:true}).click();
  await page.locator('#title-results').waitFor({state:'visible'});
  assert.match(await page.locator('#title-results').innerText(),/35 anúncios comparáveis/);
  assert.equal(await page.locator('#title-results img').count(),0);
  assert.equal(await page.locator('.to-suggestion').count(),1);
  await page.getByRole('checkbox',{name:'Lavável',exact:true}).check();
  assert.ok(await page.locator('.to-suggestion').count()>=2);
  assert.ok((await page.locator('.to-suggestion p').allTextContents()).every(title=>Array.from(title).length<=60));
  await page.getByText('Concorrentes analisados (35)',{exact:true}).click();
  assert.equal(await page.locator('#title-results details a').count(),35);
  for (const theme of ['dark','light']) for (const width of [1440,390,320]) {
   await page.setViewportSize({width,height:1000});
   await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${theme} ${width} overflow`);
  }
  await page.getByLabel('Marca',{exact:true}).fill('Outra marca');
  assert.equal(await page.locator('#title-results').isVisible(),false);
  assert.deepEqual(errors,[]);
  console.log('Local UI checks passed: extension handshake, 35 controlled records, term confirmation, XSS, copy layout, stale results, six theme/viewport combinations.');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
