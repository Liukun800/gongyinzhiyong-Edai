// Browser acceptance against a disposable database; never changes the user's demo.
const { chromium } = require('C:/Users/liuko/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const { spawn } = require('node:child_process');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const pause = ms => new Promise(r => setTimeout(r, ms));

(async()=>{
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'jev-browser-'));
  const server = spawn('C:/Users/liuko/AppData/Local/Programs/Python/Python313/python.exe', [path.join(__dirname,'app.py'),'--port','8766','--db',path.join(temp,'test.sqlite3')],{cwd:__dirname,windowsHide:true,stdio:'pipe'});
  let browser, serverErrors=''; server.stderr.on('data',d=>serverErrors+=d.toString());
  const base='http://127.0.0.1:8766', errors=[], results=[];
  async function checkReady(){for(let i=0;i<40;i++){try{if((await fetch(base+'/api/health')).ok)return;}catch{}await pause(150);}throw new Error('Server not ready: '+serverErrors);}
  try{
    await checkReady();
    browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
    const page=await browser.newPage({viewport:{width:1440,height:1050},deviceScaleFactor:1});
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base); await page.waitForFunction(()=>!document.querySelector('#run').disabled);
    const expected={D01:['待复核','待复核'],D02:['待复核','待人工核实'],D03:['待补充','待复核'],D04:['待复核','待补充'],D05:['待复核','待复核'],D06:['待人工核实','待复核']};
    async function selectCase(key){await page.selectOption('#case-select',key);await page.waitForFunction(k=>document.querySelector('#case-title').textContent.startsWith(k)&&!document.querySelector('#run').disabled,key);}
    async function runCase(){const count=await page.locator('#run-select option').count();const old=await page.locator('#run-select').inputValue();await page.click('#run');await page.waitForFunction(o=>document.querySelector('#run-select').value!==o&&!document.querySelector('#run').disabled,old);}
    for(const [key,statuses] of Object.entries(expected)){
      await selectCase(key); await runCase();
      assert.deepEqual(await page.locator('.task .badge').allTextContents(),statuses);
      assert.equal(await page.locator('.task').count(),2);
      const value=await page.evaluate(async key=>(await (await fetch('/api/cases/'+key)).json()).runs[0],key);
      assert.equal(value.usage.actual_model_requests,0);
      results.push(key+' route verified');
    }
    await selectCase('D03'); const original=await page.locator('#run-select').inputValue();
    await page.click('#demo-supplement'); await page.waitForFunction(()=>document.querySelector('#revision').textContent.includes('v2')&&!document.querySelector('#run').disabled);
    assert.equal(await page.locator('[data-review]:disabled').count(),2);
    await runCase(); assert.equal(await page.locator('.task .answer').first().textContent(),'一致');
    await page.selectOption('#run-select',original); assert.equal(await page.locator('[data-review]:disabled').count(),2);
    await page.selectOption('#run-select',{index:0});
    await page.click('[data-review="USE_MATCH"]'); await page.fill('#review-form textarea','已核对用途说明及采购订单，两份仿真材料一致。');
    await page.click('#review-form button[type="submit"]');await page.waitForFunction(()=>!document.querySelector('#review-dialog').open&&!document.querySelector('#run').disabled);
    assert.equal(await page.locator('.task .badge').first().textContent(),'人工复核完成');
    results.push('supplement, historical result protection and manual review verified');
    await selectCase('D01');await page.click('[data-edit="application"]');await page.fill('#document-form textarea','<img src=x onerror="window.__injected=true"> 自定义用途，不能沿用预设答案。');
    await page.click('#document-form button[type="submit"]');await page.waitForFunction(()=>!document.querySelector('#document-dialog').open&&!document.querySelector('#run').disabled);
    await runCase();assert.deepEqual(await page.locator('.task .badge').allTextContents(),['待人工核实','待人工核实']);
    assert.equal(await page.evaluate(()=>window.__injected),undefined);
    results.push('edited input fallback and text escaping verified');
    await page.click('#reset');await page.waitForFunction(()=>document.querySelector('#revision').textContent.includes('v3')&&!document.querySelector('#run').disabled);await runCase();
    assert.equal(await page.locator('.task .answer').first().textContent(),'一致');
    const downloadPromise=page.waitForEvent('download');await page.click('#export');const download=await downloadPromise;assert.ok(download.suggestedFilename().endsWith('.json'));results.push('reset and record export verified');
    await selectCase('D05');await page.click('[data-evidence="USE_MATCH"]');
    await fs.mkdir(path.join(__dirname,'qa'),{recursive:true});
    await page.screenshot({path:path.join(__dirname,'qa/workstation-desktop.png'),fullPage:true});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth),false);
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(__dirname,'qa/workstation-mobile.png'),fullPage:true});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth),false);
    assert.deepEqual(errors,[]);results.push('desktop/mobile layout and no uncaught browser errors verified');
    await fs.writeFile(path.join(__dirname,'qa/browser-results.json'),JSON.stringify({passed:true,checks:results,page_errors:errors},null,2));
    console.log(JSON.stringify({passed:true,checks:results,page_errors:errors},null,2));
  }finally{if(browser)await browser.close();server.kill();await new Promise(r=>server.once('exit',r));await fs.rm(temp,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
