"""Project-owned proposed handoff schema; never sends to bank systems."""
import hashlib
import json
from pathlib import Path
SCHEMA_VERSION='jev-gxs-proposal/1.0'
CONFLICTS={'存在明确矛盾','发现明确矛盾'}
INCOMPLETE={'信息不足','无法比较'}
RESOLVED_STATES={'人工复核完成','人工核实已记录','人工纠正已记录'}
def build_handoff(detail, run_id=None):
 runs=detail['runs'];selected=next((r for r in runs if r['id']==run_id),None) if run_id else (runs[0] if runs else None)
 if not selected:raise ValueError('请先运行核验，或选择存在的运行记录')
 case=detail['case'];current=selected['revision']==case['revision'] and selected['id']==runs[0]['id'];results=[];unresolved=[]
 for t in selected['tasks']:
  review=t.get('review');answer=review.get('answer') if review else t.get('answer');status=review.get('status') if review else t['status']
  issues=[]
  if answer in CONFLICTS:issues.append('存在明确矛盾，仍需原有业务流程处理')
  if answer is None or answer in INCOMPLETE:issues.append('信息或比较条件不足')
  if not review or status not in RESOLVED_STATES:issues.append('人员复核未闭环')
  if not current:issues.append('历史结果，不适用于当前版本')
  if issues:unresolved.append({'task_id':t['id'],'reasons':issues})
  results.append({'task_id':t['id'],'task_name':t['name'],'original_answer':t.get('answer'),'effective_answer':answer,'raw_score':t.get('score'),'calibration':t.get('calibration'),'result_source':t.get('source'),'route_action':t['action'],'status':status,'evidence':t.get('evidence',[]),'evidence_support_status':'requires_human_review','manual_review':review,'fast_decision':t.get('fast_decision'),'analysis':t.get('analysis'),'unresolved_reasons':issues})
 for task,result in zip(selected['tasks'],results):
  if 'decision_record' in task:result['decision_record']=task['decision_record']
 materials=selected['material_snapshot'];fingerprint=hashlib.sha256(json.dumps(materials,ensure_ascii=False,sort_keys=True).encode('utf-8')).hexdigest()
 return {'schema_version':SCHEMA_VERSION,'contract_status':'project_proposal_not_bank_api','bank_connected':False,'destination_proposal':'工小审审查任务复核位置（拟议）','application_context':{'application_id':case['id'],'title':case['title'],'material_revision':selected['revision'],'current_revision':case['revision'],'is_latest_run':current},'input_snapshot':{'materials':materials,'sha256':fingerprint},'decision_results':results,'handoff_status':'待处理事项已整理' if unresolved else '本项辅助核验复核已记录','unresolved_tasks':unresolved,'approval_decision':None,'loan_amount':None,'interest_rate':None,'disbursement_instruction':None,'audit':{'run_id':selected['id'],'created_at':selected['created_at'],'mode':selected['mode'],'model':selected.get('model'),'usage':selected.get('usage',{}),'operator_authentication':'local_demo_only'},'scope':'供本地演示和接口讨论，不发送到银行，不构成授信审批。历史导出始终使用当次材料快照。'}
def _legacy_development_summary(root):
 p=Path(root)/'experiments/results/development_comparison.json';d=json.loads(p.read_text(encoding='utf-8'));systems=[]
 for name,system in d['systems'].items():
  s=system['summary']['all'];rows=system['rows'];systems.append({'id':name,'n':s['n'],'agreement':s['correct'],'disagreement':sum(r['predicted'] is not None and not r['correct'] for r in rows),'abstained':sum(r['predicted'] is None for r in rows),'semantic_agreement':s['semantic_correct'],'semantic_n':s['semantic_n']})
 ar=d['systems']['agentjev_public_same_route']['rows']
 return {'scope':'仿真开发诊断，不是独立测试或工行生产效果','source_created_at':d['created_at'],'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'model':d['model'],'systems':systems,'actions':{k:sum(r['action']==k for r in ar) for k in ['supplement','review','human']},'errors':[{k:r[k] for k in ['case_id','task_id','expected','predicted','action']} for r in ar if not r['correct']],'automatic_completion':0,'actual_complex_requests':0,'prepared_development_pool':54,'evaluated_cases':24,'limitations':['TF-IDF每折只有10份训练材料','未完成信贷微调和独立校准','新增30份仅已准备，未重新评测','没有真实慢模型对照或收益测量']}

def development_summary(root):
 result=_legacy_development_summary(root)
 revision=Path(root).parent/'评审整改/R02_开发重测摘要.json'
 if revision.exists():
  latest=json.loads(revision.read_text(encoding='utf-8'))
  if latest.get('status')=='completed':
   result['remediation']={**latest,'scope':'同一24份已见开发材料重测，非独立泛化测试',
                          'source_file':str(revision),'sha256':hashlib.sha256(revision.read_bytes()).hexdigest(),
                          'decision':'保留轻量路由修复；当前慢模型未带来质量改善，仅作显式实验选项'}
 challenge=Path(root).parent/'评审整改/实验结果/冻结挑战汇总.json'
 if challenge.exists():
  source=json.loads(challenge.read_text(encoding='utf-8'))
  result['frozen_challenge']={'scope':source['scope'],'systems':{k:v['metrics'] for k,v in source['systems'].items()},
                            'sha256':hashlib.sha256(challenge.read_bytes()).hexdigest(),
                            'limitations':source['limitations']}
 return result

