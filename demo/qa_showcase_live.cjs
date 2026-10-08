const {chromium}=require('C:/Users/liuko/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const out=path.join(__dirname,'..','评审整改','PM12_Demo业务展示升级_20261002','qa');await fs.mkdir(out,{recursive:true});
 const url='http://127.0.0.1:8767';const health=await(await fetch(url+'/api/health')).json();assert.equal(health.model_loaded,true);delete health.csrf_token;
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});const errors=[],runs=[];
 try{
  const page=await browser.newPage({viewport:{width:1536,height:1024},deviceScaleFactor:1.25});page.setDefaultTimeout(120000);page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url+'/?view=workbench');await page.waitForFunction(()=>!document.querySelector('#run').disabled);
  assert.match(await page.locator('.mode strong').innerText(),/本地真实推理/);
  await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(out,'05_真实模型首页.png')});
  for(const id of ['D03','D02']){
   await page.click('[data-scenario="'+id+'"]');await page.waitForFunction(id=>document.querySelector('#case-title').textContent.startsWith(id)&&!document.querySelector('#run').disabled,id);
   const response=page.waitForResponse(r=>r.url().endsWith('/api/cases/'+id+'/run')&&r.request().method()==='POST',{timeout:180000});await page.click('#run');const run=await(await response).json();assert.equal(run.adapter,'agentjev_public_shadow');assert.equal(run.usage.failed_model_requests,0);assert.equal(run.usage.actual_complex_model_requests,0);assert.equal(run.usage.generated_tokens,0);runs.push(run);
   await page.waitForFunction(()=>!document.querySelector('#run').disabled&&document.querySelectorAll('.task').length===2);
   if(id==='D03'){assert.equal(run.usage.actual_model_requests,1);assert.equal(run.tasks.find(t=>t.id==='USE_MATCH').source,'input_rule');}
   else{assert.equal(run.usage.actual_model_requests,2);await page.click('[data-evidence="BIZ_CONFLICT"]');assert.equal(await page.locator('#evidence .evidence-card').count(),2);}
   if(!await page.locator('#exit-focus').isVisible())await page.click('#focus-workbench');await page.evaluate(()=>window.scrollTo(0,0));await page.waitForTimeout(300);await page.screenshot({path:path.join(out,'06_真实核验_'+id+'.png'),fullPage:true});
   if(await page.locator('#exit-focus').isVisible())await page.click('#exit-focus');
  }
  await page.click('[data-view="deployment-view"]');assert.match(await page.locator('#local-fast-state').innerText(),/已加载本地/);await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(out,'07_本机模型身份.png'),fullPage:true});
  await page.click('[data-view="workbench-view"]');await page.click('#focus-workbench');await page.setViewportSize({width:390,height:844});await page.evaluate(()=>window.scrollTo(0,0));assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({path:path.join(out,'08_真实核验_手机.png'),fullPage:true});
  assert.deepEqual(errors,[]);await fs.writeFile(path.join(out,'live_inference.json'),JSON.stringify({completed:true,kind:'two_existing_synthetic_cases_engineering_smoke_not_benchmark',date:new Date().toISOString(),health,runs,errors},null,2));
  console.log(JSON.stringify({completed:true,runs:runs.map(r=>({case_id:r.case_id,usage:r.usage,answers:r.tasks.map(t=>({task:t.id,answer:t.answer,source:t.source,action:t.action}))})),errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
