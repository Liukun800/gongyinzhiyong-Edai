"""Validate persisted official smoke results without calling any service."""
import argparse
import json
import math
from pathlib import Path

from official_client import parse_response

STAGE = Path(__file__).resolve().parent


def validate_run(run, stage=STAGE):
    cases = json.loads((stage / 'cases.json').read_text(encoding='utf-8'))
    references = json.loads((stage / 'references.json').read_text(encoding='utf-8'))
    summary = json.loads((run / 'usage_summary.json').read_text(encoding='utf-8'))
    records = summary.get('records')
    if not isinstance(records, list) or not 1 <= len(records) <= 2:
        raise ValueError('invalid_record_count')
    seen, rows = set(), []
    for index, record in enumerate(records):
        case = cases[index]
        case_id, task_id = case['case_id'], case['task_id']
        if record.get('case_id') != case_id or record.get('task_id') != task_id or case_id in seen:
            raise ValueError('invalid_case_identity')
        seen.add(case_id)
        stored = json.loads((run / (case_id + '.response.redacted.json')).read_text(encoding='utf-8'))
        if stored != record:
            raise ValueError('record_summary_mismatch')
        request = json.loads((run / (case_id + '.request.json')).read_text(encoding='utf-8'))
        questions = {task_id: case['question']}
        if request.get('state') != case['state'] or request.get('questions') != questions:
            raise ValueError('frozen_request_mismatch')
        if record.get('routing_action') != 'human_review':
            raise ValueError('human_review_required')
        if record.get('status') == 'failed':
            if index != len(records) - 1 or not isinstance(record.get('error_type'), str):
                raise ValueError('failure_stop_contract')
            rows.append({'case_id': case_id, 'status': 'failed', 'error_type': record['error_type']})
            continue
        if record.get('status') != 'measured' or record.get('auto_approval') is not False:
            raise ValueError('invalid_measured_status')
        parsed = parse_response(record, questions)
        latency = record.get('latency_ms')
        if type(latency) not in (int, float) or not math.isfinite(latency) or latency < 0:
            raise ValueError('invalid_latency')
        choice = parsed['answers'][task_id]['choice']
        agreement = choice == references[case_id]
        if record.get('reference_agreement') is not agreement:
            raise ValueError('reference_agreement_mismatch')
        rows.append({'case_id': case_id, 'status': 'measured', 'model': parsed['model'],
                     'choice': choice, 'reference_agreement': agreement,
                     'latency_ms': latency, 'usage': parsed['usage']})
    successful = sum(row['status'] == 'measured' for row in rows)
    inputs = sum(row.get('usage', {}).get('input_tokens', 0) for row in rows)
    outputs = sum(row.get('usage', {}).get('output_tokens', 0) for row in rows)
    for field, expected in [('attempted_requests', len(rows)), ('successful_requests', successful),
                            ('reported_input_tokens', inputs), ('reported_output_tokens', outputs)]:
        if type(summary.get(field)) is not int or summary[field] != expected:
            raise ValueError('usage_or_count_mismatch')
    if summary.get('bank_connected') is not False:
        raise ValueError('bank_scope_mismatch')
    return {'status': 'protocol_passed' if successful == 2 else 'failed_or_incomplete',
            'rows': rows, 'attempted_requests': len(rows), 'successful_requests': successful,
            'reference_agreements': sum(row.get('reference_agreement', False) for row in rows),
            'reported_input_tokens': inputs, 'reported_output_tokens': outputs,
            'failed_request_usage': 'unknown', 'independent_business_reviews': 0,
            'bank_connected': False, 'domain_quality_accepted': False,
            'source_run': run.name}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path)
    args = parser.parse_args()
    runs = sorted(STAGE.glob('run_*/usage_summary.json'))
    if args.run:
        run = args.run.resolve()
        if run.parent != STAGE or not run.name.startswith('run_'):
            raise ValueError('run_directory_required')
    elif runs:
        run = runs[-1].parent
    else:
        print('PENDING_OFFICIAL_OUTPUT; network_calls_in_this_command=0')
        return
    report = validate_run(run)
    target = run / 'validated_report.json'
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if target.exists() and target.read_text(encoding='utf-8') != serialized:
        raise ValueError('existing_report_changed')
    target.write_text(serialized, encoding='utf-8')
    lines = ['# 官方 Jev 最小协议验证', '',
             '| 任务 | 状态 | 返回模型 | 候选选择 | 参考标签一致 | 客户端耗时/ms |',
             '| --- | --- | --- | --- | --- | --- |']
    for row in report['rows']:
        lines.append('| ' + ' | '.join(str(row.get(key, '—')) for key in
                     ('case_id', 'status', 'model', 'choice', 'reference_agreement', 'latency_ms')) + ' |')
    lines.extend(['', f"协议状态：{report['status']}；请求{report['attempted_requests']}次，成功{report['successful_requests']}次。",
                  f"成功返回报告的输入Token：{report['reported_input_tokens']}；输出Token：{report['reported_output_tokens']}。失败请求消耗未知。",
                  '', '两条项目自编仿真任务用于确认结构化判断接口，不估计领域准确率或银行成本收益。',
                  '耗时为本地客户端到外部服务完整返回的单次观察，未测银行网络、并发或人员处理时间。',
                  '模型答案仍交人工复核；证据来源为材料索引，不能视为Jev生成或核实的证据。'])
    (run / '官方最小验证简报.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('OFFICIAL_RESULT_VALIDATED; status=' + report['status'])


if __name__ == '__main__':
    main()
