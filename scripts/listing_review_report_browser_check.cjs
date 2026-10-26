const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true});try{const p=await b.newPage();
 for(const mode of ['empty','full']){
  const html=fs.readFileSync(`visual-qa/listing-review-report-${mode}.html`,'utf8');
  for(const width of [1440,390,320]){
   await p.setViewportSize({width,height:900});await p.setContent(html);
   assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await p.evaluate(()=>window.print=()=>window.printRequested=true);await p.locator('button').click();assert.equal(await p.evaluate(()=>window.printRequested),true);
   await p.screenshot({path:`visual-qa/listing-review-report-${mode}-${width}.png`,fullPage:true});
  }
  await p.emulateMedia({media:'print'});assert.equal(await p.locator('.lr-controls').isVisible(),false);
  await p.pdf({path:`visual-qa/listing-review-report-${mode}.pdf`,format:'A4',preferCSSPageSize:true,printBackground:true});
  await p.screenshot({path:`visual-qa/listing-review-report-${mode}-print.png`,fullPage:true});
  await p.emulateMedia({media:'screen'});
 }
 console.log('Report responsive layout, print controls and A4 PDF generated.');
}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
