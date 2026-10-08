'use strict';
let queueSequence=0;
async function loadQueue(){
  const seq=++queueSequence;
  try{
    const data=await api('/api/queue');if(seq!==queueSequence)return;
    $('#queue-counts').innerHTML=Object.entries(data.counts).map(([label,n])=>`<div class="queue-count"><strong>${n}</strong><span>${esc(label)}</span></div>`).join('');
    const filter=$('#queue-filter').value;
    const rows=data.items.filter(c=>!filter||c.state===filter);
    $('#queue-items').innerHTML=rows.length?'<table><thead><tr><th>申请</th><th>来源 / 版本</th><th>核验状态</th><th>待处理任务</th><th>操作</th></tr></thead><tbody>'+rows.map(c=>`<tr><td><strong>${esc(c.title)}</strong><br><small>${esc(c.id)}</small></td><td>${c.origin==='custom_intake'?'自建仿真':'预设情形'} · v${c.revision}</td><td>${esc(c.state)}</td><td>${c.unresolved_tasks}</td><td><button data-open-case="${esc(c.id)}">进入工作台</button></td></tr>`).join('')+'</tbody></table>':'<p class="empty">此状态下暂无申请。</p>';
    $('#queue-note').textContent=data.scope;
  }catch(e){$('#queue-note').textContent='队列加载失败：'+e.message;}
}
$('#new-case').addEventListener('click',()=>{
  $('#intake-form').reset();$('#intake-error').textContent='';$('#intake-dialog').showModal();
});
$('#intake-form').addEventListener('submit',e=>{
  e.preventDefault();const f=e.target;
  const configs=[['purpose','用途说明','purpose'],['support','用途证明','purpose'],['statement','经营陈述','business'],['record','经营佐证','business']];
  const documents=configs.filter(([name])=>f.elements[name].value.trim()).map(([id,title,kind])=>({id,title,kind,subject:f.elements.subject.value.trim(),period:f.elements.period.value.trim(),paragraphs:[{id:'p1',text:f.elements[id].value.trim()}]}));
  if(!documents.length){$('#intake-error').textContent='请至少输入一份仿真材料。';return;}
  if(!f.elements.synthetic.checked){$('#intake-error').textContent='请确认仅使用自编仿真材料。';return;}
  action(async()=>{
    try{
      const c=await api('/api/cases',{title:f.elements.title.value.trim(),description:f.elements.description.value.trim(),documents,data_classification:'synthetic'});
      const cases=await api('/api/cases');$('#case-select').innerHTML=cases.map(x=>`<option value="${esc(x.id)}">${esc(x.id)} · ${esc(x.title)}</option>`).join('');
      active=c.id;$('#case-select').value=active;await refresh();$('#intake-dialog').close();productView('workbench-view');
      $('#evidence').innerHTML='<p class="empty">新申请已建立，运行核验后查看原文证据。</p>';
      message('仿真申请已建立并保存。'+(realMode?'可运行真实模型影子核验。':'流程模式下自定义语义交由人工核实。'));
    }catch(err){$('#intake-error').textContent=err.message;throw err;}
  });
});
$('#queue-filter').addEventListener('change',loadQueue);
$('#queue-refresh').addEventListener('click',loadQueue);
document.querySelector('[data-view="queue-view"]').addEventListener('click',loadQueue);
$('#queue-items').addEventListener('click',e=>{const b=e.target.closest('[data-open-case]');if(!b)return;action(async()=>{active=b.dataset.openCase;$('#case-select').value=active;await refresh();productView('workbench-view');$('#evidence').innerHTML='<p class="empty">选择核验任务查看当前运行证据。</p>';});});
window.addEventListener('case-rendered',()=>{if(detail)$('#reset').hidden=detail.case.origin==='custom_intake';if(!$('#queue-view').hidden)loadQueue();});
