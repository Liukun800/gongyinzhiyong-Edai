'use strict';
// Loaded only by the opt-in official workbench; existing modes stay untouched.
sourceNames.typesafe_official_jev = 'TypeSafe官方 Jev · 结构化判断';
const baseMessage = message;
message = function (text, error = false) {
  if (!error && runtimeHealth?.model?.backend === 'typesafe_official' && text.startsWith('真实模型已加载')) {
    text = runtimeHealth.model.offline_test_mode
      ? '官方接入预览已连接；此入口只读，不产生模型请求。'
      : '官方判断服务已配置；运行核验后按任务记录真实返回。';
  }
  baseMessage(text, error);
};
const baseDeployment = updateDeployment;
updateDeployment = function () {
  baseDeployment();
  const model = runtimeHealth?.model;
  if (model?.backend !== 'typesafe_official') return;
  const preview = model.offline_test_mode;
  $('.mode strong').textContent = preview ? '官方接入预览 · 不调用网络' : '官方 Jev · System 1';
  $('.mode span').textContent = preview ? '界面验收；运行按钮已禁用' : model.revision + ' · 仿真材料核验';
  $('.notice').textContent = preview ? '官方接入界面预览，不产生模型判断或收费请求。' : 'TypeSafe官方结构化判断 · 自编仿真材料 · 原文证据与人员复核在工作台承接。';
  if (preview) $('#run').disabled = true;
  if (!busy) $('#run').textContent = preview ? '接入预览' : '运行官方 Jev 核验';
  const connectionNote = $('#message');
  if (connectionNote && preview) connectionNote.textContent = '官方接入预览已连接；此入口只读，不产生模型请求。';
  $('#deployment-view .deployment-lead').textContent = '官方 Jev 承担用途一致性与经营陈述矛盾的限定判断；工作台检查材料条件、呈现原文、保留版本，并交接人员处理。';
  $('#deployment-view .deploy-card h3').textContent = '官方 Jev 判断服务';
  $('#local-fast-state').textContent = preview ? '接入预览 · 网络关闭' : '官方API · 按任务记录真实返回';
  $('#deployment-runtime').textContent = '判断后端：TypeSafe官方 ' + model.revision + '；候选概率和服务置信度分开保留，全部建议由人员复核。';
  const originNote = document.querySelectorAll('#deployment-view .product-section')[1]?.querySelector('p:last-child');
  if (originNote) originNote.textContent = '官方服务通过state与Choice问题适配业务；中文领域质量、误报漏识别和完整成本以同任务实验评价。';
};
const baseShowcase = renderShowcase;
renderShowcase = function () {
  baseShowcase();
  if (runtimeHealth?.model?.backend !== 'typesafe_official') return;
  updateDeployment();
  const preview = runtimeHealth.model.offline_test_mode;
  if (!busy) $('#run').textContent = preview ? '接入预览' : '运行官方 Jev 核验';
  if (preview) $('#run').disabled = true;
  if (realMode && ['D05', 'D06'].includes(active)) $('#case-description').textContent = '官方Jev判断当前仿真材料；复杂事项与原文证据交人员处理。';
  const result = run();
  const metricsLabel = $('#metrics .metric:nth-child(2) span');
  if (metricsLabel) metricsLabel.textContent = '真实判断任务请求';
  if (result?.adapter !== 'typesafe_official_jev') return;
  const usage = result.usage;
  const benefit = $('#route-benefit');
  if (benefit) benefit.textContent = '本次官方任务尝试 ' + usage.official_task_attempts + ' 次；成功返回输入 ' + usage.official_input_tokens + '、结构化输出 ' + usage.official_output_tokens + ' Token；失败消耗另核。';
  for (const task of result.tasks) {
    const cards = Array.from(document.querySelectorAll('.task'));
    const card = cards.find(item => item.querySelector('h3')?.textContent === task.name);
    const meta = card?.querySelector('.meta-content');
    if (!meta || !task.decision_record || meta.querySelector('.official-identity')) continue;
    const text = document.createElement('div');
    text.className = 'official-identity';
    const record = task.decision_record;
    text.textContent = '官方模型：' + record.official_model + '；服务置信度：' + record.service_confidence + '；输入/结构化输出Token：' + record.official_usage.input_tokens + '/' + record.official_usage.output_tokens;
    meta.appendChild(text);
  }
};
window.addEventListener('health-ready', () => queueMicrotask(updateDeployment));

