"""Frozen official Jev development comparison; max 47 calls, no retries."""
import argparse
import hashlib
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

STAGE = Path(__file__).resolve().parent
ROOT = STAGE.parents[1]
DEMO = ROOT / 'demo'
sys.path.insert(0, str(DEMO))
from engine import ANSWERS
from judgement import digest, spec_for
from official_model import OfficialDecisionModel, official_question
from shadow_engine import QUESTIONS, input_guard, model_state, task_documents
from typesafe_client import MODEL, configuration

DATA = DEMO / 'experiments/domain_dev_v2'
PM19 = ROOT / '评审整改/PM19_领域适配与同任务对照_20261006'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def freeze():
    protocol = STAGE / 'protocol.json'
    if protocol.exists():
        frozen = json.loads(protocol.read_text(encoding='utf-8'))
        for relative, expected in frozen['source_sha256'].items():
            assert sha(ROOT / relative) == expected, 'Frozen source changed: ' + relative
        assert sha(STAGE / 'inputs.json') == frozen['inputs_sha256']
        assert sha(STAGE / 'references.json') == frozen['references_sha256']
        return frozen
    old = json.loads((PM19 / 'frozen_protocol.json').read_text(encoding='utf-8'))
    cases_path, labels_path = DATA / 'combined_cases.json', DATA / 'combined_labels.json'
    for path in (cases_path, labels_path):
        assert sha(path) == old['source_sha256'][str(path.relative_to(ROOT))]
    cases = json.loads(cases_path.read_text(encoding='utf-8'))
    labels = {row['id']: row for row in json.loads(labels_path.read_text(encoding='utf-8'))}
    inputs, references = [], {}
    for case in cases:
        task = case['task_id']
        docs = task_documents(case, task)
        guard = input_guard(docs, task)
        inputs.append({'case_id': case['id'], 'task_id': task,
                       'state': model_state(docs), 'rule_answer': guard[0] if guard else None,
                       'question': official_question(spec_for(QUESTIONS[task], ANSWERS[task]))})
        references[case['id']] = {'answer': labels[case['id']]['answer'],
                                  'lineage_group': labels[case['id']]['lineage_group']}
    assert len(inputs) == 54 and sum(row['rule_answer'] is None for row in inputs) == 47
    write(STAGE / 'inputs.json', inputs)
    write(STAGE / 'references.json', references)
    sources = [cases_path, labels_path, PM19 / 'summary.json', Path(__file__),
               DEMO / 'typesafe_client.py', DEMO / 'official_model.py',
               DEMO / 'judgement.py', DEMO / 'shadow_engine.py', DEMO / 'engine.py']
    frozen = {'version': 'PM21-official-same-task-1', 'model': MODEL, 'case_count': 54,
              'semantic_cases': 47, 'shared_rule_cases': 7, 'max_http_calls': 47, 'retries': 0,
              'scope': 'same 54 project-authored synthetic development materials; no independent bank labels',
              'comparison': 'same state, task instructions, candidate labels and input guards as PM19; official criteria verbalize the registered candidates',
              'limits': ['Different pretraining, model sizes and adaptation resources; not an architecture-only causal comparison',
                         'External API end-to-end timing and local feature extraction timing have different scopes',
                         'No calibrated acceptance threshold, automatic lending, human time saving or bank connection claim'],
              'source_sha256': {str(path.relative_to(ROOT)): sha(path) for path in sources},
              'inputs_sha256': sha(STAGE / 'inputs.json'), 'references_sha256': sha(STAGE / 'references.json'),
              'created_at': datetime.now(timezone.utc).isoformat()}
    write(protocol, frozen)
    return frozen


