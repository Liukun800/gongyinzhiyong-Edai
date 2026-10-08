"""CPU path inference of a pinned public AgentJev checkpoint. Shadow mode only."""
import hashlib
import json
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / 'models' / 'agentjev-public'
PINNED_SHA = 'a3c3503b71a04da0e30cbd17362f5733ba0a5ccae6d3eb5db7a84a2398a4953b'
REVISION = '0e2593e6e6c0eade0700712ac13c4389aa7654cc'


class InputTooLong(ValueError):
    pass


class PublicDecisionModel:
    def __init__(self, model_dir=MODEL_DIR, threads=4):
        started = time.perf_counter()
        import torch
        from safetensors.torch import load_file
        from transformers import AutoTokenizer, Qwen3Config
        from vendor.agentjev.model import AgentJevModel
        self.lock = threading.Lock()
        self.torch = torch
        torch.set_num_threads(threads)
        self.directory = Path(model_dir)
        weight_path = self.directory / 'model.safetensors'
        manifest = json.loads((self.directory / 'verified_manifest.json').read_text(encoding='utf-8'))
        if manifest.get('revision') != REVISION or not manifest.get('verified'):
            raise RuntimeError('Unverified model revision; run download_model.py')
        digest = hashlib.sha256()
        with weight_path.open('rb') as f:
            for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != PINNED_SHA:
            raise RuntimeError('Model weight hash mismatch')
        print('Loading verified public AgentJev checkpoint on CPU...', flush=True)
        self.tokenizer = AutoTokenizer.from_pretrained(self.directory, local_files_only=True, trust_remote_code=False)
        config = Qwen3Config.from_pretrained(self.directory, local_files_only=True)
        config._attn_implementation = 'sdpa'
        weights = load_file(str(weight_path), device='cpu')
        with torch.device('meta'):
            self.model = AgentJevModel(str(self.directory), backbone_config=config)
        self.model.load_state_dict(weights, strict=True, assign=True)
        del weights
        # Rotary frequency buffers are nonpersistent and need materializing after meta construction.
        backbone = self.model.path_encoder.backbone
        backbone.rotary_emb = type(backbone.rotary_emb)(config, device=torch.device('cpu'))
        if any(b.is_meta for b in self.model.buffers()) or any(p.is_meta for p in self.model.parameters()):
            raise RuntimeError('Unexpected unmaterialized model tensor')
        self.model.eval()
        self.max_tokens = 2048
        self.name = 'AgentJev-0.6B / public coding-completion checkpoint'
        self.load_seconds = round(time.perf_counter() - started, 2)
        self.dtype = str(next(self.model.parameters()).dtype)
        print(f'AgentJev ready: {self.dtype}, {self.load_seconds}s load; bank calibration disabled.', flush=True)

    def info(self):
        return {'name': self.name, 'repo': 'aimeigaoshou/agent-jev', 'revision': REVISION,
                'weight_sha256': PINNED_SHA, 'device': 'cpu', 'dtype': self.dtype,
                'encoder': 'independent_candidate_paths', 'shared_prefix_compute': False,
                'max_path_tokens': self.max_tokens, 'load_seconds': self.load_seconds,
                'bank_domain_trained': False, 'bank_domain_calibrated': False,
                'temperature': 1.0, 'auto_completion_enabled': False,
                'checkpoint_card_scope': 'coding-completion; not a credit model'}

    def decide(self, state, question, candidates):
        return self.decide_many([(state, question, candidates)])[0]

    def decide_many(self, requests):
        """Batch independent questions in one padded backbone pass."""
        from vendor.agentjev.contract import prepare, encode_paths
        if not requests:
            return []
        prepared_items = []
        candidates_by_request = []
        for state, question, candidates in requests:
            if len(candidates) > 3:
                raise ValueError('Bank demo supports at most 3 candidates')
            prepared = prepare({'state': state, 'questions': [{'id': 'decision', 'type': 'choice',
                                                               'question': question, 'options': candidates}]})
            try:
                paths, _, _ = encode_paths(prepared, self.tokenizer, self.max_tokens)
            except ValueError as exc:
                raise InputTooLong(str(exc)) from exc
            prepared_items.append(paths)
            candidates_by_request.append(list(candidates))
        started = time.perf_counter()
        torch = self.torch
        with self.lock, torch.inference_mode():
            flat_paths = [path for group in prepared_items for path in group]
            lengths = torch.tensor([len(path) for path in flat_paths], dtype=torch.long)
            width = int(lengths.max().item())
            pad_id = self.tokenizer.pad_token_id
            if pad_id is None:
                pad_id = self.tokenizer.eos_token_id or 0
            ids = torch.full((len(flat_paths), width), pad_id, dtype=torch.long)
            attention = torch.zeros_like(ids)
            for index, path in enumerate(flat_paths):
                ids[index, :len(path)] = torch.tensor(path, dtype=torch.long)
                attention[index, :len(path)] = 1
            outputs = self.model.path_encoder.backbone(input_ids=ids, attention_mask=attention, use_cache=False)
            hidden = outputs.last_hidden_state[torch.arange(len(flat_paths)), lengths - 1]

            group_count = len(prepared_items)
            candidate_count = max(len(group) for group in prepared_items)
            vectors = hidden.new_zeros((group_count, candidate_count, hidden.shape[-1]))
            mask = torch.zeros((group_count, candidate_count), dtype=torch.bool)
            offset = 0
            for index, group in enumerate(prepared_items):
                count = len(group)
                vectors[index, :count] = hidden[offset:offset + count]
                mask[index, :count] = True
                offset += count
            logits = self.model._score(vectors, mask).float()
            probabilities = torch.softmax(logits, dim=-1)
            if not torch.isfinite(probabilities[mask]).all():
                raise RuntimeError('Non-finite model output')
            values = probabilities.tolist()
            logit_values = logits.tolist()
        wall_ms = round((time.perf_counter()-started)*1000, 2)
        results = []
        for index, candidates in enumerate(candidates_by_request):
            scores = values[index][:len(candidates)]
            candidate_logits = logit_values[index][:len(candidates)]
            best = max(range(len(scores)), key=scores.__getitem__)
            group = prepared_items[index]
            results.append({'answer': candidates[best], 'score': scores[best],
                            'distribution': dict(zip(candidates, scores)),
                            'candidate_paths': len(group),
                            'input_path_tokens': sum(len(path) for path in group),
                            'generated_tokens': 0, 'wall_ms': wall_ms,
                            'logits': candidate_logits,
                            'score_semantics': 'raw candidate mass; not bank accuracy or credit risk',
                            'batch_size': len(requests), 'batch_wall_ms': wall_ms})
        return results


if __name__ == '__main__':
    model = PublicDecisionModel()
    result = model.decide('材料甲：同一主体在2026年8月全月正常营业。材料乙：同一主体在2026年8月整月停业且未经营。',
                          '两份同主体同期间的经营陈述是否存在明确矛盾？', ['发现明确矛盾', '未发现明确矛盾', '无法比较'])
    report = {'model': model.info(), 'smoke_result': result, 'note': 'Single engineering probe, not an accuracy test.'}
    (ROOT / 'qa' / 'real-model-smoke.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)
