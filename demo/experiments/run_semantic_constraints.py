"""Paired development-only wording experiment; never overwrites old experiments."""
import argparse
import hashlib
import json
import platform
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1]
ROOT = DEMO.parent
sys.path.insert(0, str(DEMO))
from shadow_engine import ShadowEngine, QUESTIONS
from experiments.semantic_constraints_v1 import QUESTIONS_V1

OUT = ROOT / '评审整改/PM14_语义约束开发验证_20261005'
SETS = {
    'exposed28': ('demo/experiments/review_holdout_v1/cases.json',
                  'demo/experiments/review_holdout_v1/labels.sealed.json'),
    'legacy24': ('demo/experiments/development_cases.json',
                 'demo/experiments/development_labels.json'),
}
CONFLICT = {'存在明确矛盾', '发现明确矛盾'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(name, value):
    path = OUT / name
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / 'plan.json').exists():
        raise RuntimeError('Preparation already frozen; do not replace it')
    protected = [ROOT / p for pair in SETS.values() for p in pair]
    protected += list((ROOT / '评审整改/实验结果').glob('*.json'))
    protected += [ROOT / read(ROOT / '评审整改/执行台账.json')['current_document']]
    save('protected_before.json', {str(p): sha(p) for p in protected})
    save('plan.json', {
        'created': datetime.now().isoformat(), 'stage': 'development_only',
        'hypothesis': '通用资金归属及经营比较维度约束可改善已知误报与漏识别',
        'baseline_questions': QUESTIONS, 'candidate_questions': QUESTIONS_V1,
        'model': 'same pinned AgentJev-0.6B CPU; threads=4; no training/calibration',
        'sets': SETS, 'order': 'all cases; alternate baseline/candidate first per global index',
        'adoption_gate': {
            'exposed28_net_matches': 'strictly improves',
            'legacy24_matches': 'no decrease',
            'conflict_misses': 'no increase on either set; H05 must be corrected',
            'false_conflicts': 'no increase on either set',
            'inference_failures': 'zero on both versions',
            'deployment': 'passing is development evidence only; no automatic default enablement'
        },
        'labels': 'unreviewed project references; opened only after all paired predictions',
        'limits': 'already exposed materials; no independent quality/cost/bank benefit claim'
    })
    print('PREPARED', OUT, flush=True)


def run():
    plan = read(OUT / 'plan.json')
    if plan['baseline_questions'] != QUESTIONS or plan['candidate_questions'] != QUESTIONS_V1:
        raise RuntimeError('Task wording changed after freeze')
    if (OUT / 'paired_predictions.json').exists():
        raise RuntimeError('Run output exists; preserve all results')
    protected = read(OUT / 'protected_before.json')
    if any(sha(p) != v for p, v in protected.items()):
        raise RuntimeError('Protected input changed since preparation')
    from real_model import PublicDecisionModel
    started = time.perf_counter()
    model = PublicDecisionModel(threads=4)
    engines = {'baseline': ShadowEngine(model),
               'candidate': ShadowEngine(model, questions=QUESTIONS_V1)}
    report = {'status': 'running', 'model': model.info(), 'environment': {
        'python': sys.version, 'platform': platform.platform(), 'threads': 4,
        'process_model_instances': 1}, 'rows': [],
        'code_sha256': {str(p): sha(p) for p in [Path(__file__),
                           DEMO / 'shadow_engine.py', DEMO / 'real_model.py',
                           DEMO / 'experiments/semantic_constraints_v1.py']}}
    save('paired_predictions.json', report)
    index = 0
    for suite, (inputs, _) in SETS.items():
        for case in read(ROOT / inputs):
            order = ['baseline', 'candidate'] if index % 2 == 0 else ['candidate', 'baseline']
            row = {'suite': suite, 'case_id': case['id'], 'task_id': case['task_id'], 'order': order}
            for version in order:
                step = time.perf_counter()
                row[version] = engines[version].evaluate(case, [case['task_id']])
                row[version]['paired_elapsed_ms'] = round((time.perf_counter()-step)*1000, 2)
            report['rows'].append(row)
            save('paired_predictions.json', report)
            index += 1
            print(f'PAIR {index}/52 {suite} {case["id"]}: '
                  f'{row["baseline"]["tasks"][0]["answer"]} -> '
                  f'{row["candidate"]["tasks"][0]["answer"]}', flush=True)
    report.update(status='completed', process_wall_seconds=round(time.perf_counter()-started, 2))
    save('paired_predictions.json', report)
    summarize()


