"""Validate real saved output before building the same-task comparison."""
import json

import run_comparison as runner


def main():
    runner.freeze()
    runs = list(runner.STAGE.glob('run_*/summary.json'))
    if not runs:
        print('PENDING_OFFICIAL_COMPARISON; no measured batch; network_calls=0')
        return
    if len(runs) != 1:
        raise ValueError('Multiple runs require explicit reconciliation')
    directory = runs[0].parent
    saved = json.loads(runs[0].read_text(encoding='utf-8'))
    inputs = {item['case_id']: item for item in json.loads((runner.STAGE / 'inputs.json').read_text(encoding='utf-8'))}
    references = json.loads((runner.STAGE / 'references.json').read_text(encoding='utf-8'))
    rows = saved['rows']
    assert saved['protocol_sha256'] == runner.sha(runner.STAGE / 'protocol.json')
    assert len({row['case_id'] for row in rows}) == len(rows)
    assert [row['case_id'] for row in rows] == list(inputs)[:len(rows)]
    for row in rows:
        item = inputs[row['case_id']]
        assert row == json.loads((directory / (row['case_id'] + '.result.json')).read_text(encoding='utf-8'))
        assert row['task_id'] == item['task_id']
        assert row['state_sha256'] == runner.digest(item['state'])
        assert row['question_sha256'] == runner.digest(item['question'])
        if item['rule_answer'] is not None:
            assert row['source'] == 'input_rule' and row['answer'] == item['rule_answer']
        elif row['status'] == 'measured':
            record = row['decision_record']
            assert record['official_model'] == runner.MODEL and not record['offline_test_mode']
            assert record['state_sha256'] == row['state_sha256']
            assert record['official_question_sha256'] == runner.digest({item['task_id']: item['question']})
            from typesafe_client import parse_response
            parse_response({'model': record['official_model'],
                            'answers': {item['task_id']: {'type': 'choice', 'choice': row['answer'],
                                        'probabilities': row['distribution'], 'confidence': row['service_confidence']}},
                            'usage': row['official_usage']}, {item['task_id']: item['question']})
            assert record['official_usage'] == row['official_usage']
    computed = runner.summarize(rows, references)
    for key, value in computed.items():
        assert saved[key] == value, 'Summary mismatch: ' + key
    baseline = json.loads((runner.PM19 / 'summary.json').read_text(encoding='utf-8'))
    comparison = {'official': computed, 'pm19_systems': baseline['systems'],
                  'scope': 'Same synthetic development cases; different pretrained systems, not architecture-only causality',
                  'bank_connected': False, 'independent_business_reviews': 0,
                  'cost_savings_measured': False}
    out = directory / 'validated_comparison.json'
    if out.exists():
        assert json.loads(out.read_text(encoding='utf-8')) == comparison
    else:
        runner.write(out, comparison)
    print('SAVED_OFFICIAL_OUTPUT_VALIDATED; complete=' + str(computed['complete']))


if __name__ == '__main__':
    main()
