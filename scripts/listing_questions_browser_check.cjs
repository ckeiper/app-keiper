const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{const page=await browser.newPage();
for(const mode of ['empty','ready','limited','page2','fresh','unknown','partial','queue','queue-page2','queue-empty','search','search-page2','search-empty','search-escaped'])for(const theme of ['dark','light'])for(const width of [1440,390,320]){
 await page.setViewportSize({width,height:900});await page.setContent(fs.readFileSync(`visual-qa/listing-questions-${mode}.html`,'utf8'));
 await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.equal(await page.locator('.lq-cards article').count(),4);
 assert.equal(await page.locator('.k-refresh').count(),1);
 assert.equal(await page.locator('.k-refresh button').textContent(),'Atualizar Perguntas');
 if(theme==='light'){
 assert.equal(await page.locator('.listing-questions').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(255, 255, 255)');
 assert.equal(await page.locator('.lq-cards article').first().evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(242, 246, 251)');
 }
 if(theme==='dark')assert.equal(await page.locator('.listing-questions').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(16, 34, 56)');
 assert.equal(await page.locator('.listing-questions #perguntas .lq-row').count(),['empty','queue-empty','search-empty','search-escaped'].includes(mode)?0:mode==='queue-page2'?1:mode==='search-page2'?2:10);
 assert.equal(await page.locator('.listing-questions #recorrencias .lq-row').count(),mode==='empty'?0:3);
 assert.equal(await page.locator('.listing-questions form[method=post]').count(),0);
 const taskLinks=page.getByRole('link',{name:/Planejar ajuste da pergunta #/});for(const link of await taskLinks.all())assert.match(await link.getAttribute('href'),/^\/anuncios\/1\/MLB123\/tarefas\?pergunta=[1-9][0-9]{0,19}#lt-criar$/);if(mode==='ready')assert.equal(await taskLinks.count(),9);
 const queueLink=page.locator('.lq-card-link').filter({hasText:'Aguardando resposta'});
 assert.ok((await queueLink.getAttribute('href')).includes('status=pending#perguntas'));
 if(mode.startsWith('queue')){
 assert.equal(await page.locator('.listing-questions select').inputValue(),'pending');
 assert.ok((await page.locator('#perguntas').textContent()).includes('Mais antigas primeiro'));
 if(mode==='queue') {
 assert.equal(await page.locator('#perguntas .lq-row strong').first().textContent(),'Pergunta #22');
 assert.equal(await page.locator('#perguntas .lq-wait').count(),10);
 assert.ok((await page.locator('#perguntas nav a').getAttribute('href')).includes('status=pending'));
 }
 if(mode==='queue-page2')assert.equal(await page.locator('#perguntas .lq-wait').textContent(),'Tempo de espera não verificado');
 if(mode==='queue-empty')assert.ok((await page.locator('#perguntas').textContent()).includes('confirmada nesta amostra'));
 }
 const originalStatus=await page.locator('.listing-questions select').inputValue();const search=page.getByRole('searchbox',{name:'Buscar na pergunta ou resposta'});const originalSearch=await search.inputValue();assert.equal(await search.count(),1);assert.equal(await search.getAttribute('maxlength'),'200');assert.equal(await page.locator('.lq-search-form').getAttribute('method'),'get');await search.focus();assert.equal(await search.evaluate(e=>document.activeElement===e),true);
 if(mode.startsWith('search')){assert.equal(await page.getByRole('link',{name:'Limpar busca'}).count(),1);if(mode==='search-escaped')assert.equal(await search.inputValue(),'<script>searchAttack()</script>');if(mode==='search')assert.ok((await page.locator('#perguntas nav a').getAttribute('href')).includes('q=TENSAO'));}
 await search.fill('Medida');assert.equal(await search.inputValue(),'Medida');
 await page.locator('.listing-questions select').selectOption('pending');
 await page.locator('.listing-questions select').selectOption('ANSWERED');
 assert.equal(await page.locator('.listing-questions select').inputValue(),'ANSWERED');
 await page.locator('.listing-questions select').selectOption('all');
 if(mode==='limited')assert.ok((await page.locator('.listing-questions [role=status]').textContent()).includes('1.000'));
 if(mode==='fresh')assert.ok((await page.locator('#perguntas').textContent()).includes('Retirada do anúncio'));
 if(mode==='partial')assert.ok((await page.locator('.lq-coverage').textContent()).includes('Coleta parcial'));
 if(mode==='unknown')assert.ok((await page.locator('#perguntas').textContent()).includes('Status sem verificação recente'));
 await search.fill(originalSearch);await page.locator('.listing-questions select').selectOption(originalStatus);
 await page.screenshot({path:`visual-qa/listing-questions-${mode}-${theme}-${width}.png`,fullPage:true});
}console.log('84 question scope, search, filters and desktop/mobile cases passed.');}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
