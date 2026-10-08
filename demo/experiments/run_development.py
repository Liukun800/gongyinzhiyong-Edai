"""Reproducible diagnostic comparison, explicitly not a held-out bank benchmark."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
import urllib.request

import numpy as np
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine import ANSWERS
from shadow_engine import task_documents, input_guard, model_state, route_answer

HERE = Path(__file__).resolve().parent


def load_data():
    manifest = json.loads((HERE/'dataset_manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest['hashes'].items():
        if hashlib.sha256((HERE/name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Dataset hash mismatch: {name}')
    cases=json.loads((HERE/'development_cases.json').read_text(encoding='utf-8'))
    labels=json.loads((HERE/'development_labels.json').read_text(encoding='utf-8'))
    annotations={a['id']:a for a in labels}
    assert len(annotations)==len(cases)==24
    for case in cases:
        a=annotations[case['id']]
        assert a['task_id']==case['task_id'] and a['answer'] in ANSWERS[case['task_id']]
        assert a['expected_action']==route_answer(a['answer'])[1]
        for e in a['evidence']:
            assert any(d['id']==e['document_id'] and any(p['id']==e['paragraph_id'] and p['text']==e['quote']
                       for p in d['paragraphs']) for d in case['documents'])
    return cases,annotations,manifest


def feature_text(case):
    state=model_state(task_documents(case,case['task_id']))
    return json.dumps(state,ensure_ascii=False,sort_keys=True)


def row(case, annotation, answer, source, **extra):
    return {'case_id':case['id'],'task_id':case['task_id'],'family':annotation['family'],
            'expected':annotation['answer'],'predicted':answer,'correct':answer==annotation['answer'],
            'expected_action':annotation['expected_action'],'action':route_answer(answer)[1],
            'source':source,**extra}


def grouped_baseline(cases,annotations):
    rows,folds=[],[]
    for task in ANSWERS:
        subset=[c for c in cases if c['task_id']==task]
        for family in sorted({annotations[c['id']]['family'] for c in subset}):
            train=[c for c in subset if annotations[c['id']]['family']!=family]
            validation=[c for c in subset if annotations[c['id']]['family']==family]
            assert not {annotations[c['id']]['family'] for c in train}&{family}
            assert {annotations[c['id']]['answer'] for c in train}==set(ANSWERS[task])
            model=make_pipeline(TfidfVectorizer(analyzer='char',ngram_range=(2,4),sublinear_tf=True),
                                LogisticRegression(C=1.,class_weight='balanced',max_iter=2000,random_state=20260927))
            model.fit([feature_text(c) for c in train],[annotations[c['id']]['answer'] for c in train])
            folds.append({'task_id':task,'validation_family':family,'train_ids':[c['id'] for c in train],
                          'validation_ids':[c['id'] for c in validation],
                          'vectorizer_fit_scope':'training fold only'})
            for case in validation:
                started=time.perf_counter()
                guard=input_guard(task_documents(case,task),task)
                distribution=None
                if guard:
                    answer,source=guard[0],'input_rule'
                else:
                    probs=model.predict_proba([feature_text(case)])[0]
                    distribution=dict(zip(model.classes_,map(float,probs)))
                    answer=max(distribution,key=distribution.get)
                    source='tfidf_logistic_group_oof'
                rows.append(row(case,annotations[case['id']],answer,source,distribution=distribution,
                                wall_ms=round((time.perf_counter()-started)*1000,3)))
    return rows,folds


def rules_only(cases,annotations):
    result=[]
    for c in cases:
        guard=input_guard(task_documents(c,c['task_id']),c['task_id'])
        result.append(row(c,annotations[c['id']],guard[0] if guard else None,
                          'input_rule' if guard else 'abstain_semantics'))
    return result


def request(base,path,body=None,token=None):
    headers={'Content-Type':'application/json'}
    if token:headers['X-Demo-Token']=token
    req=urllib.request.Request(base+path,data=None if body is None else json.dumps(body,ensure_ascii=False).encode(),headers=headers)
    with urllib.request.urlopen(req,timeout=90) as response:
        return json.load(response)


def real_shadow(cases,annotations,base):
    health=request(base,'/api/health')
    if health.get('app_revision')!='2026-09-27-review2' or not health.get('model_loaded'):
        raise RuntimeError('Updated real-shadow service required')
    rows,raw=[],[]
    # Gold annotations remain in this evaluator; the endpoint receives neither labels nor case IDs.
    for case in cases:
        started=time.perf_counter()
        result=request(base,'/api/shadow/evaluate',{'documents':case['documents'],'task_ids':[case['task_id']]},health['csrf_token'])
        latency=round((time.perf_counter()-started)*1000,3)
        t=result['tasks'][0]
        rows.append(row(case,annotations[case['id']],t['answer'],t['source'],
                        distribution=t['distribution'],wall_ms=latency,usage=result['usage']))
        raw.append({'case_id':case['id'],'result':result})
        print(f"{case['id']}: {t['answer']} ({'match' if rows[-1]['correct'] else 'MISMATCH'})",flush=True)
        (HERE/'results').mkdir(exist_ok=True)
        (HERE/'results/agentjev_progress.json').write_text(json.dumps({'completed':len(rows),'raw':raw},ensure_ascii=False,indent=2),encoding='utf-8')
    return rows,raw,health['model']


def summarize(rows):
    summaries={}
    for task in [*ANSWERS,'all']:
        selected=[r for r in rows if task=='all' or r['task_id']==task]
        semantic=[r for r in selected if r['source'] not in ('input_rule','abstain_semantics')]
        answered=[r for r in selected if r['predicted'] is not None]
        conflicts=[r for r in selected if r['expected'] in ('存在明确矛盾','发现明确矛盾')]
        misses=[r['case_id'] for r in conflicts if r['predicted'] not in ('存在明确矛盾','发现明确矛盾')]
        summaries[task]={'n':len(selected),'correct':sum(r['correct'] for r in selected),
                         'answered':len(answered),'correct_among_answered':sum(r['correct'] for r in answered),
                         'rule_n':sum(r['source']=='input_rule' for r in selected),
                         'semantic_n':len(semantic),'semantic_correct':sum(r['correct'] for r in semantic),
                         'conflict_n':len(conflicts),'conflict_not_identified_ids':misses,
                         'route_matches':sum(r['action']==r['expected_action'] for r in selected),
                         'auto_completed':0,'mistake_ids':[r['case_id'] for r in selected if not r['correct']],
                         'confusion':dict(Counter(f"{r['expected']} -> {r['predicted'] or '未作语义判断'}" for r in selected))}
    return summaries


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',default='http://127.0.0.1:8767')
    parser.add_argument('--skip-real',action='store_true')
    args=parser.parse_args()
    cases,annotations,manifest=load_data()
    baseline,folds=grouped_baseline(cases,annotations)
    systems={'rules':rules_only(cases,annotations),'tfidf_logistic_same_route':baseline}
    raw,model=[],None
    if not args.skip_real:
        actual,raw,model=real_shadow(cases,annotations,args.base)
        systems['agentjev_public_same_route']=actual
    report={'created_at':datetime.now(timezone.utc).isoformat(),'scope':'development diagnostics, not final test or bank performance',
            'dataset':manifest,'model':model,'environment':{'python':platform.python_version(),'sklearn':sklearn.__version__},
            'baseline':{'algorithm':'char 2-4 gram TF-IDF + balanced logistic regression; C=1 fixed',
                        'split':'leave one case family out within each task; 6 folds per task; 10 train / 2 validation',
                        'calibration':'none; raw probabilities never authorize automatic completion',
                        'folds':folds},
            'systems':{k:{'summary':summarize(v),'rows':v} for k,v in systems.items()},'real_raw':raw}
    folder=HERE/'results';folder.mkdir(exist_ok=True)
    path=folder/('baseline_only.json' if args.skip_real else 'development_comparison.json')
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v['summary']['all'] for k,v in report['systems'].items()},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
