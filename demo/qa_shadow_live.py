"""Engineering checks via the real local shadow service; not a performance benchmark."""
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:8767'


def call(path, body=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['X-Demo-Token'] = token
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    with urllib.request.urlopen(urllib.request.Request(BASE+path, data=data, headers=headers), timeout=180) as response:
        return json.load(response)


def main():
    health = call('/api/health')
    assert health['model_loaded'] is True
    report = {'model':health['model'], 'scope':'Six demo cases, engineering probes only; not held-out accuracy.', 'results':[]}
    for key in ['D01','D02','D03','D04','D05','D06']:
        detail = call('/api/cases/'+key)
        result = call('/api/cases/'+key+'/run', {'revision':detail['case']['revision']},health['csrf_token'])
        assert result['mode']=='真实模型影子'
        assert result['usage']['failed_model_requests']==0
        assert result['usage']['simulated_analysis_requests']==0
        for task in result['tasks']:
            if task['source']=='agentjev_public_shadow':
                assert abs(sum(task['distribution'].values())-1)<1e-5
                assert task['score']==max(task['distribution'].values())
                assert task['status'] in ('待复核','待人工核实','待补充')
            else:
                assert task['source']=='input_rule'
        report['results'].append(result)
        print(json.dumps({'case':key,'answers':[t['answer'] for t in result['tasks']], 'usage':result['usage']},ensure_ascii=False),flush=True)
    assert [t['distribution'] for t in report['results'][4]['tasks']]==[t['distribution'] for t in report['results'][5]['tasks']]
    report['passed']=True
    (ROOT/'qa'/'shadow-live-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Real shadow engineering checks passed; full predictions retained.',flush=True)


if __name__=='__main__':
    main()
