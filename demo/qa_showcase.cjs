const {chromium}=require('C:/Users/liuko/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
(async()=>{
 const out=path.join(__dirname,'..','评审整改','PM12_Demo业务展示升级_20261002','qa');await fs.mkdir(out,{recursive:true});
 const tmp=await fs.mkdtemp(path.join(os.tmpdir(),'jev-pm12-'));
 const server=spawn('C:/Users/liuko/AppData/Local/Programs/Python/Python313/python.exe',[path.join(__dirname,'app.py'),'--port','8782','--db',path.join(tmp,'pm12.sqlite3')],{cwd:__dirname,stdio:'pipe'});
 const checks=[],errors=[];let browser;
 try{
  for(let i=0;i<80;i++){try{if((await fetch('http://127.0.0.1:8782/api/health')).ok)break;}catch{}await new Promise(r=>setTimeout(r,200));}
  browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1.5});page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8782/?view=workbench');await page.waitForFunction(()=>!document.querySelector('#run').disabled);
  assert.match(await page.locator('header').innerText(),/基于Jev式判断与快慢协同的贷前材料核验引擎/);
  await page.screenshot({path:path.join(out,'01_首页_桌面.png')});
  await page.click('[data-scenario="D03"]');await page.waitForFunction(()=>document.querySelector('#case-title').textContent.startsWith('D03')&&!document.querySelector('#run').disabled);
  await page.click('#run');await page.waitForFunction(()=>document.querySelectorAll('.task').length===2&&!document.querySelector('#run').disabled);
  assert.match(await page.locator('#tasks').innerText(),/待补充/);assert.match(await page.locator('#route-benefit').innerText(),/真实模型调用为0/);
  await page.click('#focus-workbench');assert.equal(await page.locator('.showcase-hero').isVisible(),false);
  await page.evaluate(()=>window.scrollTo(0,0));await page.waitForTimeout(250);await page.screenshot({path:path.join(out,'02_补件闭环_聚焦.png'),fullPage:true});
  await page.click('#demo-supplement');await page.waitForFunction(()=>document.querySelector('#revision').textContent.includes('v2')&&!document.querySelector('#run').disabled);
  assert.match(await page.locator('#trace-caption').innerText(),/历史/);
  await page.click('#run');await page.waitForFunction(()=>document.querySelector('#trace-caption').textContent.includes('当前有效')&&!document.querySelector('#run').disabled);
  await page.click('[data-evidence="USE_MATCH"]');await page.locator('[data-locate="order"]').click();assert.equal(await page.locator('[data-document="order"]').evaluate(e=>e.classList.contains('located')),true);
  await page.click('[data-review="USE_MATCH"]');await page.fill('#review-form [name="reason"]','已比对当前材料版本中的申请用途与采购订单原文，记录演示复核。');await page.click('#review-form [type="submit"]');await page.waitForFunction(()=>!document.querySelector('#review-dialog').open&&!document.querySelector('#run').disabled);
  await page.click('[data-review="BIZ_CONFLICT"]');await page.fill('#review-form [name="reason"]','已比对同主体同期间经营陈述原文，记录演示复核。');await page.click('#review-form [type="submit"]');await page.waitForFunction(()=>!document.querySelector('#review-dialog').open&&!document.querySelector('#run').disabled);
  await page.click('#report');await page.waitForSelector('#report-dialog[open]');assert.match(await page.locator('#report-body').innerText(),/辅助核验/);await page.locator('#report-dialog').screenshot({path:path.join(out,'03_核验摘要.png')});await page.click('[data-close="report-dialog"]');
  await page.click('[data-view="integration-view"]');await page.click('#contract-preview');await page.waitForFunction(()=>document.querySelector('#contract-json').textContent.includes('approval_decision'));
  const handoff=JSON.parse(await page.locator('#contract-json').innerText());assert.equal(handoff.bank_connected,false);assert.equal(handoff.approval_decision,null);assert.equal(handoff.decision_results.length,2);assert.equal(handoff.unresolved_tasks.length,0);
  const dl=page.waitForEvent('download');await page.click('#contract-export');await(await dl).saveAs(path.join(out,'已复核辅助核验结果包.json'));
  checks.push('补件→新版本→重跑→原文定位→两项人工复核→摘要/结果包导出闭环');
  await page.click('[data-view="workbench-view"]');await page.click('#exit-focus');await page.click('[data-scenario="D05"]');await page.waitForFunction(()=>document.querySelector('#case-title').textContent.startsWith('D05')&&!document.querySelector('#run').disabled);assert.equal(await page.locator('#contract-json').innerText(),'');
  await page.click('#run');await page.waitForFunction(()=>document.querySelectorAll('.task').length===2&&!document.querySelector('#run').disabled);assert.match(await page.locator('#route-trace').innerText(),/复杂分析（模拟）/);
  await page.click('[data-scenario="D06"]');await page.waitForFunction(()=>document.querySelector('#case-title').textContent.startsWith('D06')&&!document.querySelector('#run').disabled);await page.click('#run');await page.waitForFunction(()=>document.querySelectorAll('.task').length===2&&!document.querySelector('#run').disabled);assert.match(await page.locator('#tasks').innerText(),/模拟超时/);
  checks.push('模拟复杂分析与故障清楚标识；切换申请清除旧对接预览');
  await page.click('[data-view="deployment-view"]');assert.match(await page.locator('#local-fast-state').innerText(),/未加载模型/);
  await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(out,'04_本地部署与业务位置.png'),fullPage:true});
  for(const width of [1440,1024,768,390]){
   await page.setViewportSize({width,height:950});
   for(const view of ['workbench-view','queue-view','ecosystem-view','development-view','integration-view','deployment-view','business-view']){
    await page.click('[data-view="'+view+'"]');await page.waitForTimeout(150);await page.evaluate(()=>window.scrollTo(0,0));
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow '+view+' '+width);
    if(width===1440||width===390)await page.screenshot({path:path.join(out,view+'-'+width+'.png'),fullPage:true});
   }
  }
  checks.push('七视图在1440/1024/768/390像素宽度无页面横向溢出');assert.deepEqual(errors,[]);
  await fs.writeFile(path.join(out,'browser_acceptance.json'),JSON.stringify({passed:true,date:new Date().toISOString(),checks,errors},null,2));console.log(JSON.stringify({passed:true,checks,errors}));
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
