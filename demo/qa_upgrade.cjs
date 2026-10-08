const {chromium}=require('C:/Users/liuko/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const out=process.env.JEV_QA_OUT||path.join(__dirname,'qa','upgrade');await fs.mkdir(out,{recursive:true});
 const tmp=await fs.mkdtemp(path.join(os.tmpdir(),'jev-upgrade-'));
 const server=spawn('C:/Users/liuko/AppData/Local/Programs/Python/Python313/python.exe',[path.join(__dirname,'app.py'),'--port','8780','--db',path.join(tmp,'browser.sqlite3')],{cwd:__dirname,stdio:'pipe'});
 let browser;const errors=[];const checks=[];
 try {
  for(let i=0;i<60;i++){try{if((await fetch('http://127.0.0.1:8780/api/health')).ok)break;}catch{}await new Promise(r=>setTimeout(r,200));}
  browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const page=await browser.newPage({viewport:{width:1440,height:1100},deviceScaleFactor:1.5});
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8780/?view=workbench');await page.waitForFunction(()=>!document.querySelector('#new-case').disabled);
  await page.click('#new-case');
  const vals={title:'新增申请完整流程验证',description:'用途和经营材料的仿真核验',subject:'仿真主体甲',period:'2026-08',purpose:'申请资金用于采购生产用铜材。',support:'采购订单标的是生产用铜材。',statement:'本期持续正常生产。',record:'本期生产记录显示持续正常生产。'};
  for(const [k,v] of Object.entries(vals))await page.fill('#intake-form [name="'+k+'"]',v);
  await page.check('#intake-form [name="synthetic"]');await page.locator('#intake-dialog').screenshot({path:path.join(out,'intake.png')});
  await page.click('#intake-form [type="submit"]');await page.waitForFunction(()=>!document.querySelector('#intake-dialog').open&&!document.querySelector('#run').disabled);
  const id=await page.locator('#case-select').inputValue();assert.match(id,/^S-/);
  await page.click('#run');await page.waitForFunction(()=>document.querySelectorAll('.task').length===2&&!document.querySelector('#run').disabled);
  assert.match(await page.locator('#tasks').innerText(),/未形成判断/);checks.push('New synthetic intake is persisted; flow mode does not invent predictions');
  for(const [task,answer] of [['USE_MATCH','一致'],['BIZ_CONFLICT','未发现明确矛盾']]){
    await page.click('[data-review="'+task+'"]');await page.selectOption('#review-form [name="action"]','resolve');
    await page.selectOption('#review-form [name="answer"]',answer);await page.fill('#review-form [name="reason"]','已逐项比对当前版本仿真原文并记录核实结果。');
    await page.click('#review-form [type="submit"]');await page.waitForFunction(()=>!document.querySelector('#review-dialog').open&&!document.querySelector('#run').disabled);
  }
  await page.click('[data-view="queue-view"]');await page.waitForFunction(()=>document.querySelector('#queue-items').textContent.includes('辅助核验已复核'));
  await page.selectOption('#queue-filter','辅助核验已复核');await page.waitForFunction(()=>document.querySelectorAll('#queue-items tbody tr').length===1);
  await page.click('[data-open-case="'+id+'"]');await page.waitForFunction(()=>!document.querySelector('#run').disabled);
  await page.click('[data-edit="purpose"]');await page.fill('#document-form [name="text"]','补充说明：申请资金仍用于采购生产用铜材。');await page.click('#document-form [type="submit"]');
  await page.waitForFunction(()=>document.querySelector('#revision').textContent.includes('v2')&&!document.querySelector('#run').disabled);
  await page.click('[data-view="queue-view"]');await page.selectOption('#queue-filter','待重跑');await page.waitForFunction(()=>document.querySelector('#queue-items').textContent.includes('新增申请完整流程验证'));
  checks.push('Manual review closes the task; material revision invalidates prior run and moves queue to rerun');
  await page.selectOption('#queue-filter','');await page.waitForFunction(()=>document.querySelectorAll('#queue-items tbody tr').length===7);
  await page.locator('#queue-view').screenshot({path:path.join(out,'queue.png')});
  await page.click('[data-view="workbench-view"]');await page.selectOption('#case-select','D01');await page.waitForFunction(()=>!document.querySelector('#run').disabled);await page.click('#run');await page.waitForFunction(()=>document.querySelectorAll('.route-row').length===2&&!document.querySelector('#run').disabled);
  await page.locator('.workspace').screenshot({path:path.join(out,'workbench.png')});
  await page.click('[data-view="integration-view"]');await page.click('#contract-preview');await page.waitForFunction(()=>document.querySelector('#contract-json').textContent.includes('bank_connected'));
  const handoff=JSON.parse(await page.locator('#contract-json').innerText());assert.equal(handoff.approval_decision,null);assert.equal(handoff.bank_connected,false);
  const pending=page.waitForEvent('download');await page.click('#contract-export');await(await pending).saveAs(path.join(out,'handoff-example.json'));
  checks.push('Result export retains evidence and null credit-approval fields');
  await page.click('[data-view="development-view"]');await page.waitForFunction(()=>document.querySelectorAll('#dev-errors tbody tr').length===7);await page.locator('#development-view').screenshot({path:path.join(out,'development.png')});
  for(const size of [{width:1440,height:1100},{width:390,height:844}]){
    await page.setViewportSize(size);
    for(const view of ['workbench-view','queue-view','ecosystem-view','development-view','integration-view']){
      await page.click('[data-view="'+view+'"]');await page.waitForTimeout(150);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow '+view);
      await page.screenshot({path:path.join(out,view+'-'+size.width+'.png'),fullPage:true});
    }
  }
  assert.deepEqual(errors,[]);checks.push('All five views fit desktop and mobile; no page errors');
  const result={passed:true,checks,errors,date:new Date().toISOString()};await fs.writeFile(path.join(out,'browser-results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 } finally {if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
