import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { analyze } from '../static/title_optimizer.mjs';
const input = {product:'Kit 2 Travesseiros',brand:'Fibrasca',model:'Grafeno',original:'Kit 2 Travesseiros Fibrasca Grafeno Macio'};
const records = Array.from({length:60}, (_, i) => ({title:'Kit 2 Travesseiros Fibrasca Grafeno Macio Antistress Lavável',url:`https://produto.mercadolivre.com.br/MLB-${1000000+i}-produto?tracking=${i}`}));
let result = analyze(input, [...records, ...records]);
assert.equal(result.competitors.length, 50); assert.equal(result.sampleComplete, true);
assert.equal(result.keywords[0].count, 50);
assert.equal(result.keywords.find(row=>row.term==='Antistress').confirmed, false);
assert.ok(result.suggestions.every(title=>!title.includes('Antistress')));
assert.ok(result.suggestions.every(title=>Array.from(title).length<=60));
assert.equal(analyze(input, [records[0], {...records[0], url:records[0].url+'&other=1'}]).competitors.length, 1);
assert.equal(analyze(input, [{...records[0], sponsored:true},{...records[0],url:'https://evil.example/x'},{...records[0],url:'https://www.mercadolivre.com.br.evil.example/x'},{...records[0],title:'Kit 2 Travesseiros Outra Grafeno'}]).competitors.length, 0);
result = analyze({...input,confirmed:['Antistress','Lavável']}, records);
assert.ok(result.suggestions.some(title=>title.includes('Antistress')));
assert.equal(new Set(result.suggestions).size, result.suggestions.length);
assert.ok(result.suggestions.every(title=>title.startsWith('Kit 2 Travesseiros Fibrasca Grafeno')));
assert.equal(analyze({...input, product:'Produto'.repeat(10)},records).baseTooLong,true);
assert.equal(analyze(input,records.slice(0,5)).sampleComplete,false);
assert.equal(analyze(input,[]).suggestions.length,0);
const offer = {title:records[0].title,url:'https://www.mercadolivre.com.br/produto/up/MLBU1234567?pdp_filters=item_id:MLB1234567'};
assert.equal(analyze(input,[offer,{...offer,url:offer.url.replace('MLB1234567','MLB7654321')}]).competitors.length,2);
const malicious = analyze(input,[{...records[0],title:records[0].title+' <img src=x onerror=alert(1)>'}]);
assert.equal(malicious.competitors.length,1); // UI must insert this using textContent.
// Extension collector contract with controlled DOM doubles. Live selectors remain unvalidated.
function card(title, url, sponsored=false) {
 const anchor={href:url,innerText:title};const heading={innerText:title,closest:()=>anchor,querySelector:()=>null};
 return {innerText:title+(sponsored?' Patrocinado':''),getClientRects:()=>[{}],querySelector:selector=>selector==='h2, h3'?heading:null};
}
const context={URL,document:{body:{innerText:''},querySelectorAll:()=>[card('Produto','https://www.mercadolivre.com.br/p/MLB123456'),card('Anúncio','https://www.mercadolivre.com.br/p/MLB999999',true),card('Redirect','https://click1.mercadolivre.com.br/x')],querySelector:()=>({href:'https://lista.mercadolivre.com.br/produto_Desde_49'})}};
vm.createContext(context); vm.runInContext(fs.readFileSync('extensions/title_optimizer/collector.js','utf8'),context);
let collected = context.readTitleSearchPage();assert.equal(collected.records.length,1);assert.equal(collected.excludedSponsored,1);assert.ok(collected.next.endsWith('_Desde_49'));
context.document.querySelectorAll=()=>[];context.document.body.innerText='Hubo un error accediendo a esta pagina...';
assert.equal(context.readTitleSearchPage().state,'unavailable');
console.log('Title analysis and controlled collector checks passed. Live ML collection remains pending.');
function worker(pages) {
 const updates=new Set(),removed=new Set();const calls={pages:[],closed:[]};let listener;let index=0;
 const chrome={runtime:{id:'extension-id',onMessage:{addListener:fn=>listener=fn}},tabs:{create:async()=>({id:99}),update:async(id,{url})=>{calls.pages.push(url);queueMicrotask(()=>{for(const fn of updates)fn(id,{status:'complete'});});},remove:async id=>{calls.closed.push(id);},onUpdated:{addListener:fn=>updates.add(fn),removeListener:fn=>updates.delete(fn)},onRemoved:{addListener:fn=>removed.add(fn),removeListener:fn=>removed.delete(fn)}},scripting:{executeScript:async()=>[{result:pages[index++]}]}};
 const context={chrome,URL,Date,setTimeout,clearTimeout,queueMicrotask,importScripts:()=>{},readTitleSearchPage:()=>{}};
 vm.createContext(context);vm.runInContext(fs.readFileSync('extensions/title_optimizer/search.js','utf8'),context);
 return {context,calls,listener,updates,removed};
}
let w=worker([{state:'read',records:[records[0]],next:'https://lista.mercadolivre.com.br/produto_Desde_49',excludedSponsored:1},{state:'read',records:[records[0],records[1]],next:null,excludedSponsored:2}]);
let searchResult=await vm.runInContext('search("travesseiro")',w.context);
assert.equal(searchResult.records.length,2);assert.equal(searchResult.pages,2);assert.equal(searchResult.excludedSponsored,3);assert.equal(w.calls.closed.length,1);assert.equal(w.updates.size,0);assert.equal(w.removed.size,0);
w=worker([{state:'unavailable',records:[],next:null}]);searchResult=await vm.runInContext('search("produto")',w.context);assert.ok(searchResult.error);assert.equal(w.calls.pages.length,1);assert.equal(w.calls.closed.length,1);
w=worker([{state:'read',records:[records[0]],next:'https://evil.example/next',excludedSponsored:0}]);searchResult=await vm.runInContext('search("produto")',w.context);assert.equal(w.calls.pages.length,1);assert.match(searchResult.error,/não permitido/);
let reply;w.listener({type:'ping'},{id:'extension-id',url:'https://evil.example/otimizador-titulos'},value=>reply=value);assert.equal(reply,undefined);
w.listener({type:'ping'},{id:'extension-id',url:'https://app.keiperconsultoria.com.br/otimizador-titulos/1'},value=>reply=value);assert.equal(reply.ready,true);
console.log('Extension worker checks passed: pagination, deduplication, stop on errors, allowed origin, cleanup.');
