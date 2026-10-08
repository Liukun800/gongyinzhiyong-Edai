"""Derive evidence from saved predictions without changing models or labels."""
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'评审整改交付版/图文增强与痛点完善_20261008'
KIT=OUT/'评审补证材料'
PM19=ROOT/'评审整改/PM19_领域适配与同任务对照_20261006'
CONFLICT={'存在明确矛盾','发现明确矛盾'}

def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def csv_write(path,headers,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(headers);w.writerows(rows)

def main():
    KIT.mkdir(parents=True,exist_ok=True)
    sources=[ROOT/'评审整改/实验结果/holdout_dual.json',
             ROOT/'评审整改/实验结果/holdout_slow.json',
             ROOT/'demo/experiments/review_holdout_v1/labels.sealed.json',
             PM19/'summary.json',PM19/'逐例同任务对照.csv',
             ROOT/'评审整改/PM12_Demo业务展示升级_20261002/sources/工行公开来源.json']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in sources}
    dual,slow,labels,latest=map(load,[sources[0],sources[1],sources[2],sources[3]])
    expected={r['id']:r['answer'] for r in labels}
    assert len(expected)==28 and len(dual['rows'])==28
    transitions=[]
    for r in dual['rows']:
        task=r['prediction']['tasks'][0]
        before=task.get('fast_decision',{}).get('answer',task['answer'])
        after=task['answer'];ref=expected[r['case_id']]
        calls=r['prediction']['usage']['actual_complex_model_requests']
        category=('纠错' if before!=ref and after==ref else
                  '新增错误' if before==ref and after!=ref else
                  '正确保持' if before==ref and after==ref else '错误保持')
        transitions.append({'id':r['case_id'],'task':r['task_id'],'reference':ref,
                            'before':before,'after':after,'slow_calls':calls,
                            'transition':category,'routing_reason':task.get('routing_reason',''),
                            'workflow_ms':r['wall_ms']})
    upgraded=[r for r in transitions if r['slow_calls']]
    fast_correct=sum(r['before']==r['reference'] for r in transitions)
    final_correct=sum(r['after']==r['reference'] for r in transitions)
    assert (fast_correct,final_correct,len(upgraded))==(17,15,7)
    buckets={name:[r['id'] for r in upgraded if r['transition']==name]
             for name in ['纠错','新增错误','正确保持','错误保持']}
    csv_write(KIT/'双系统逐例承接与纠错.csv',
              ['案例','任务','项目参考标签（未独立复核）','快判断','最终结果','实际慢调用','配对变化','升级原因','流程耗时毫秒'],
              [[r[k] for k in ['id','task','reference','before','after','slow_calls','transition','routing_reason','workflow_ms']] for r in transitions])
    report={'scope':'历史仿真记录离线重算；标签未独立复核，不新增模型调用',
            'paired_dual':{'n':28,'fast_correct':fast_correct,'final_correct':final_correct,
                           'upgraded':len(upgraded),'buckets':buckets,
                           'net_correct_change':final_correct-fast_correct,
                           'fast_path_retained_wrong':[r['id'] for r in transitions if not r['slow_calls'] and r['before']!=r['reference']]},
            'task_metrics':latest['tasks'],
            'resource_records':{'dual_workflow_sum_seconds':round(sum(r['wall_ms'] for r in dual['rows'])/1000,2),
                                'slow_workflow_sum_seconds':round(sum(r['wall_ms'] for r in slow['rows'])/1000,2),
                                'dual_load_seconds':dual['model']['load_seconds'],
                                'process_total_seconds':dual['process_wall_seconds'],
                                'measurement_scope':'逐例流程耗时合计不含此前模型加载；单次历史运行不作稳定性能基准'},
            'official_domain_batch_available':False,
            'unmeasured':['工小审现有细粒度任务表现','独立业务标签','人员查证工时','完整处理成本','银行信用风险改善'],
            'source_hashes':hashes,'new_official_calls':0}
    assert all(sha(ROOT/p)==h for p,h in hashes.items())
    (KIT/'补证核查.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    # No invented bank capability gap or measured value is entered in these records.
    csv_write(KIT/'工小审同任务增量确认表.csv',
              ['任务','现有处理方式（银行填写）','本项目新增设计','共同比较指标','既有结果','组件结果','业务确认人与日期'],
              [['资金用途一致性','','明确借款资金归属与比较范围；关联成对原文','漏识别、误报、查证工时','','',''],
               ['经营陈述矛盾','','对齐主体、期间、渠道；保留不可比事项','不可比误报、关键漏识别、查证工时','','',''],
               ['材料更新及事项交接','','有效版本绑定、重新核验与未决事项承接','旧结论误用、事项遗漏、返工工时','','','']])
    csv_write(KIT/'快慢协同验收登记.csv',
              ['核验任务','复杂关系定义','材料条件','候选升级条件','关键错误上限（业务确认）','冻结版本','新资料结果','采用决定'],
              [['用途一致性','资金分摊、指代或跨材料关系','充分、可比、有原文','经独立验证的任务条件','','','',''],
               ['经营陈述矛盾','多期间、多渠道或跨主体关系','充分、可比、有原文','经独立验证的任务条件','','','','']])
    csv_write(KIT/'完整收益同任务测量.csv',
              ['匿名任务编号','路径','材料版本','模型及路由版本','核验结果','原文支持裁定','模型用量','失败重试费用','人员操作秒','外部等待秒','部署维护分摊','完整费用','端到端响应毫秒','测量人员与日期'],[])
    lines=['# 评审补证核查与采用依据','',
           '本材料依据已保存的开发预测及工行公开来源离线整理，不更改原实验、标签或默认模型。','',
           '## 工小审协同必要性','',
           '工行公开公告确认工小审为信贷评审AI数字助手，公开描述不能确定其两项具体核验任务的覆盖、耗时和错误分布。产品增量以同任务比较为依据：既有处理方式与增加本组件的方式使用相同材料、输出要求和人员责任。仅在核验质量、查证工时或完整资源成本获得可重复改善时采用；能力重复且无收益时复用既有能力。','',
           '## 历史双系统配对重算','',
           f'28份仿真中快判断参考一致{fast_correct}/28，最终{final_correct}/28，升级{len(upgraded)}份。',
           '| 升级结果 | 数量 | 案例 |','|---|---:|---|']
    lines += [f'| {k} | {len(v)} | {"、".join(v) or "无"} |' for k,v in buckets.items()]
    lines += ['',f'净变化{final_correct-fast_correct}份。未升级的错误项：'+ '、'.join(report['paired_dual']['fast_path_retained_wrong'])+'。',
              '这证明当前具体模型和路由未形成协同质量增量；不能据此外推官方Jev或工银智涌的表现。阈值0.8是历史工程实验配置，未校准，不作为业务采用门槛。','',
              '## 完整收益评价','',
              '成本比较纳入共同材料准备、快慢调用、失败、人员查证与纠正、部署维护分摊。人员工时与实际调用量分别计量，不以模型错误数量推定工作时间。风险评价先报告材料核验的漏检与误报，信贷不良率、违约率和损失改善需另有跟踪数据。',
              '银行受控比较采用相同核验任务、质量要求及材料版本；记录有效操作时间、外部等待、端到端系统响应和完整费用。当前相关实测字段保持空白。','',
              '## 待取得的关键证据','',
              '1. 银行填写现有任务覆盖、结果与增量确认表。',
              '2. 独立复核人员裁定标签；冻结新资料、模型和路由后进行同任务评价。',
              '3. 在获准环境完成同质量工时、响应及完整成本测量。',
              '4. 官方47条领域对照当前无run结果；沿用既有PM21入口，不重复已完成的两例。','',
              'CSV是采集与验收材料，不是已实施或已测得的结果。']
    (KIT/'评审补证核查与采用依据.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'paired_dual':report['paired_dual'],'resource_records':report['resource_records'],
                      'task_metrics':{t:{k:{s:v[s] for s in ['n','semantic_n','semantic_correct','conflict_n','conflict_nonidentification','false_conflicts']} for k,v in systems.items() if k in ['jev_frozen','jev_head_adapted']} for t,systems in latest['tasks'].items()}},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
