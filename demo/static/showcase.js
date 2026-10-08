'use strict';
// Presentation only: never replaces predictions, applies thresholds, or submits reviews.
const showcaseIcons=['▦','☷','◇','▥','⇄'];
document.querySelectorAll('.product-tabs button').forEach((b,i)=>{b.dataset.symbol=showcaseIcons[i];});
$('.product-tabs').insertAdjacentHTML('afterbegin','<div class="side-brand"><div class="brand-mark" aria-hidden="true"><i></i><i></i><i></i><i></i></div><strong>工银智涌 e贷</strong><span>CREDIT REVIEW WORKSPACE</span></div><div class="nav-caption">贷前材料核验</div>');
$('.product-tabs').insertAdjacentHTML('beforeend','<button data-view="deployment-view" data-symbol="◫" aria-selected="false">本地模型与接入</button><div class="side-foot"><strong>数字金融 · 竞赛原型</strong>材料归集之后<br>综合审查之前</div>');
document.querySelector('[data-view="deployment-view"]').addEventListener('click',()=>productView('deployment-view'));
$('#workbench-view').insertAdjacentHTML('afterbegin',`
<section class="showcase-hero" aria-label="项目价值总览">
 <div><div class="hero-kicker">JEV-STYLE JUDGMENT / EVIDENCE-FIRST REVIEW</div><h2>把材料中的疑点，<br>变成<em>有依据的待办。</em></h2><p class="hero-copy">为工小审拟配置前置核验组件：先检查材料条件，再完成有限语义判断，将原文、疑点与处理建议一起交给审查人员。</p><div class="hero-actions"><button class="primary" id="enter-review">开始演示 <span aria-hidden="true">→</span></button><small>2 类任务 · 原文可回看 · 复核有记录</small></div></div>
 <div class="hero-map" aria-label="规则预检、快判断、按需慢分析、人员复核的方案结构图"><div class="map-context"><span>面向工小审的适配设计</span><span>任务级协同</span></div><div class="map-input">申请材料 → 完整性 / 主体 / 期间预检</div><div class="map-connector"></div><div class="map-core"><div class="map-node fast"><strong>Jev式快判断</strong><span>有限选项 · 结构化输出</span></div><div class="map-link">→<small>按需</small></div><div class="map-node"><strong>慢思考协同</strong><span>复杂关系 · 深入分析</span></div></div><div class="map-connector"></div><div class="map-output">核验建议 + 原文依据 + 待处理事项 → 人员复核</div></div>
</section>
<section class="value-row" aria-label="业务价值与可演示能力">
 <article class="value-card"><div class="value-icon" aria-hidden="true">⌕</div><div><h3>原文并排看</h3><p>将申请、证明与陈述带回同一核验任务，减少反复翻找材料。</p></div></article>
 <article class="value-card"><div class="value-icon" aria-hidden="true">⑂</div><div><h3>任务按需分流</h3><p>规则处理缺项，快模型判断语义，复杂分析仅在条件触发时调用。</p></div></article>
 <article class="value-card"><div class="value-icon" aria-hidden="true">⇥</div><div><h3>结果成包交接</h3><p>汇总建议、证据与复核记录，以拟议结果包承接现有评审流程。</p></div></article>
</section>
<section class="scenario-selector" aria-label="演示情形"><span>选择材料情形</span><button class="scenario-chip" data-scenario="D01" aria-pressed="true">01 常规材料</button><button class="scenario-chip" data-scenario="D02" aria-pressed="false">02 冲突陈述</button><button class="scenario-chip" data-scenario="D03" aria-pressed="false">03 材料缺项</button><button class="scenario-chip" data-scenario="D04" aria-pressed="false">04 跨期材料</button><button class="scenario-chip" data-scenario="D05" aria-pressed="false">05 补充协议</button><button class="scenario-chip" data-scenario="D06" aria-pressed="false">06 接管演示</button><button id="focus-workbench" aria-pressed="false">聚焦核验</button></section>`);
$('main').insertAdjacentHTML('beforeend',`
<section id="deployment-view" class="product-view" hidden>
 <div class="hero-kicker">LOCAL INFERENCE / WORKFLOW ADAPTATION</div><h2>本地运行，与业务流程衔接</h2><p class="deployment-lead">当前原型用社区 Jev-like 模型承载有限判断。模型负责提供候选答案，应用负责材料条件、任务分流、证据记录与人员承接。以下按本次服务实际状态显示。</p>
 <div class="deploy-summary"><article class="deploy-card"><div class="deploy-label">01 / SYSTEM 1</div><h3>社区快判断模型</h3><p class="deploy-model-name" id="local-fast-name">正在读取运行配置</p><p>首期运行 Choice 类任务：用途一致性、经营陈述矛盾。Score / Noul 作为扩展接口研究，不展示为已落地信贷能力。</p><span class="deploy-state" id="local-fast-state">等待服务信息</span></article><article class="deploy-card"><div class="deploy-label">02 / SYSTEM 2</div><h3>按需复杂分析</h3><p class="deploy-model-name" id="local-slow-name">正在读取运行配置</p><p>通过输入检查、仍需复杂分析的任务才进入升级条件；明确矛盾交由人员核实，材料不足不能由模型补造事实。</p><span class="deploy-state" id="local-slow-state">等待服务信息</span></article><article class="deploy-card"><div class="deploy-label">03 / BUSINESS HANDOFF</div><h3>拟协同工小审</h3><p>接收材料片段与任务上下文，返回辅助建议、出处与未解决事项；后续综合审查与授信授权仍由原业务流程承接。</p><span class="deploy-state">当前为本地结果包</span></article></div>
 <section class="product-section"><h3>嵌入位置：材料归集之后，综合审查之前</h3><div class="deployment-flow"><div><strong>材料归集</strong><p>申请、订单、说明与经营记录</p></div><b aria-hidden="true">→</b><div><strong>本项目核验组件</strong><p>规则 → 快判断 → 按需慢分析 → 人员处理</p></div><b aria-hidden="true">→</b><div><strong>工小审拟议协同位置</strong><p>带原文依据的核验结果与待办</p></div><b aria-hidden="true">→</b><div><strong>现有评审流程</strong><p>综合审查、授权审批与后续办理</p></div></div><p>图中银行侧连接为方案设计；实际接口、授权和部署需按银行要求验证。</p></section>
 <section class="product-section"><h3>本机模型身份与调用口径</h3><div id="deployment-runtime" class="mode-detail">正在读取服务信息。</div><p>安装官方 SDK 只代表拥有客户端。官方模型、社区模型及其部署许可需要分别核实，不能把社区本地推理称为官方 Jev 私有化部署。</p><p>本地权重来源与版本见项目模型清单。现有公开 AgentJev 权重原任务为代码完成判断，中文信贷适配和分数校准仍需专项验证。</p></section>
 <section class="product-section"><h3>由演示走向银行验证</h3><div class="deployment-flow"><div><strong>当前：本地仿真演示</strong><p>两项任务、可编辑原文、真实调用及结果留痕</p></div><b aria-hidden="true">→</b><div><strong>下一步：领域离线验证</strong><p>可信标签、强对照、校准与完整开销测量</p></div><b aria-hidden="true">→</b><div><strong>再推进：受控辅助试点</strong><p>环境与接口适配、权限、人工承接及回滚验收</p></div></div></section>
</section>`);
$('main').appendChild($('main>footer'));
$('#enter-review').addEventListener('click',()=>{$('.toolbar').scrollIntoView({behavior:'smooth',block:'start'});$('#case-select').focus({preventScroll:true});});
$('#focus-workbench').addEventListener('click',()=>setFocus(true));
$('.toolbar').insertAdjacentHTML('beforeend','<button id="exit-focus" hidden>返回全景</button>');
$('#exit-focus').addEventListener('click',()=>setFocus(false));
function setFocus(on){document.body.classList.toggle('focus-mode',on);$('#focus-workbench').setAttribute('aria-pressed',String(on));$('#exit-focus').hidden=!on;window.scrollTo({top:0,behavior:'smooth'});}
document.querySelectorAll('[data-scenario]').forEach(b=>b.addEventListener('click',()=>{if(busy)return;$('#case-select').value=b.dataset.scenario;$('#case-select').dispatchEvent(new Event('change'));}));
function updateDeployment(){const h=runtimeHealth;if(!h)return;const m=h.model,dual=!!m?.dual_system,upstream=['upstream_http','versioned_local_http'].includes(m?.backend);$('#local-fast-name').textContent=m?.name||'流程模拟 · 不调用模型';$('#local-fast-state').textContent=m?(upstream?'已配置判断服务 · 运行失败转人工':'已加载本地 CPU 权重'):'当前服务未加载模型';$('#local-slow-name').textContent=dual?m.slow_model.name:'本模式未启用真实慢模型';$('#local-slow-state').textContent=dual?'本地通用模型实验替代':'可另启双系统实验服务';$('#deployment-runtime').textContent=m?'当前模式：'+(dual?'真实快慢协同实验':'真实模型影子')+'；快模型：'+m.name+'；版本：'+(m.revision||'由上游服务声明')+'。所有输出保持人工复核；当前版本不自动完成核验。':'当前为流程模拟，结果来自预设样例，真实模型调用数为0。可使用 start_shadow.ps1 启动本地真实判断服务。';if(!dual){const card=document.querySelector('#ecosystem-view .product-grid article:last-child p');card.textContent='复杂分析协同目标。当前模式未启用真实复杂分析；双系统实验可使用本地通用生成模型，银行连接保持拟议设计。';}else{document.querySelector('#ecosystem-view .product-grid article:last-child p').textContent='复杂分析协同目标。当前双系统使用本地通用模型作为实验替代，工银智涌连接仍为拟议设计。';}}
let displayedContext='';
function renderShowcase(){if(!detail)return;document.querySelectorAll('[data-scenario]').forEach(b=>{b.setAttribute('aria-pressed',String(b.dataset.scenario===active));b.disabled=busy;});$('#focus-workbench').disabled=busy;const r=run(),dual=r?.adapter==='jev_dual_experiment'||runtimeHealth?.model?.dual_system;
 $('#run').textContent=busy?'正在核验…':dual?'运行快慢协同实验':realMode?'运行本地真实核验':'运行流程演示';
 if(realMode&&['D05','D06'].includes(active)){$('#case-description').textContent=dual?'本地快模型先判断，满足实验条件时才调用本地慢模型；运行结果保留原文和人员处理路径。':'本地快模型判断含补充协议的材料，保留结构化建议和原文；当前模式不调用慢模型。';}
 if(realMode){document.querySelector('[data-scenario="D06"]').textContent='06 多材料判断';}
 $('#scenario-guide').textContent=active==='D05'||active==='D06'?(dual?'先观察快模型实际结果，再核对是否触发慢分析。调用失败同样如实保留，不以模拟成功替代。':realMode?'本情形在快判断模式中真实运行；复杂分支与故障注入仅在对应模式展示。':scenarioGuides[active]):scenarioGuides[active]||'自建仿真材料：核对主体、期间与相关原文后运行。';
 const key=active+'|'+runId+'|'+detail.case.revision;if(key!==displayedContext){$('#contract-json').textContent='';displayedContext=key;}
 if(r){const rule=r.tasks.filter(t=>t.source==='input_rule').length;const simulation=r.adapter==='fixture_simulator';let el=$('#route-benefit');if(!el){$('#route-trace').insertAdjacentHTML('afterend','<p id="route-benefit" class="trace-note"></p>');el=$('#route-benefit');}el.textContent=simulation?'本次为预设流程演示。真实模型调用为0，不计为节约量。':`本次处理记录：${rule} 项由输入规则直接处理；快判断请求 ${r.usage.actual_model_requests} 次；慢分析请求 ${r.usage.actual_complex_model_requests||0} 次。调用数是运行事实，成本与质量增益另行对照。`;if(!current())el.textContent='历史运行｜'+el.textContent;}
 else if($('#route-benefit'))$('#route-benefit').remove();
 updateDeployment();
}
window.addEventListener('case-rendered',renderShowcase);
window.addEventListener('health-ready',updateDeployment);
if(detail)renderShowcase();