def summarize(rows, references):
    conflicts = {'存在明确矛盾', '发现明确矛盾'}
    semantic = [row for row in rows if row['source'] != 'input_rule']
    answered = [row for row in rows if row.get('answer') is not None]
    valid = [row for row in semantic if row['status'] == 'measured']
    times = [row['wall_ms'] for row in valid]
    return {'scope': 'development reference agreement; not bank accuracy',
            'processed_cases': len(rows), 'complete': len(rows) == 54 and len(valid) == 47,
            'agreement_n': sum(row.get('answer') == references[row['case_id']]['answer'] for row in answered),
            'semantic_agreement_n': sum(row.get('answer') == references[row['case_id']]['answer'] for row in valid),
            'semantic_processed_n': len(semantic), 'semantic_successful_n': len(valid),
            'conflict_nonidentification_ids': [row['case_id'] for row in rows if
                references[row['case_id']]['answer'] in conflicts and row.get('answer') not in conflicts],
            'false_conflict_ids': [row['case_id'] for row in rows if
                references[row['case_id']]['answer'] not in conflicts and row.get('answer') in conflicts],
            'reported_input_tokens': sum(row.get('official_usage', {}).get('input_tokens', 0) for row in valid),
            'reported_output_tokens': sum(row.get('official_usage', {}).get('output_tokens', 0) for row in valid),
            'client_latency_median_ms': statistics.median(times) if times else None,
            'failure_usage': 'unknown', 'independent_business_reviews': 0, 'bank_connected': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    frozen = freeze()
    if not args.run:
        print('PROTOCOL_FROZEN; cases=54; semantic=47; network_calls=0')
        return 0
    configuration()
    minimum = ROOT / '评审整改/PM20_官方Jev判断头最小验证'
    verified = [json.loads(path.read_text(encoding='utf-8')) for path in minimum.glob('run_*/validated_report.json')]
    assert any(report.get('status') == 'protocol_passed' for report in verified), 'Minimum protocol verification required'
    if any(STAGE.glob('run_*/manifest.json')):
        raise ValueError('Comparison already started; inspect saved results before another paid run')
    run = STAGE / ('run_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    run.mkdir()
    write(run / 'manifest.json', {'protocol_sha256': sha(STAGE / 'protocol.json'), 'model': MODEL,
                                 'started_at': datetime.now(timezone.utc).isoformat(), 'max_http_calls': 47})
    inputs = json.loads((STAGE / 'inputs.json').read_text(encoding='utf-8'))
    references = json.loads((STAGE / 'references.json').read_text(encoding='utf-8'))
    predictor = OfficialDecisionModel(max_requests=47)
    rows = []
    for item in inputs:
        row = {'case_id': item['case_id'], 'task_id': item['task_id'],
               'state_sha256': digest(item['state']), 'question_sha256': digest(item['question'])}
        if item['rule_answer'] is not None:
            row.update(source='input_rule', status='rule_handled', answer=item['rule_answer'])
        else:
            task = item['task_id']
            try:
                output = predictor.decide(item['state'], QUESTIONS[task], ANSWERS[task])
                row.update(source='typesafe_official_jev', status='measured', **output)
            except Exception as exc:
                row.update(source='typesafe_official_jev', status='failed', answer=None,
                           error_type=getattr(exc, 'kind', 'official_call_failed'), action='human')
        rows.append(row)
        write(run / (item['case_id'] + '.result.json'), row)
        print(json.dumps({k: row.get(k) for k in ('case_id', 'status', 'answer', 'error_type')}, ensure_ascii=False), flush=True)
        if row['status'] == 'failed':
            break
    summary = summarize(rows, references)
    summary.update(attempted_official_tasks=len(predictor.events), rows=rows,
                   protocol_sha256=sha(STAGE / 'protocol.json'))
    write(run / 'summary.json', summary)
    # Verify unchanged sources after the real calls; retain failure/incomplete results.
    freeze()
    print('RESULT_DIRECTORY=' + str(run))
    print('COMPLETE=' + str(summary['complete']))
    return 0 if summary['complete'] else 1


if __name__ == '__main__':
    sys.exit(main())
