const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright');
(async()=>{const b=await chromium.launch();try{const p=await b.newPage();for(const mode of ['initial','ready','empty','blocked','uncertain','confirmed','xss'])for(const theme of ['dark','light'])for(const width of [1440,390,320]){
await p.setViewportSize({width,height:900});await p.setContent(fs.readFileSync(`visual-qa/attribute-editor-${mode}.html`,'utf8'));await p.evaluate(t=>document.documentElement.dataset.theme=t,theme);
assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.equal(await p.locator('input[name=selected]:checked').count(),0);assert.equal(await p.evaluate(()=>window.injected),undefined);
const help=p.locator('.attribute-editor .kc-help').first();await help.locator('button').hover();assert.ok(await help.locator('[role=tooltip]').isVisible());await p.mouse.move(0,0);await help.locator('button').focus();assert.ok(await help.locator('[role=tooltip]').isVisible());await p.locator('.attribute-editor h2').click();
if(mode==='ready'){assert.equal(await p.getByRole('button',{name:'Aplicar selecionadas no Mercado Livre',exact:true}).count(),1);assert.equal(await p.locator('.ae-hidden').textContent(),'Oculto');await p.locator('input[name=selected]').check();assert.equal(await p.locator('input[name=selected]:checked').count(),1);assert.equal(await p.locator('.ae-apply [name=action]').inputValue(),'apply');}
if(['initial','empty','blocked','uncertain','confirmed'].includes(mode))assert.equal(await p.getByRole('button',{name:'Aplicar selecionadas no Mercado Livre',exact:true}).count(),0);
if(mode==='blocked')assert.ok(await p.locator('input[name=selected]').isDisabled());
if(mode==='uncertain'){assert.equal(await p.getByRole('button',{name:'Confirmar envio por nova leitura',exact:true}).count(),1);assert.equal(await p.locator('[name=manual_checked]').count(),1);}
await p.screenshot({path:`visual-qa/attribute-editor-${mode}-${theme}-${width}.png`,fullPage:true});
}console.log('42 attribute editor theme/viewport states passed.');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
