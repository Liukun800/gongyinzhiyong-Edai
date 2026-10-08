const {chromium}=require('C:/Users/liuko/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto('http://127.0.0.1:8767');
    await page.waitForFunction(()=>!document.querySelector('#run').disabled);
    await page.selectOption('#case-select','D02');
    await page.waitForFunction(()=>document.querySelector('#case-title').textContent.startsWith('D02')&&!document.querySelector('#run').disabled);
    await page.click('[data-review="BIZ_CONFLICT"]');
    assert.match(await page.locator('#review-current').textContent(),/原始判断：.*当前判断：.*当前状态：/);
    const reviewState=await page.locator('#review-form').evaluate(f=>({text:document.querySelector('#review-current').textContent,confirmDisabled:f.elements.action.querySelector('[value="confirm"]').disabled,action:f.elements.action.value}));
    console.log(JSON.stringify(reviewState));
    assert.equal(reviewState.confirmDisabled,true);
    await page.screenshot({path:path.join(__dirname,'qa/review-dialog-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    const box=await page.locator('#review-dialog').boundingBox();
    assert.ok(box.x>=0&&box.x+box.width<=390&&box.y>=0&&box.y+box.height<=844);
    await page.screenshot({path:path.join(__dirname,'qa/review-dialog-mobile.png'),fullPage:true});
    assert.deepEqual(errors,[]);
    await fs.writeFile(path.join(__dirname,'qa/review-readonly-results.json'),JSON.stringify({passed:true,checks:['original and effective answer separated','incomplete task cannot be confirmed','desktop/mobile dialog fits','no page errors'],mutations:0},null,2));
    console.log('Read-only review dialog checks passed; no workstation records changed.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
