"""Freeze new project-authored scenarios. Never claim independent expert labels."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEST = HERE / 'review_holdout_v1'


def build():
    if (DEST / 'manifest.json').exists():
        raise RuntimeError('Holdout is already frozen; do not overwrite it')
    cases, labels = [], []

    def add(family, task, texts, answer, rationale, *, subjects=None, periods=None):
        cid = 'H' + str(len(cases)+1).zfill(2)
        docs = [{'id': 'm'+str(i+1), 'title': '材料'+str(i+1),
                 'kind': 'purpose' if task == 'USE_MATCH' else 'business',
                 'subject': (subjects or ['仿真企业丙']*len(texts))[i],
                 'period': (periods or ['2026-06']*len(texts))[i],
                 'paragraphs': [{'id': 'p1', 'text': text}]} for i, text in enumerate(texts)]
        cases.append({'id': cid, 'revision': 1, 'task_id': task, 'documents': docs})
        labels.append({'id': cid, 'task_id': task, 'family': family, 'answer': answer,
                       'rationale': rationale, 'label_status': 'project_authored_unreviewed',
                       'reviewer': None, 'evidence': [d['id']+':p1' for d in docs]})

    U, B = 'USE_MATCH', 'BIZ_CONFLICT'
    add('H_U_allocation',U,['申请C的借款六成买纸箱，四成买印刷标签，覆盖全部借款。','对应申请C的采购清单列明：纸箱占借款60%，印刷标签占40%，无其他支出。'],'一致','全部资金分配相容。')
    add('H_U_allocation',U,['申请C的全部借款仅用于纸箱和标签采购。','对应申请C的实际支出说明：全部借款支付仓库租金，未采购任何纸箱或标签。'],'存在明确矛盾','同一全部借款用途互斥。')
    add('H_U_allocation',U,['申请C的借款六成买纸箱，四成买标签。','仅附申请C中纸箱采购合同，说明剩余四成资金用途暂无资料。'],'信息不足','剩余范围缺少证据，未出现明确相反用途。')
    add('H_U_funding_source',U,['申请C借款仅采购木板；设备另以股东自有资金购买。','资金明细：借款全部付木板供应商；设备价款完全由股东自有资金承担，两项不混用。'],'一致','应比较借款范围，自有资金支出不冲突。')
    add('H_U_funding_source',U,['申请C借款全部仅采购木板；不用于设备。','资金明细明确：申请C全部借款付设备尾款，木板由股东自有资金购买。'],'存在明确矛盾','借款与自有资金的归属被明确交换。')
    add('H_U_funding_source',U,['申请C借款仅采购木板。','企业本期同时购入木板和设备，明细未注明哪项使用本次借款。'],'信息不足','采购事实不能确定借款对应关系。')
    add('H_U_payment_stage',U,['申请C仅支付冷柜采购首付款，后续尾款另行筹资。','同一冷柜合同约定本次借款支付首付款，尾款不占用此次借款。'],'一致','付款阶段和资金范围一致。')
    add('H_U_payment_stage',U,['申请C全部借款只付冷柜采购首付款。','本次借款付款凭证注明全部付广告服务费；冷柜首付款尚未支付。'],'存在明确矛盾','同一借款唯一用途互斥。')
    add('H_U_payment_stage',U,['申请C仅支付冷柜采购首付款。','附件仅说明冷柜总价，不说明首付款、付款安排及本次借款的对应关系。'],'信息不足','总价不能证明首付款安排。')
    add('H_U_agent_purchase',U,['申请C只用于采购咖啡豆，委托代理商代采。','代采协议明确代理商将申请C全部资金用于咖啡豆采购，不另作他用。'],'一致','代理身份不改变明确采购用途。')
    add('H_U_agent_purchase',U,['申请C的资金全部只采购咖啡豆。','代理商报告明确申请C的全部资金实际购买门店家具，未购咖啡豆。'],'存在明确矛盾','同一委托资金实际用途相反。')
    add('H_U_agent_purchase',U,['申请C资金只采购咖啡豆。','仅有向代理商转账回单，没有代采品类或用途的记载。'],'信息不足','转账本身不足以确定品类。')
    add('H_B_channels',B,['六月企业线下门店整月关门，但线上订单正常处理。','六月线下门店没有营业，线上渠道持续接单。'],'未发现明确矛盾','两种渠道陈述相容。')
    add('H_B_channels',B,['六月企业所有线上和线下渠道均停止营业，没有任何接单。','六月该企业线上渠道每天接单营业，线下门店关闭。'],'发现明确矛盾','全渠道停止与线上每天营业冲突。')
    add('H_B_channels',B,['六月线下门店停业。','六月报表写“业务仍在运行”，未注明是线下还是线上或其他业务。'],'无法比较','第二份陈述的业务口径不清楚。')
    add('H_B_partial_month',B,['六月一日至十日停业，十一日起恢复营业。','六月前十天未营业，其余二十天持续营业。'],'未发现明确矛盾','分段期间对应相容。')
    add('H_B_partial_month',B,['六月一日至十日每天正常营业，没有停业。','六月一日至十日完全停业，没有开展经营。'],'发现明确矛盾','相同十天状态互斥。')
    add('H_B_partial_month',B,['六月曾停业三天，未记具体日期。','六月上旬中有七天正常营业，未记具体日期，其余日期状态不详。'],'无法比较','未能定位日期，不能断言同日矛盾。')
    add('H_B_metric_scope',B,['六月新签合同金额为零，但收到五月旧合同回款。','六月没有新签合同；当月回款全部来自五月合同。'],'未发现明确矛盾','合同新增与历史回款是不同指标且说明一致。')
    add('H_B_metric_scope',B,['六月新签合同数量为零。','统计说明明确有三份合同在六月新签，不含续签或历史合同。'],'发现明确矛盾','同一新增合同数量零与三互斥。')
    add('H_B_metric_scope',B,['六月新签合同数量为零。','六月业务数量为三，但未定义“业务数量”是否指新签合同。'],'无法比较','统计指标未统一。')
    add('H_B_places',B,['六月东店暂停营业，西店持续营业。','六月东店未营业；西店每天营业。'],'未发现明确矛盾','相同两店状态相容。')
    add('H_B_places',B,['六月东店全月停业。','另一份记录明确同一东店在六月每天营业，并非西店。'],'发现明确矛盾','同店同月状态冲突。')
    add('H_B_places',B,['六月东店停业。','六月某门店持续营业，但门店名称和归属无法确定。'],'无法比较','无法确认是否同一门店。')
    add('H_guard_missing',U,['申请C借款仅采购耗材。'],'信息不足','缺少第二份可比较材料。')
    add('H_guard_subject',U,['申请C采购耗材。','文件记载申请C资金支付房租。'],'信息不足','材料登记为不同主体，先核实归属。',subjects=['仿真企业丙','仿真企业丁'])
    add('H_guard_period',B,['本月正常营业。','本月整月停业。'],'无法比较','登记的月份不同，不能当作同月冲突。',periods=['2026-05','2026-06'])
    add('H_guard_blank',B,['企业六月正常营业。','企业六月整月停业。'],'无法比较','第二份主体归属登记为空，应先补充归属。',subjects=['仿真企业丙',''])

    DEST.mkdir(parents=True, exist_ok=True)
    for name, value in [('cases.json',cases),('labels.sealed.json',labels)]:
        (DEST/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    training = HERE/'domain_dev_v2/combined_cases.json'
    known = json.loads(training.read_text(encoding='utf-8'))
    def fingerprint(c):
        return hashlib.sha256(json.dumps(c['documents'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    overlap = set(map(fingerprint,cases)) & set(map(fingerprint,known))
    if overlap: raise RuntimeError('Exact duplicate inputs with development corpus')
    manifest = {'version':'review-holdout-v1','cases':len(cases),'family_count':len({r['family'] for r in labels}),
        'split':'held_out_from_this_round_training_and_tuning','expert_reviewed':False,
        'data_status':'new_project_authored_synthetic_challenge_not_independent_bank_test',
        'generation':'manually specified material families; no model predictions used to generate labels',
        'exact_overlap_with_development':0,'semantic_independence':'not independently certified; task concepts necessarily overlap',
        'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in DEST.iterdir() if p.suffix=='.json'},
        'training_source_sha256':hashlib.sha256(training.read_bytes()).hexdigest(),
        'evaluation_status':'not_run','usage_rule':'Do not tune using holdout outputs; independent label review still pending'}
    (DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    review = ['id,task_id,proposed_label,reviewer,reviewed_label,reason,status']
    review += [f'{r["id"]},{r["task_id"]},{r["answer"]},,,,pending' for r in labels]
    (DEST/'independent_review.csv').write_text('\n'.join(review)+'\n',encoding='utf-8-sig')
    print(json.dumps({'cases':len(cases),'families':manifest['family_count'],'exact_overlap':0,'expert_reviewed':False},ensure_ascii=False))


if __name__=='__main__': build()