// Business case precedes the interactive workbench; official facts and design remain distinct.
document.querySelector('.nav-caption').insertAdjacentHTML('afterend','<button data-view="business-view" data-symbol="◈" aria-selected="false">价值与接入场景</button>');
document.querySelector('[data-view="business-view"]').addEventListener('click',()=>productView('business-view'));
$('main').insertAdjacentHTML('afterbegin',`
<section id="business-view" class="product-view" hidden>
 <section class="business-hero"><div class="hero-kicker">DIGITAL FINANCE / BUSINESS CASE</div><h2>让成熟的信贷 AI 能力，<br><em>匹配更精细的任务分工。</em></h2><p>以工小审相关材料审查任务为拟议切入点，把高频、有限答案的核验拆成可执行任务：先检查、再判断、按需深入分析，最后带着证据回到评审流程。</p><div class="hero-actions"><button class="primary" id="business-start">进入业务演示 →</button><span class="business-tag">贷前材料核验 · 数字金融</span></div></section>
 <div class="section-heading"><span>01 / 已有基础</span><h2>工行已经具备什么能力？</h2><p>依据工行公开披露说明业务语境；内部调用链不作推定。</p></div>
 <div class="official-grid"><article><div class="evidence-label">官方披露 · 2026年8月28日</div><h3>工银智涌</h3><p>工行持续完善大模型技术体系，已在多个业务领域落地600余个场景。</p><a href="https://www.bj.icbc.com.cn/page/1267851085701156864.html" target="_blank" rel="noopener noreferrer">2026年上半年经营情况 [1] ↗</a></article><article><div class="evidence-label">官方披露 · 2026年8月28日</div><h3>工小审</h3><p>工行持续升级信贷评审AI数字助手。项目从材料审查中的具体判断任务寻找拟协同位置。</p><a href="https://www.bj.icbc.com.cn/page/1267851085701156864.html" target="_blank" rel="noopener noreferrer">现有助手持续升级 [1] ↗</a></article><article><div class="evidence-label">官方披露 · 分期口径</div><h3>融资全流程智能体矩阵</h3><p>2026年一季度公告使用“智贷通”，半年公告使用“智融通”。本 Demo 以融资全流程业务语境为上游，不假定名称间的内部系统对应关系。</p><a href="https://www.icbc.com.cn/page/1223260226921385984.html" target="_blank" rel="noopener noreferrer">一季度公告 [2] ↗</a><a href="https://www.bj.icbc.com.cn/page/1267851085701156864.html" target="_blank" rel="noopener noreferrer">半年公告 [1] ↗</a></article></div>
 <div class="section-heading"><span>02 / 介入依据</span><h2>同一份材料，不同任务需要不同能力。</h2><p>以一笔仿真小微经营贷款申请为例，区分确定规则、语义核验和复杂分析。</p></div>
 <section class="business-scenario"><div class="scenario-brief"><span>本项目首期场景</span><h3>采购流动资金<br>贷前材料核验</h3><p>申请用途、采购订单、经营陈述与经营记录进入工作台。使用者是材料核验与信贷审查人员；输出由后续评审流程承接。</p><small>所有示例为自编仿真；不对应工行内部已确认流程。</small></div><div class="task-ladder"><article><b>规则处理</b><div><strong>材料齐了吗？主体、期间能比较吗？</strong><p>确定性条件先检查，缺项形成补件或口径核实事项。</p></div></article><article><b>Jev式判断</b><div><strong>用途与订单一致吗？经营陈述相互矛盾吗？</strong><p>从有限候选中输出结构化建议，保留原文供人员核对。</p></div></article><article><b>按需慢分析</b><div><strong>材料充分，但多份更正与关系仍待澄清？</strong><p>满足实验升级条件时再分析；明确矛盾直接交人工核实。</p></div></article></div></section>
 <div class="section-heading"><span>03 / 为什么采用Jev式判断</span><h2>把有限判断直接变成可承接的任务信号。</h2><p>这是可验证的设计假设；同底座分类与约束生成同样应纳入对照。</p></div>
 <section class="product-section value-matrix"><div class="status-table"><table><thead><tr><th>业务问题</th><th>可选处理方式</th><th>本方案的设计</th><th>需要验证的优势</th></tr></thead><tbody><tr><td>确定缺项、主体和期间</td><td>规则检查</td><td>保留规则，先做可判定检查</td><td>避免不必要的模型请求</td></tr><tr><td>有限选项的语义核验</td><td>分类器、受限生成或决策模型</td><td>Jev式候选判断，答案直接映射任务动作</td><td>同等质量下的时延与完整开销</td></tr><tr><td>复杂关系与综合说明</td><td>生成式模型与人工分析</td><td>按条件升级，保留原始快判断和失败接管</td><td>升级是否有质量增益，是否值得增加成本</td></tr><tr><td>结论核实与结果交接</td><td>人员结合原文处理</td><td>答案、原文、版本和人员依据成包保留</td><td>查证工作量、证据正确性和处理闭环质量</td></tr></tbody></table></div><p class="matrix-note">这张表比较可选设计路径，不描述工行当前的全部内部实现。结构化输出能力也并非Jev独有。</p></section>
 <div class="section-heading"><span>04 / 看得见的闭环</span><h2>从上游材料，到带依据的审查待办。</h2><p>以下是拟议介入后的业务演示路径，银行侧输入与回传以本地数据包模拟。</p></div>
 <div class="business-flow"><article><span>01</span><h3>上游材料归集</h3><p>仿真申请与原文材料</p></article><b>→</b><article class="engine-stage"><span>02 · 本项目</span><h3>材料核验组件</h3><p>规则 → 快判断 → 按需慢分析</p></article><b>→</b><article><span>03</span><h3>审查人员处理</h3><p>核对证据、补件或更正</p></article><b>→</b><article><span>04</span><h3>拟议工小审回传</h3><p>核验建议 + 证据 + 待办</p></article></div>
 <div class="demo-entry-row"><button data-start-scenario="D03"><strong>演示 A · 缺件闭环</strong><span>发现缺项 → 补件 → 重跑 → 复核</span></button><button data-start-scenario="D02"><strong>演示 B · 矛盾核实</strong><span>真实判断 → 原文对照 → 人员处理</span></button><button data-start-scenario="D05"><strong>演示 C · 复杂关系</strong><span>快判断 → 查看实际升级路径</span></button></div>
 <section class="business-proof"><div><span class="evidence-label">已可演示</span><h3>任务与证据闭环</h3><p>编辑仿真原文、本地真实推理、材料版本失效提醒、人员复核、摘要与结果包导出。</p></div><div><span class="evidence-label">仍需验证</span><h3>增量效果与银行适配</h3><p>历史28例开发诊断中双系统未优于快模型。需继续验证领域质量、校准、完整成本及行内接口适配。</p><button id="business-evidence">查看实验依据 →</button></div></section>
 <details class="source-details"><summary>公开来源与论证边界</summary><p>[1] 工商银行2026年上半年经营情况，公布于2026年8月28日。[2] 工商银行2026年一季度经营情况，公布于2026年4月29日。核查日期：2026年10月2日。</p><p>“600余个场景”是工行全行多个领域的公开口径，不是本项目的覆盖量。公开披露不能证明工行存在全样本大模型调用、固定审批耗时或缺少前置路由，本方案不据此推导75%降本等结论。</p></details>
</section>`);
function openBusinessScenario(id){if(busy||!detail)return;productView('workbench-view');setFocus(true);$('#case-select').value=id;$('#case-select').dispatchEvent(new Event('change'));}
$('#business-start').addEventListener('click',()=>openBusinessScenario('D03'));
document.querySelectorAll('[data-start-scenario]').forEach(b=>b.addEventListener('click',()=>openBusinessScenario(b.dataset.startScenario)));
$('#business-evidence').addEventListener('click',()=>{productView('development-view');window.scrollTo(0,0);});
$('.toolbar').insertAdjacentHTML('beforebegin','<section class="workflow-rail" aria-label="拟议业务接入演示路径"><div><span>01 · 仿真上游</span><strong>材料归集</strong><small id="journey-input">等待材料</small></div><b>→</b><div class="active"><span>02 · 本组件</span><strong>辅助核验</strong><small id="journey-run">等待运行</small></div><b>→</b><button id="journey-review"><span>03 · 人员承接</span><strong>核实与复核</strong><small id="journey-review-state">处理当前任务</small></button><b>→</b><button id="journey-handoff"><span>04 · 拟议回传</span><strong>结果包预览</strong><small>本地预览 / 导出</small></button></section>');
$('#journey-review').addEventListener('click',()=>$('.workspace').scrollIntoView({behavior:'smooth',block:'start'}));
$('#journey-handoff').addEventListener('click',()=>{productView('integration-view');if(run())$('#contract-preview').click();window.scrollTo(0,0);});
window.addEventListener('case-rendered',()=>{
 $('#business-start').disabled=busy||!detail;document.querySelectorAll('[data-start-scenario]').forEach(b=>b.disabled=busy||!detail);
 if(!detail)return;const r=run();$('#journey-input').textContent=detail.case.documents.length+' 份材料 · v'+detail.case.revision;$('#journey-run').textContent=!r?'待运行':current()?'当前版本已核验':'材料已变化 · 待重跑';$('#journey-review-state').textContent=r?r.tasks.filter(t=>!t.review).length+' 项尚无人员记录':'处理当前任务';$('#journey-handoff').disabled=busy||!r;
});
const entryView=new URLSearchParams(location.search).get('view');
productView(entryView&&document.getElementById(entryView+'-view')?entryView+'-view':'business-view');

// PM15: business illustrations explain task relations; they do not assert measured savings.
document.querySelector('#business-view .source-details').insertAdjacentHTML('beforebegin',`
<section class="pm15-gallery"><div class="section-heading"><span>05 / 业务设计图解</span><h2>核验什么，结果交给谁？</h2><p>从材料关系到人员待办，把产品的设计逻辑放回审查工作。</p></div>
<figure><img src="/pm15-relations.svg" alt="用途与经营两项任务的材料比较关系"><figcaption>图解一 · 对齐比较范围，保留答案、成对原文和处理事项。</figcaption></figure>
<figure><img src="/pm15-handoff.svg" alt="核验事项包的输入、证据、待办与后续评审承接"><figcaption>图解二 · 项目提出的协同设计；结果交接保留人员处理与既有授权流程。</figcaption></figure></section>`);
