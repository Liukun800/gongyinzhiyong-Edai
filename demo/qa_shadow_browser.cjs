const { chromium } = require('C:/Users/liuko/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const page=await browser.newPage({viewport:{width:1440,height:1050}});
  page.setDefaultTimeout(120000);
  const errors=[], checks=[];
  let edited=false;
  page.on('pageerror',e=>errors.push(e.message));
  const base='http://127.0.0.1:8767';
  async function getDetail(){return await (await fetch(base+'/api/cases/D01')).json();}
  async function run(){const old=await page.locator('#run-select').inputValue();await page.click('#run');await page.waitForFunction(o=>document.querySelector('#run-select').value!==o&&!document.querySelector('#run').disabled,old);return (await getDetail()).runs[0];}
  try{
    await page.goto(base);await page.waitForFunction(()=>!document.querySelector('#run').disabled);
    assert.match(await page.locator('.mode strong').textContent(),/真实模型影子/);
    const first=await run();assert.equal(first.usage.successful_model_requests,2);
    assert.equal(first.usage.simulated_analysis_requests,0);
    assert.ok(first.tasks.every(t=>t.source==='agentjev_public_shadow'));
    assert.equal(await page.locator('.distribution').count(),2);
    checks.push('real CPU results and raw candidate scores rendered');
    await page.click('[data-edit="record"]');
    await page.fill('#document-form textarea','仿真主体A在2026年8月整月停止营业，期间没有开展任何经营活动。');
    await page.click('#document-form button[type="submit"]');
    await page.waitForFunction(()=>!document.querySelector('#document-dialog').open&&!document.querySelector('#run').disabled);edited=true;
    assert.equal(await page.locator('[data-review]:disabled').count(),2);
    const changed=await run();assert.equal(changed.usage.successful_model_requests,2);
    assert.ok(changed.tasks.every(t=>t.source==='agentjev_public_shadow'));
    assert.notDeepEqual(changed.tasks[1].distribution,first.tasks[1].distribution);
    checks.push('edited text triggers actual re-inference, preserves old snapshot');
    assert.ok(changed.tasks.every(t=>['待复核','待人工核实','待补充'].includes(t.status)));
    checks.push('no automatically completed credit task');
    await page.click('[data-evidence="BIZ_CONFLICT"]');
    assert.match(await page.locator('#evidence').textContent(),/停止营业/);
    await page.screenshot({path:path.join(__dirname,'qa/shadow-workstation-desktop.png'),fullPage:true});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await page.screenshot({path:path.join(__dirname,'qa/shadow-workstation-mobile.png'),fullPage:true});
    assert.deepEqual(errors,[]);checks.push('desktop/mobile rendering and evidence display verified');
    const report={passed:true,checks,page_errors:errors,first_run:first.id,changed_run:changed.id,
                  original_distribution:first.tasks[1].distribution,changed_distribution:changed.tasks[1].distribution,
                  scope:'Functional real-model UI checks only, not measured accuracy.'};
    await fs.writeFile(path.join(__dirname,'qa/shadow-browser-results.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report,null,2));
  }finally{
    if(edited){const c=(await getDetail()).case;const health=await (await fetch(base+'/api/health')).json();await fetch(base+'/api/cases/D01/reset',{method:'POST',headers:{'Content-Type':'application/json','X-Demo-Token':health.csrf_token},body:JSON.stringify({revision:c.revision})});}
    await browser.close();
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
