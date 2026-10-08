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
new MutationObserver(() => {
  if (runtimeHealth?.model?.offline_test_mode && !$('#run').disabled) $('#run').disabled = true;
}).observe($('#run'), { attributes: true, attributeFilter: ['disabled'] });
