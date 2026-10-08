"""Unseal project labels only after all frozen prediction runs have completed."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT.parent/'评审整改/实验结果'
CONFLICT={'存在明确矛盾','发现明确矛盾'}


def summarize():
    reports={name:json.loads((OUT/f'holdout_{name}.json').read_text(encoding='utf-8')) for name in ['encoder','dual','slow']}
    if any(r['status']!='completed' for r in reports.values()):raise RuntimeError('Incomplete prediction run')
    label_path=ROOT/'experiments/review_holdout_v1/labels.sealed.json'
    labels={r['id']:r for r in json.loads(label_path.read_text(encoding='utf-8'))}
    systems={}
    for name in ['encoder','fast','dual','slow']:
        report=reports['dual' if name=='fast' else name];rows=[]
        for r in report['rows']:
            p=r['prediction'];task=p['tasks'][0] if name in ('fast','dual') else p
            result=task.get('fast_decision',task) if name=='fast' else task
            answer=result['answer'];gold=labels[r['case_id']]
            source=result['source'];action=task['action']
            if name=='fast' and 'fast_decision' in task:
                action='review' if answer in ('一致','未发现明确矛盾') else 'human'
            rows.append({'case_id':r['case_id'],'task_id':r['task_id'],'expected':gold['answer'],
                         'answer':answer,'correct':answer==gold['answer'],'action':action,'source':source})
        if {r['case_id'] for r in rows}!=set(labels):raise RuntimeError('Mismatched case IDs')
        semantic=[r for r in rows if r['source']!='input_rule']
        conflicts=[r for r in rows if r['expected'] in CONFLICT]
        metrics={'n':len(rows),'correct':sum(r['correct'] for r in rows),'semantic_n':len(semantic),
                 'semantic_correct':sum(r['correct'] for r in semantic),'reference_conflicts':len(conflicts),
                 'conflict_misses':sum(r['answer'] not in CONFLICT for r in conflicts),
                 'conflict_false_positives':sum(r['answer'] in CONFLICT and r['expected'] not in CONFLICT for r in rows),
                 'invalid_or_no_answer':sum(r['answer'] is None for r in rows),
                 'conflict_sent_to_supplement':sum(r['expected'] in CONFLICT and r['action']=='supplement' for r in rows),
                 'auto_completed':0,'requires_personnel':len(rows)}
        if name=='dual':
            metrics.update(actual_slow_requests=sum(r['prediction']['usage']['actual_complex_model_requests'] for r in report['rows']),
                failed_slow_requests=sum(r['prediction']['usage']['failed_complex_model_requests'] for r in report['rows']),
                prompt_tokens=sum(r['prediction']['usage']['complex_prompt_tokens'] for r in report['rows']),
                completion_tokens=sum(r['prediction']['usage']['complex_completion_tokens'] for r in report['rows']))
        elif name=='slow':
            metrics.update(actual_slow_requests=sum(r['prediction']['actual_complex_model_requests'] for r in report['rows']),
                failed_slow_requests=sum(r['prediction']['source']=='complex_model_error' for r in report['rows']),
                prompt_tokens=sum(r['prediction'].get('usage',{}).get('prompt_tokens',0) for r in report['rows']),
                completion_tokens=sum(r['prediction'].get('usage',{}).get('completion_tokens',0) for r in report['rows']))
        if name!='fast':metrics['observed_wall_seconds']=round(sum(r['wall_ms'] for r in report['rows'])/1000,2)
        systems[name]={'metrics':metrics,'rows':rows}
    c,e=systems['slow']['metrics'],systems['dual']['metrics']
    quality=(e['conflict_misses']<=c['conflict_misses'] and e['correct']>=c['correct'] and
             e['conflict_sent_to_supplement']<=c['conflict_sent_to_supplement'])
    summary={'scope':'28份项目自编冻结仿真挑战；标签尚未独立业务复核，不代表银行泛化或生产效果',
        'systems':systems,'label_sha256':hashlib.sha256(label_path.read_bytes()).hexdigest(),
        'prediction_file_hashes':{k:hashlib.sha256((OUT/f'holdout_{k}.json').read_bytes()).hexdigest() for k in reports},
        'same_quality_screen_passed':quality,
        'resource_comparison':{'slow_calls_baseline':c['actual_slow_requests'],'slow_calls_dual':e['actual_slow_requests'],
            'call_reduction_fraction':1-e['actual_slow_requests']/c['actual_slow_requests'] if c['actual_slow_requests'] else None,
            'verified_cost_savings':None,'bank_approval_speedup':None},
        'limitations':['项目自编标签，不具独立业务复核证据','没有信贷领域微调和校准','0.80为工程阈值',
            'CPU运行存在严重启动/调度停顿，时延仅记录，不作为容量或审批时效证据',
            'fast列来自真实双系统运行内的原始快判断，不是另外运行的完整服务','全部任务保留人员处理，不能证明人工复核减少']}
    (OUT/'冻结挑战汇总.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v['metrics'] for k,v in systems.items()},ensure_ascii=False,indent=2))
    print('same_quality_screen_passed',quality)


if __name__=='__main__':summarize()
