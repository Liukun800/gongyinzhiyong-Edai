const {chromium}=require('C:/Users/liuko/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const out=path.join(__dirname,'..','评审整改','PM12_Demo业务展示升级_20261002','qa');await fs.mkdir(out,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});const checks=[],errors=[];
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1.5});page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8767/');await page.waitForFunction(()=>!document.querySelector('#run').disabled);
  assert.equal(await page.locator('#business-view').isVisible(),true);assert.equal(await page.locator('#workbench-view').isVisible(),false);assert.equal(await page.locator('#business-view .official-grid a').count(),4);
  await page.screenshot({path:path.join(out,'09_先论证再演示_首页.png')});await page.screenshot({path:path.join(out,'10_价值论证_全页.png'),fullPage:true});checks.push('默认先展示银行公开能力、拟议介入位置与可验证增量，附四个官方来源链接');
  await page.click('[data-start-scenario="D02"]');await page.waitForFunction(()=>document.querySelector('#case-title').textContent.startsWith('D02')&&!document.querySelector('#run').disabled);
  assert.equal(await page.locator('#workbench-view').isVisible(),true);assert.equal(await page.locator('#exit-focus').isVisible(),true);assert.match(await page.locator('#journey-input').innerText(),/4 份材料/);assert.match(await page.locator('#journey-run').innerText(),/已核验/);
  await page.click('[data-evidence="BIZ_CONFLICT"]');await page.evaluate(()=>window.scrollTo(0,0));await page.waitForTimeout(250);await page.screenshot({path:path.join(out,'11_业务接入后的真实核验.png'),fullPage:true});
  await page.click('#journey-handoff');await page.waitForFunction(()=>document.querySelector('#contract-json').textContent.includes('approval_decision'));
  const h=JSON.parse(await page.locator('#contract-json').innerText());assert.equal(h.bank_connected,false);assert.equal(h.approval_decision,null);assert.equal(h.application_context.application_id,'D02');assert.equal(h.application_context.is_latest_run,true);checks.push('业务案例入口→真实既有运行→原文对照→拟议结果包预览，未新增模型测量');
  await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(out,'12_拟议回传结果.png'),fullPage:true});
  await page.click('[data-view="ecosystem-view"]');await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(out,'13_蓝色业务协同.png'),fullPage:true});
  for(const width of [1440,1024,768,390]){
   await page.setViewportSize({width,height:950});
   for(const view of ['business-view','workbench-view','deployment-view']){
    await page.click('[data-view="'+view+'"]');await page.evaluate(()=>window.scrollTo(0,0));assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,view+' '+width);
    if(width===390)await page.screenshot({path:path.join(out,'14_'+view+'_手机.png'),fullPage:true});
   }
  }
  checks.push('新增入口、业务阶段条和接入说明在四个宽度无溢出');assert.deepEqual(errors,[]);await fs.writeFile(path.join(out,'business_entry_acceptance.json'),JSON.stringify({passed:true,date:new Date().toISOString(),checks,errors},null,2));console.log(JSON.stringify({passed:true,checks,errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
