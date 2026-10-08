"""Contrastive development data and label-separated training exports, not model training."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import ANSWERS
from shadow_engine import QUESTIONS, model_state, route_answer, task_documents, input_guard
from vendor.agentjev.contract import prepare

HERE = Path(__file__).resolve().parent
OUT = HERE / 'domain_dev_v2'


def build_contrasts():
    cases, labels = [], []

    def family(name, lineage, task, anchor, variants, focus, parents, metadata=None):
        for i, (answer, text, reason) in enumerate(variants, 1):
            key = f'{name}-{i}'
            texts = [anchor, text]
            docs = [{'id': f'm{j+1}', 'title': f'材料{j+1}',
                     'kind': 'purpose' if task == 'USE_MATCH' else 'business',
                     'subject': '仿真主体甲', 'period': '2026-08',
                     'paragraphs': [{'id': 'p1', 'text': t}]} for j,t in enumerate(texts)]
            if metadata:
                for doc, fields in zip(docs, metadata.get(i, [{}, {}])):
                    doc.update(fields)
            cases.append({'id': key, 'revision': 1, 'task_id': task, 'documents': docs})
            labels.append({'id': key, 'task_id': task, 'answer': answer,
                           'family': name, 'lineage_group': lineage, 'parent_ids': parents,
                           'contrast_focus': focus, 'split': 'development_only',
                           'rationale': reason, 'expected_action': route_answer(answer)[1],
                           'evidence': [{'document_id':d['id'],'paragraph_id':'p1',
                                         'quote':d['paragraphs'][0]['text']} for d in docs],
                           'label_status':'项目编制的仿真参考标签，未经银行专家独立标注',
                           'provenance':'基于已知开发错误与任务定义编制；不属于独立测试'})

    U, B = 'USE_MATCH', 'BIZ_CONFLICT'
    family('CU1','U_exclusive',U,
           '本申请A拟融资购买面粉原料，申请用途仅限面粉。本次核验对应拟采购合同，不比较历史交易。',[
        ('一致','本文件为申请A的唯一且有效拟采购合同：标的全部为面粉原料，覆盖本申请完整用途。','合同完整支持唯一用途。'),
        ('存在明确矛盾','本文件为申请A的唯一且有效拟采购合同：标的全部为办公电脑，不含面粉，无更正文件。','同一申请的当前拟采购合同与排他用途冲突。'),
        ('信息不足','本文件为申请A的拟采购合同封面：标的明细页缺失，无法从封面判断采购何物。','申请对应明确但缺少标的，不应判为矛盾。')],
        '同一拟采购阶段的标的一致、互斥与未知',['U03','U04'])
    family('CU2','U_direct',U,
           '申请A的全部融资用途是购置仓库用叉车，没有其他用途。',[
        ('一致','申请A对应设备合同：购置仓储搬运叉车，合同覆盖全部申请用途。','同义表达指向同一叉车用途。'),
        ('存在明确矛盾','申请A对应唯一设备合同：只购置冷藏柜，明确不购置叉车；无更正。','当前唯一合同与排他用途相反。'),
        ('信息不足','申请A对应设备合同：只写仓库设备，附件未提供，无法确定具体设备是否为叉车。','上位概念不足以确认具体设备。')],
        '同义设备名、排他异类与过宽名称',['U02'])
    family('CU3','U_revision',U,
           '申请A当前仅拟采购铜材。唯一原订单标的是切割设备；如有有效更正，则以更正后的订单为准。',[
        ('一致','申请A的更正协议已签署并生效：原订单切割设备全部改为铜材，原标的条款失效。','按明确题设，生效更正解除原用途冲突。'),
        ('存在明确矛盾','申请A的更正协议尚未签署且未生效：拟把切割设备改为铜材，当前原订单仍有效。','未生效建议不能解除当前有效订单冲突。'),
        ('信息不足','申请A有一份拟把设备改为铜材的更正协议，但签署页及生效条款缺失，现有材料无法判断哪个版本有效。','有效版本不确定，不能自行认定草案生效或无效。')],
        '更正已生效、明确未生效与有效性未知',['U07','U08'])
    family('CU4','U_link',U,
           '本次只核验申请A，其全部用途为购买服装面料。另有独立申请B，不纳入本次核验。',[
        ('一致','本有效订单仅对应申请A，完整标的为服装面料，覆盖申请A全部用途。','同一申请且完整支持用途。'),
        ('存在明确矛盾','本唯一有效订单仅对应申请A，完整标的为装修材料，不含服装面料；无更正。','申请对应正确，唯一有效标的与用途冲突。'),
        ('信息不足','本有效订单仅对应申请B，完整标的为服装面料；明确不对应申请A，未提供A的订单。','相同商品不能替代申请对应关系。')],
        '申请对应与标的两个条件必须同时检查',['U11','U12'])
    family('CU5','U_scope',U,
           '申请A仅拟采购面粉和食用油，需核验两类货物的完整用途。',[
        ('一致','申请A有效采购明细完整列出面粉和食用油，明确覆盖申请A所有采购项目。','两类用途完整覆盖。'),
        ('存在明确矛盾','申请A唯一且完整有效采购明细只包含办公家具，明确没有面粉和食用油，无其他订单或更正。','完整且排他明细与两类申请用途均冲突。'),
        ('信息不足','申请A仅提交面粉订单，食用油订单待补；现有订单只说明部分采购，没有否定食用油用途。','部分覆盖不等于排他矛盾。')],
        '完整覆盖、完整冲突与部分覆盖',['U09','U10'])
    family('CB1','B_consistent',B,
           '仿真主体甲2026年8月整个自然月均未营业，没有任何经营活动。',[
        ('未发现明确矛盾','仿真主体甲2026年8月整月闭店，期间没有开展经营。','两个否定经营状态相容，不因停业词判矛盾。'),
        ('发现明确矛盾','仿真主体甲2026年8月每天均正常营业，整个自然月没有闭店日。','相同整月的营业与不营业互斥。'),
        ('无法比较','仿真主体甲只报告2026年7月整月营业，未提供2026年8月的对应经营记录。','第二份正文描述其他期间，登记字段不能替代正文。')],
        '停业词不是矛盾标签；正文期间须校验',['B02'])
    family('CB2','B_opposed',B,
           '仿真主体甲2026年8月全月正常营业，期间没有停业。',[
        ('未发现明确矛盾','仿真主体甲2026年8月持续营业，未发生暂停经营。','否定停业与正常营业相容。'),
        ('发现明确矛盾','仿真主体甲2026年8月全月未营业，期间未开展经营。','同一期间全月营业与全月未营业冲突。'),
        ('无法比较','仿真主体甲2026年8月只提交经营记录封面，营业状态及日期明细全部缺失。','有文件但没有可比陈述，不能仅按文件数量视为充分。')],
        '否定范围与存在文件但缺少内容',['B03','B04','D02'])
    family('CB3','B_scope',B,
           '仿真主体甲2026年8月生产线停工，但零售门店全月正常营业；两者是不同经营范围。',[
        ('未发现明确矛盾','仿真主体甲2026年8月零售门店全月未停业，生产线整月没有生产。','不同范围的状态分别相容。'),
        ('发现明确矛盾','仿真主体甲2026年8月同一零售门店整月闭店，没有任何营业日；本条仅描述该门店。','第二份明确限定相同门店，存在冲突。'),
        ('无法比较','仿真主体甲2026年8月某经营单元停工，但记录未标明是生产线还是零售门店。','经营范围无法对应，不强判矛盾或一致。')],
        '范围不同与范围未知不得混同',['B09','B10'])
    family('CB4','B_correction',B,
           '仿真主体甲2026年8月原说明记为全月营业，另一份当前记录为整月停业。现需结合更正状态判断。',[
        ('未发现明确矛盾','原说明已有效更正为2026年8月整月停业，原全月营业陈述明确作废；另一记录保持整月停业。','有效更正解除冲突。'),
        ('发现明确矛盾','将原全月营业说明改为停业的申请已被撤回，没有生效更正；原说明和整月停业记录均仍有效。','没有有效更正，相反陈述仍冲突。'),
        ('无法比较','更正资料缺少确认页，无法确定原营业说明是否已作废；当前有效版本无法确定。','不能自行为不明版本设定效力。')],
        '更正有效性决定哪些陈述可以比较',['B11','B12'])
    family('CB5','B_period',B,
           '仿真主体甲2026年8月全月停业，本说明不描述7月或其他主体。',[
        ('未发现明确矛盾','仿真主体甲2026年8月整月未经营，整个自然月闭店。','同期间相同状态。'),
        ('发现明确矛盾','仿真主体甲2026年8月全月正常经营，没有停业日。','同期间相反状态。'),
        ('无法比较','仿真主体甲2026年7月全月正常经营，没有停业日。','日期变化不直接构成矛盾。')],
        '期间相同后才判断内容冲突',['B05','B06'],
        metadata={3:[{}, {'period':'2026-07'}]})
    return cases, labels


def build_bundle():
    original_manifest=json.loads((HERE/'dataset_manifest.json').read_text(encoding='utf-8'))
    for name,digest in original_manifest['hashes'].items():
        if hashlib.sha256((HERE/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Original development data changed')
    old_cases=json.loads((HERE/'development_cases.json').read_text(encoding='utf-8'))
    old_labels=json.loads((HERE/'development_labels.json').read_text(encoding='utf-8'))
    cases,labels=build_contrasts()
    for label in old_labels:
        label['lineage_group']=label['family']
        label['parent_ids']=[]
    all_cases=old_cases+cases
    all_labels=old_labels+labels
    lookup={a['id']:a for a in all_labels}
    exports,decisions=[],[]
    for case in all_cases:
        annotation=lookup[case['id']]
        task=case['task_id']; documents=task_documents(case,task)
        request={'state':model_state(documents),'questions':[{
            'id':'decision','type':'choice','question':QUESTIONS[task], 'options':ANSWERS[task]}]}
        prepare(request)  # Validate against the inference contract, not the upstream training script.
        target={'answer':annotation['answer'],'candidate_index':ANSWERS[task].index(annotation['answer'])}
        exports.append({'record_id':case['id'],'task_id':task,'lineage_group':annotation['lineage_group'],
                        'usage':'development_only','request':request,'target':target})
        guard=input_guard(documents,task)
        decisions.append({'id':case['id'],'task_id':task,'lineage_group':annotation['lineage_group'],
                          'input_rule_answer':guard[0] if guard else None,
                          'semantic_training_eligible':guard is None})
    # Development-only folds. Parent and descendant cases are never split across a fold.
    folds=[]
    for task in ANSWERS:
        subset=[c for c in all_cases if c['task_id']==task]
        for group in sorted({lookup[c['id']]['lineage_group'] for c in subset}):
            train=[c['id'] for c in subset if lookup[c['id']]['lineage_group']!=group]
            validation=[c['id'] for c in subset if lookup[c['id']]['lineage_group']==group]
            folds.append({'task_id':task,'validation_lineage_group':group,'train_ids':train,
                          'validation_ids':validation,'scope':'development diagnostic only'})
    return cases,labels,all_cases,all_labels,exports,decisions,folds


def write():
    cases,labels,all_cases,all_labels,exports,decisions,folds=build_bundle()
    OUT.mkdir(exist_ok=True)
    files={'contrast_cases.json':cases,'contrast_labels.json':labels,
           'combined_cases.json':all_cases,'combined_labels.json':all_labels,
           'eligibility.json':decisions,'development_folds.json':folds}
    for name,body in files.items():
        (OUT/name).write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    catalog=['# 30份成组对比材料审阅册','',
             '用途：开发标注审阅。所有主体与材料均为仿真；不是银行客户材料，不是最终测试集。',
             '每组三份材料包，共用首份材料，改变第二份材料中的关键条件。标签为项目参考，待独立审核。','']
    for case,label in zip(cases,labels):
        catalog.extend([f"## {case['id']}｜{label['answer']}",'',
                        f"比较重点：{label['contrast_focus']}",''])
        for d in case['documents']:
            catalog.extend([f"{d['title']}（{d['subject']}；登记期间{d['period']}）：",'',
                            d['paragraphs'][0]['text'],''])
        catalog.extend([f"参考依据：{label['rationale']}",
                        f"处理动作：{route_answer(label['answer'])[0]}；派生组：{label['lineage_group']}。",''])
    (OUT/'30份成组对比材料审阅册.md').write_text('\n'.join(catalog),encoding='utf-8')
    name='training_records.jsonl'
    (OUT/name).write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in exports),encoding='utf-8')
    manifest={'version':'domain-dev-v2','status':'training_data_preparation_only',
              'original_count':24,'new_count':30,'combined_count':54,
              'contrast_families':10,'lineage_groups':len({a['lineage_group'] for a in all_labels}),
              'label_counts_by_task':{task:dict(Counter(a['answer'] for a in all_labels if a['task_id']==task)) for task in ANSWERS},
              'semantic_eligible':sum(d['semantic_training_eligible'] for d in decisions),
              'no_final_test_set':True,'expert_labels':False,'model_training_performed':False,
              'schema':'project-local request + separate target; not claimed compatible with upstream train loader',
              'hashes':{name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in [*files,'training_records.jsonl']}}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k!='hashes'},ensure_ascii=False,indent=2))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    write()