// Shortcuts keep the official demonstration focused on business paths.
function addDemoShortcuts() {
  if (document.querySelector('.official-demo-shortcuts')) return;
  const toolbar = document.querySelector('.toolbar');
  if (!toolbar) return;
  const wrap = document.createElement('div');
  wrap.className = 'official-demo-shortcuts';
  wrap.innerHTML = '<span class="shortcut-label">一键填充演示路径</span>' +
    '<button type="button" data-demo-case="D01">材料一致</button>' +
    '<button type="button" data-demo-case="D02">明确矛盾</button>' +
    '<button type="button" data-demo-case="D03">缺件补充</button>' +
    '<span class="shortcut-tip">均为脱敏仿真材料；运行后仍需人工复核</span>';
  toolbar.parentNode.insertBefore(wrap, toolbar.nextSibling);
  wrap.addEventListener('click', (event) => {
    const button = event.target.closest('[data-demo-case]');
    if (!button || button.disabled) return;
    const select = document.querySelector('#case-select');
    if (!select) return;
    select.value = button.dataset.demoCase;
    select.dispatchEvent(new Event('change', {bubbles: true}));
    const guide = document.querySelector('#scenario-guide');
    if (guide) guide.textContent = button.dataset.demoCase === 'D03'
      ? '已填充缺件路径：先运行查看补件提示，再点击“补入演示采购订单”，重新运行观察版本变化。'
      : '已填充完整材料：点击“运行官方 Jev 核验”，查看候选判断、原文证据和人工复核入口。';
  });
}
window.addEventListener('health-ready', () => queueMicrotask(addDemoShortcuts));

function addIntakePresets() {
  if (document.querySelector('.official-intake-presets')) return;
  const form = document.querySelector('#intake-form');
  if (!form) return;
  const anchor = form.querySelector('.intake-materials');
  if (!anchor) return;
  const bar = document.createElement('div');
  bar.className = 'official-intake-presets';
  bar.innerHTML = '<strong>不想逐项填写？</strong><button type="button" data-intake-preset="consistent">填充一致案例</button><button type="button" data-intake-preset="conflict">填充矛盾案例</button><button type="button" data-intake-preset="missing">填充缺件案例</button><span>仅生成脱敏仿真文字</span>';
  anchor.parentNode.insertBefore(bar, anchor);
  const values = {
    consistent: ['材料一致演示申请','用途与经营材料可比且相互支持','仿真主体A','2026-08','采购生产用钢材','订单关联申请，采购标的为生产用钢材','2026年8月全月正常营业','2026年8月全月持续营业'],
    conflict: ['经营矛盾演示申请','同主体同期间陈述存在互斥信息','仿真主体A','2026-08','采购生产用钢材','订单关联申请，采购标的为生产用钢材','2026年8月全月正常营业','2026年8月整月停业'],
    missing: ['缺件补充演示申请','用途说明已有但缺少采购证明材料','仿真主体A','2026-08','采购生产用钢材','','','']
  };
  bar.addEventListener('click', event => {
    const key = event.target.closest('[data-intake-preset]')?.dataset.intakePreset;
    if (!key) return;
    const v = values[key];
    ['title','description','subject','period','purpose','support','statement','record'].forEach((name,i) => { form.elements[name].value = v[i]; });
    form.elements.synthetic.checked = true;
    const error = document.querySelector('#intake-error');
    if (error) error.textContent = '已填充演示材料，可直接创建申请。';
  });
}
window.addEventListener('health-ready', () => queueMicrotask(addIntakePresets));
new MutationObserver(() => {
  if (runtimeHealth?.model?.offline_test_mode && !$('#run').disabled) $('#run').disabled = true;
}).observe($('#run'), { attributes: true, attributeFilter: ['disabled'] });
