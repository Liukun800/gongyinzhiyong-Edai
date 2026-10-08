"""Execute preregistered, label-separated synthetic review experiments."""
import argparse
import hashlib
import json
import os
import platform
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
from shadow_engine import ShadowEngine, input_guard, task_documents, QUESTIONS
from engine import ANSWERS

OUT = ROOT.parent/'评审整改/实验结果'
DATA = ROOT/'experiments/review_holdout_v1'


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tmp.replace(path)


def load_cases(suite):
    path = (ROOT/'experiments/development_cases.json') if suite == 'development' else DATA/'cases.json'
    return json.loads(path.read_text(encoding='utf-8')), hashlib.sha256(path.read_bytes()).hexdigest()


def slow_result(model, case):
    tid = case['task_id']; docs = task_documents(case, tid); guard = input_guard(docs, tid)
    if guard:
        return {'answer':guard[0], 'action':'supplement', 'source':'input_rule', 'reason':guard[1],
                'actual_complex_model_requests':0, 'usage':{}, 'evidence':[]}
    try:
        value = model.analyze(tid,docs)
        return {**value, 'action':'review' if value['answer'] in ('一致','未发现明确矛盾') else 'human',
                'source':'real_slow_analysis', 'actual_complex_model_requests':1}
    except Exception as exc:
        attempt = getattr(exc,'attempt',{})
        return {'answer':None,'action':'human','source':'complex_model_error','error':str(exc),
                'attempt':attempt,'usage':attempt.get('usage',{}),'actual_complex_model_requests':1}


def encoder_predictions(cases):
    import numpy as np
    import torch
    from transformers import AutoModel, AutoTokenizer
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold, cross_val_score
    torch.set_num_threads(4)
    train = json.loads((ROOT/'experiments/domain_dev_v2/combined_cases.json').read_text(encoding='utf-8'))
    gold = {r['id']:r for r in json.loads((ROOT/'experiments/domain_dev_v2/combined_labels.json').read_text(encoding='utf-8'))}
    revision='8f23c25b06e129b6c986331a13d8d025a92cf0ea'
    directory=ROOT/'models/bert-base-chinese-local'
    tokenizer=AutoTokenizer.from_pretrained(directory,local_files_only=True,trust_remote_code=False)
    model=AutoModel.from_pretrained(directory,local_files_only=True,trust_remote_code=False,add_pooling_layer=False)
    model.eval(); vectors=[]; times=[]
    for index, c in enumerate(train+cases):
        text='\n'.join(f"主体:{d['subject']} 期间:{d['period']}\n"+'\n'.join(p['text'] for p in d['paragraphs']) for d in c['documents'])
        start=time.perf_counter()
        inputs=tokenizer(QUESTIONS[c['task_id']],text,return_tensors='pt',truncation=False)
        if inputs['input_ids'].shape[1]>512: raise RuntimeError('Encoder input exceeds 512; no silent truncation')
        with torch.inference_mode(): vec=model(**inputs).last_hidden_state[:,0,:].cpu().numpy()[0]
        vectors.append(vec); times.append((time.perf_counter()-start)*1000)
        if (index+1)%20==0: print('ENCODED',index+1,flush=True)
    vectors=np.asarray(vectors); models={}; cv_records={}
    for tid in ANSWERS:
        indices=[i for i,c in enumerate(train) if c['task_id']==tid]
        x=vectors[indices]; y=np.asarray([gold[train[i]['id']]['answer'] for i in indices])
        groups=np.asarray([gold[train[i]['id']].get('lineage_group',gold[train[i]['id']].get('family',train[i]['id'])) for i in indices])
        splitter=GroupKFold(n_splits=3); choices=[]
        for cvalue in [.01,.1,1.]:
            pipe=make_pipeline(StandardScaler(),LogisticRegression(C=cvalue,max_iter=2000,class_weight='balanced',random_state=41))
            score=cross_val_score(pipe,x,y,groups=groups,cv=splitter,scoring='balanced_accuracy',error_score='raise')
            choices.append({'C':cvalue,'fold_scores':score.tolist(),'mean':float(score.mean())})
        best=max(choices,key=lambda r:r['mean'])
        models[tid]=make_pipeline(StandardScaler(),LogisticRegression(C=best['C'],max_iter=2000,class_weight='balanced',random_state=41)).fit(x,y)
        cv_records[tid]={'training_count':len(indices),'group_count':len(set(groups)),'cv':choices,'selected_C':best['C']}
    rows=[]
    for i,c in enumerate(cases):
        tid=c['task_id']; guard=input_guard(task_documents(c,tid),tid)
        if guard: prediction={'answer':guard[0],'action':'supplement','source':'input_rule','usage':{}}
        else:
            answer=models[tid].predict(vectors[len(train)+i:len(train)+i+1])[0]
            probs=models[tid].predict_proba(vectors[len(train)+i:len(train)+i+1])[0]
            prediction={'answer':answer,'action':'review' if answer in ('一致','未发现明确矛盾') else 'human',
                        'source':'bert_frozen_logistic','distribution':dict(zip(models[tid].classes_,probs.tolist())),
                        'usage':{'wall_ms':times[len(train)+i]}}
        rows.append({'case_id':c['id'],'task_id':tid,'prediction':prediction,'wall_ms':times[len(train)+i]})
    return rows, {'model':'bert-base-chinese','revision':revision,'method':'frozen Chinese encoder CLS + scaled logistic head',
                  'training_count':len(train),'hyperparameters':cv_records,'split':'3-fold grouped development CV; no holdout labels read'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--system',choices=['fast','slow','dual','encoder'],required=True)
    p.add_argument('--suite',choices=['development','holdout'],default='holdout');a=p.parse_args()
    cases,input_hash=load_cases(a.suite);start=time.perf_counter()
    report={'system':a.system,'suite':a.suite,'input_sha256':input_hash,'scope':'project-authored synthetic evaluation; no independent expert review',
            'python':platform.python_version(),'protocol':'评审整改/G3_对照协议_v1.md','status':'running','rows':[]}
    path=OUT/(a.suite+'_'+a.system+'.json');dump(path,report)
    if a.system=='encoder':
        if a.suite!='holdout': raise ValueError('54 training inputs include legacy development cases; do not evaluate encoder on them')
        report['rows'],report['model']=encoder_predictions(cases)
    else:
        if a.system in ('fast','dual'):
            from real_model import PublicDecisionModel
            fast=PublicDecisionModel()
        if a.system in ('slow','dual'):
            from slow_model import LocalSlowModel
            slow=LocalSlowModel()
        if a.system=='dual':
            from dual_engine import DualEngine
            engine=DualEngine(fast,slow,threshold=.8)
        elif a.system=='fast': engine=ShadowEngine(fast)
        report['model']=slow.info() if a.system=='slow' else engine.info()
        print('MODELS_READY',a.system,flush=True)
        for c in cases:
            step=time.perf_counter()
            if a.system=='slow': prediction=slow_result(slow,c)
            else: prediction=engine.evaluate(c,[c['task_id']])
            report['rows'].append({'case_id':c['id'],'task_id':c['task_id'],'prediction':prediction,
                                    'wall_ms':round((time.perf_counter()-step)*1000,2)})
            dump(path,report)
            print(a.system,c['id'],'recorded',len(report['rows']),flush=True)
    report.update(status='completed',process_wall_seconds=round(time.perf_counter()-start,2))
    dump(path,report);print('COMPLETED',str(path),flush=True)


if __name__=='__main__':main()
