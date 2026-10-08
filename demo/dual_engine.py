"""Task-level real fast/slow cooperation; all results remain review suggestions."""
import time

from shadow_engine import ShadowEngine, task_documents
from slow_model import SlowAnalysisError


class DualEngine(ShadowEngine):
    def __init__(self, predictor, slow_model, threshold=.8):
        super().__init__(predictor)
        if not .5 <= threshold <= 1: raise ValueError('Invalid experimental routing threshold')
        self.slow_model, self.threshold = slow_model, threshold

    def info(self):
        return {**super().info(), 'dual_system': True, 'slow_model': self.slow_model.info(),
                'routing_threshold': self.threshold, 'threshold_status': 'engineering_experiment_not_calibrated',
                'slow_quality_verified': False, 'default_use_recommended': False,
                'auto_completion_enabled': False}

    def evaluate(self, case, task_ids=None):
        start = time.perf_counter()
        result = super().evaluate(case, task_ids)
        usage = result['usage']
        usage.update(successful_complex_model_requests=0, failed_complex_model_requests=0,
                     complex_prompt_tokens=0, complex_completion_tokens=0, complex_wall_ms=0)
        for task in result['tasks']:
            if task['source'] in ('input_rule', 'model_error'): continue
            if task['answer'] in ('存在明确矛盾', '发现明确矛盾'):
                task['routing_reason'] = 'explicit_conflict_to_human'
                continue
            trigger = (task['answer'] in ('信息不足', '无法比较') or task['score'] < self.threshold)
            if not trigger:
                task['routing_reason'] = 'fast_suggestion_requires_review'
                continue
            task['fast_decision'] = {k: task[k] for k in ('answer', 'score', 'distribution', 'source', 'model_usage')}
            task['routing_reason'] = 'semantic_uncertainty_or_low_raw_score'
            usage['actual_complex_model_requests'] += 1
            try:
                analyzed = self.slow_model.analyze(task['id'], task_documents(case, task['id']))
                usage['successful_complex_model_requests'] += 1
                task.update(answer=analyzed['answer'], score=None, distribution=None,
                            source='real_slow_analysis', evidence=analyzed['evidence'],
                            evidence_semantics=analyzed['evidence_validation'],
                            calibration='生成式复杂分析不提供可用于自动通过的校准概率',
                            analysis={'mode': '真实System 2实验分析', 'text': analyzed['reason'],
                                      'model': analyzed['model'], 'raw_output': analyzed['raw_output'],
                                      'usage': analyzed['usage']},
                            reason='快模型未满足实验分流条件，已调用真实复杂分析并检查引用；结论仍需人员复核。')
                if analyzed['answer'] in ('一致', '未发现明确矛盾'):
                    task.update(action='review', status='待复核')
                else:
                    task.update(action='human', status='待人工核实')
            except Exception as exc:
                usage['failed_complex_model_requests'] += 1
                analyzed = getattr(exc, 'attempt', {})
                task.update(answer=None, score=None, distribution=None, action='human', status='待人工核实',
                            source='complex_model_error', reason=f'复杂分析未形成通过检查的结果（{type(exc).__name__}）；转人工，快模型原输出保留。',
                            analysis={'mode': '真实复杂分析失败', 'text': str(exc),
                                      'model': self.slow_model.info(), 'raw_output': analyzed.get('raw_output'),
                                      'usage': analyzed.get('usage', {})})
            spend = analyzed.get('usage', {})
            usage['complex_prompt_tokens'] += spend.get('prompt_tokens', 0)
            usage['complex_completion_tokens'] += spend.get('completion_tokens', 0)
            usage['complex_wall_ms'] += spend.get('wall_ms', 0)
        result.update(mode='真实快慢协同实验', adapter='jev_dual_experiment',
                      scope='快模型与通用生成模型真实运行；实验替代System 2；全部为辅助建议，不自动审批。')
        usage['workflow_ms'] = round((time.perf_counter() - start) * 1000, 2)
        return result