def summarize():
    report = read(OUT / 'paired_predictions.json')
    if report['status'] != 'completed' or len(report['rows']) != 52:
        raise RuntimeError('Cannot summarize incomplete predictions')
    summaries, details = {}, []
    for suite, (_, label_file) in SETS.items():
        labels = {l['id']: l for l in read(ROOT / label_file)}
        rows = [r for r in report['rows'] if r['suite'] == suite]
        summaries[suite] = {}
        for version in ('baseline', 'candidate'):
            ms, token_counts = [], []
            matches = misses = false_conflicts = failures = 0
            for row in rows:
                prediction = row[version]
                task = prediction['tasks'][0]
                reference = labels[row['case_id']]['answer']
                matches += task['answer'] == reference
                misses += reference in CONFLICT and task['answer'] not in CONFLICT
                false_conflicts += reference not in CONFLICT and task['answer'] in CONFLICT
                failures += prediction['usage']['failed_model_requests']
                ms.append(prediction['paired_elapsed_ms'])
                token_counts.append(prediction['usage']['input_path_tokens'])
            summaries[suite][version] = {
                'n': len(rows), 'reference_matches': matches, 'conflict_misses': misses,
                'false_conflicts': false_conflicts, 'failed_requests': failures,
                'median_workflow_ms': round(statistics.median(ms), 2),
                'total_input_path_tokens': sum(token_counts)}
        for row in rows:
            ref = labels[row['case_id']]['answer']
            before = row['baseline']['tasks'][0]['answer']
            after = row['candidate']['tasks'][0]['answer']
            details.append({'suite': suite, 'case_id': row['case_id'], 'reference': ref,
                            'baseline': before, 'candidate': after,
                            'change': 'improved' if before != ref and after == ref else
                                      'regressed' if before == ref and after != ref else
                                      'changed_wrong' if before != after else 'unchanged'})
    checks = {}
    for suite, value in summaries.items():
        b, c = value['baseline'], value['candidate']
        checks[suite + '_match_gate'] = c['reference_matches'] > b['reference_matches'] if suite == 'exposed28' else c['reference_matches'] >= b['reference_matches']
        checks[suite + '_no_more_misses'] = c['conflict_misses'] <= b['conflict_misses']
        checks[suite + '_no_more_false_conflicts'] = c['false_conflicts'] <= b['false_conflicts']
        checks[suite + '_zero_failures'] = b['failed_requests'] == c['failed_requests'] == 0
    h05 = next(d for d in details if d['case_id'] == 'H05')
    checks['H05_corrected'] = h05['candidate'] == h05['reference']
    before = read(OUT / 'protected_before.json')
    checks['protected_files_unchanged'] = all(sha(p) == v for p, v in before.items())
    summary = {'scope': 'exposed development only; unreviewed reference labels',
               'results': summaries, 'checks': checks,
               'development_gate_passed': all(checks.values()),
               'default_changed': False, 'training_performed': False,
               'independent_review_completed': False,
               'changes': details, 'limits': 'no generalization or monetary/approval-time claim'}
    save('summary.json', summary)
    save('protected_after.json', {p: sha(p) for p in before})
    print(json.dumps({'results': summaries, 'checks': checks,
                      'development_gate_passed': all(checks.values())}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'run', 'summarize'])
    args = parser.parse_args()
    {'prepare': prepare, 'run': run, 'summarize': summarize}[args.action]()
