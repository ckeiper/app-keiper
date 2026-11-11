const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{const page=await browser.newPage();
for(const mode of ['ready','shift','zero','zero-real','partial','pending','invalid','spike'])for(const theme of ['dark','light'])for(const width of [1440,390,320]){
 await page.setViewportSize({width,height:900});await page.setContent(fs.readFileSync(`visual-qa/listing-projection-history-${mode}.html`,'utf8'));
 await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await page.evaluate(()=>document.fonts.ready);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await page.locator('.ph form').count(),0);
 assert.equal(await page.getByRole('link',{name:'Padrão semanal e cobertura'}).getAttribute('href'),'/anuncios/7/MLB1/padrao-semanal');
 const ready=!['partial','pending','invalid'].includes(mode);
 assert.equal(await page.locator('.ph-table tbody tr').count(),ready?4:0);
 assert.equal(await page.locator('.ph .wp-cmp-series').count(),ready?8:0);
 assert.equal(await page.locator('.ph .wp-stats article').count(),ready?3:0);
 assert.equal(await page.locator('.ph progress').getAttribute('value'),mode==='partial'?'55':'56');
 if(!ready)assert.ok((await page.locator('.ph [role=status]').textContent()).includes('Conferência indisponível'));
 if(['zero','zero-real'].includes(mode)){assert.ok((await page.locator('.ph-zero').textContent()).includes('O percentual não é calculado'));assert.equal(await page.locator('.ph .wp-stats strong').nth(2).textContent(),'—');}
 if(mode==='shift'){assert.equal(await page.locator('.ph .wp-stats strong').first().textContent(),'4,4');assert.equal(await page.locator('.ph .wp-stats strong').nth(1).textContent(),'-4,4');}
 if(mode==='ready')assert.equal(await page.locator('.ph .wp-stats strong').first().textContent(),'0,0');
 const expected=theme==='light'?'rgb(255, 255, 255)':'rgb(16, 34, 56)';assert.equal(await page.locator('.ph').evaluate(e=>getComputedStyle(e).backgroundColor),expected);
 if(ready){const wrap=page.locator('.ph-table');await wrap.focus();assert.ok(await wrap.evaluate(e=>document.activeElement===e));if(width<650)assert.ok(await wrap.evaluate(e=>e.scrollWidth>e.clientWidth));}
 const method=page.locator('.ph .section-help details');
 assert.equal(await method.evaluate(el=>el.open),false);
 await method.locator('summary').click();
 assert.ok(await method.getByText('Não reconstitui',{exact:false}).isVisible());
 if(width===390)await page.screenshot({path:`visual-qa/listing-projection-history-${mode}-${theme}-${width}.png`,fullPage:true});
}console.log('48 retrospective mean scope/theme/viewport cases passed.');}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
