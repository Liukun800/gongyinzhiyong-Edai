"""Author-defined synthetic development cases. Not real bank data or a final test set."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import ANSWERS
from shadow_engine import route_answer

OUT = Path(__file__).resolve().parent
cases, labels = [], []


def add(key, family, task, answer, texts, rationale, periods=None, subjects=None):
    kind = 'purpose' if task == 'USE_MATCH' else 'business'
    docs = []
    for i, text in enumerate(texts):
        docs.append({'id': f'm{i+1}', 'title': f'材料{i+1}', 'kind': kind,
                     'subject': subjects[i] if subjects else '仿真主体甲',
                     'period': periods[i] if periods else '2026-08',
                     'paragraphs': [{'id': 'p1', 'text': text}]})
    case = {'id': key, 'revision': 1, 'task_id': task, 'documents': docs}
    cases.append(case)
    labels.append({'id': key, 'task_id': task, 'family': family,
                   'split': 'development_only', 'answer': answer,
                   'expected_action': route_answer(answer)[1], 'rationale': rationale,
                   'evidence': [{'document_id': d['id'], 'paragraph_id': 'p1',
                                 'quote': d['paragraphs'][0]['text']} for d in docs],
                   'label_status': '项目编制的仿真参考标签，未经银行专家独立标注',
                   'provenance': '项目开发合成材料，不来自银行客户或生产系统'})


U, B = 'USE_MATCH', 'BIZ_CONFLICT'
add('U01','U_direct',U,'一致',[
    '申请A的全部借款拟用于购买生产用铝材。',
    '申请A对应采购订单：购买用于生产的铝型材；本订单覆盖申请的全部采购需求。'],
    '同申请、完整覆盖、用途同义；只判断文字一致性。')
add('U02','U_direct',U,'一致',[
    '本次申请资金只用于购置仓库搬运叉车。',
    '对应本次申请的设备合同约定购入一台仓储叉车，无其他采购项目。'],
    '搬运叉车与仓储叉车在给定范围内指同一设备。')
add('U03','U_exclusive',U,'存在明确矛盾',[
    '本次申请的资金全部且仅用于购进面粉原料。',
    '本次申请对应的唯一采购合同标的是办公电脑，不包含面粉，且没有补充协议。'],
    '排他用途与唯一合同标的直接冲突。')
add('U04','U_exclusive',U,'存在明确矛盾',[
    '申请资金只用于购买配送车辆，不用于其他支出。',
    '对应本申请的支出证明记载：全部资金用于门店装修，未购置车辆。'],
    '同一申请资金的全部去向相互排斥。')
add('U05','U_absent',U,'信息不足',[
    '本次申请拟购买冷藏设备，尚未提交合同或订单。'],
    '只有用途说明，没有交叉核验材料。')
add('U06','U_absent',U,'信息不足',[
    '本次借款拟支付生产原料采购款，证明文件后补。'],
    '缺少对应证明，不能编造支持关系。')
add('U07','U_revision',U,'一致',[
    '申请A当前资金用途为购买生产用铜材。',
    '申请A原订单标的为切割设备；双方允许以生效协议更改标的。',
    '双方已签署并生效的更正协议：原订单全部标的改为生产用铜材，原设备条款废止。'],
    '按题设有效更正覆盖旧条款；不据此证明协议真实。')
add('U08','U_revision',U,'存在明确矛盾',[
    '申请A的资金只用于生产用铜材采购。',
    '申请A唯一有效订单：购买切割设备，不含铜材。',
    '改购铜材的补充协议只是未签署草案，当前不生效；原订单继续有效。'],
    '未生效草案不能覆盖有效订单，现有用途仍冲突。')
add('U09','U_scope',U,'信息不足',[
    '本申请购买两类货物：面粉和食用油，需核验完整用途。',
    '对应订单仅记载面粉采购，明确不覆盖食用油，其他证明尚未提交。'],
    '部分支持并非完整支持，也未排除另一类用途。')
add('U10','U_scope',U,'一致',[
    '本申请资金仅用于购买面粉和食用油。',
    '本申请的第一份订单覆盖全部面粉采购，第二份订单覆盖全部食用油采购；两份订单合计覆盖本申请全部用途。'],
    '材料明确说明多订单合计完整覆盖申请用途。')
add('U11','U_link',U,'存在明确矛盾',[
    '申请A仅用于服装面料采购。另有独立申请B用于装修。',
    '本文件明确对应申请A：资金全部支付店面装修，未购买服装面料；申请B未使用本文件。'],
    '对应关系明确为A，不能用B的装修用途解释A冲突。')
add('U12','U_link',U,'信息不足',[
    '申请A拟购买服装面料。另有独立申请B购买服装面料。',
    '本订单仅对应申请B，不对应申请A；申请A尚无对应采购证明。'],
    '货物同名但申请不同，不足以核验A。')

add('B01','B_consistent',B,'未发现明确矛盾',[
    '仿真主体甲2026年8月全月正常营业，没有停业。',
    '仿真主体甲2026年8月持续经营，全月未暂停营业。'],
    '同期间经营状态同义一致。')
add('B02','B_consistent',B,'未发现明确矛盾',[
    '仿真主体甲2026年8月因检修整月停业，没有开展经营活动。',
    '2026年8月仿真主体甲整月未营业，未开展任何经营活动。'],
    '两份材料都描述同一停业状态。')
add('B03','B_opposed',B,'发现明确矛盾',[
    '仿真主体甲在2026年8月全月正常营业，期间未停业。',
    '仿真主体甲在2026年8月整月停业，期间未开展经营。'],
    '来自已暴露D02错误结构的开发回归案例，绝不作未见测试。')
add('B04','B_opposed',B,'发现明确矛盾',[
    '仿真主体甲在2026年8月每一天均对外营业，没有闭店日。',
    '仿真主体甲在2026年8月一天也未营业，整个自然月闭店。'],
    '同一完整期间的全称陈述互相排斥。')
add('B05','B_period',B,'无法比较',[
    '仿真主体甲2026年7月整月停业。',
    '仿真主体甲2026年8月全月正常营业。'],
    '不同月份允许状态变化。',periods=['2026-07','2026-08'])
add('B06','B_period',B,'无法比较',[
    '仿真主体甲2025年度未开展经营。',
    '仿真主体甲2026年度持续经营。'],
    '不同年度不能直接判定矛盾。',periods=['2025','2026'])
add('B07','B_subject',B,'无法比较',[
    '仿真主体甲2026年8月全月营业。',
    '仿真主体乙2026年8月整月停业。'],
    '两家主体不同，营业状态无直接可比性。',subjects=['仿真主体甲','仿真主体乙'])
add('B08','B_subject',B,'无法比较',[
    '仿真主体丙2026年8月没有任何经营活动。',
    '仿真主体丁2026年8月每天均开展经营。'],
    '不同主体的相反陈述不构成同主体矛盾。',subjects=['仿真主体丙','仿真主体丁'])
add('B09','B_scope',B,'未发现明确矛盾',[
    '仿真主体甲2026年8月生产线整月停工，但零售门店全月营业。',
    '仿真主体甲2026年8月零售门店没有停业；本记录不描述生产线。'],
    '经营范围不同，生产线停工不否定门店营业。')
add('B10','B_scope',B,'发现明确矛盾',[
    '仿真主体甲2026年8月唯一零售门店整月关闭，没有一天营业。',
    '仿真主体甲2026年8月同一零售门店每天营业，没有任何闭店日。'],
    '明确限定同一门店和整月，属于可比范围内冲突。')
add('B11','B_correction',B,'未发现明确矛盾',[
    '仿真主体甲2026年8月原说明写整月停业；现经有效更正为全月营业，原停业陈述作废。',
    '仿真主体甲2026年8月全月持续经营，无停业日。'],
    '按题设生效更正后的陈述比较。')
add('B12','B_correction',B,'发现明确矛盾',[
    '仿真主体甲2026年8月全月持续经营。更正申请未经确认，当前说明仍有效。',
    '仿真主体甲2026年8月整月停业，未开展经营；无生效更正文件。'],
    '不存在能解除相反陈述的生效更正。')


def write():
    assert len(cases) == 24 and len({c['id'] for c in cases}) == 24
    for task in (U,B):
        subset=[a for a in labels if a['task_id']==task]
        assert all(sum(a['answer']==answer for a in subset)==4 for answer in ANSWERS[task])
        assert len({a['family'] for a in subset})==6
    OUT.mkdir(exist_ok=True)
    for filename, data in [('development_cases.json',cases),('development_labels.json',labels)]:
        (OUT/filename).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest={'version':'dev-v1','cases':24,'task_counts':{U:12,B:12},
              'groups':12,'labels_per_task_class':4,'scope':'synthetic development only; no final test set',
              'hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
                        [OUT/'development_cases.json',OUT/'development_labels.json']}}
    (OUT/'dataset_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False))


if __name__=='__main__':
    write()
