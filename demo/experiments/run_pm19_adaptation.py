"""PM19: grouped development-only adaptation and same-task model comparison.

Uses only the 54 project-authored synthetic development cases. The 28-case
review challenge set is never opened. All semantic models share input guards,
task wording, answer options, and leave-one-lineage-group-out folds.
"""
from __future__ import annotations

import argparse
import copy
import gc
import hashlib
import json
import os
import platform
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

DEMO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEMO))
from engine import ANSWERS
from shadow_engine import QUESTIONS, input_guard, model_state, task_documents

EXP = Path(__file__).resolve().parent
DATA = EXP / "domain_dev_v2"
OUT = Path(__file__).resolve().parents[2] / "评审整改" / "PM19_领域适配与同任务对照_20261006"
ART = OUT / "artifacts"
OUT.mkdir(parents=True, exist_ok=True)
ART.mkdir(parents=True, exist_ok=True)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save(path: Path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def load():
    names = ["combined_cases.json", "combined_labels.json", "eligibility.json", "development_folds.json"]
    manifest_path = DATA / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, expected in manifest["hashes"].items():
        if sha(DATA / name) != expected:
            raise ValueError(f"Domain development source hash mismatch: {name}")
    cases = json.loads((DATA / names[0]).read_text(encoding="utf-8"))
    labels = json.loads((DATA / names[1]).read_text(encoding="utf-8"))
    eligibility = json.loads((DATA / names[2]).read_text(encoding="utf-8"))
    folds = json.loads((DATA / names[3]).read_text(encoding="utf-8"))
    assert len(cases) == len(labels) == len(eligibility) == 54
    label = {r["id"]: r for r in labels}
    eligible = {r["id"]: r["semantic_training_eligible"] for r in eligibility}
    assert len({r["lineage_group"] for r in labels}) == 12
    for c in cases:
        assert c["id"] in label and c["task_id"] == label[c["id"]]["task_id"]
        assert c["id"] in eligible
    for fold in folds:
        tr, va = set(fold["train_ids"]), set(fold["validation_ids"])
        assert tr.isdisjoint(va)
        assert all(label[x]["lineage_group"] != fold["validation_lineage_group"] for x in tr)
        assert all(label[x]["lineage_group"] == fold["validation_lineage_group"] for x in va)
    return cases, label, eligible, folds, manifest


def feature_text(case):
    docs = task_documents(case, case["task_id"])
    return json.dumps(model_state(docs), ensure_ascii=False, sort_keys=True)


def base_rows(cases, labels, eligible):
    rows = {}
    for c in cases:
        tid = c["task_id"]
        guard = input_guard(task_documents(c, tid), tid)
        assert (guard is None) == eligible[c["id"]]
        rows[c["id"]] = {
            "case_id": c["id"], "task_id": tid,
            "lineage_group": labels[c["id"]]["lineage_group"],
            "expected": labels[c["id"]]["answer"],
            "expected_action": labels[c["id"]]["expected_action"],
            "rule_answer": guard[0] if guard else None,
            "semantic_eligible": eligible[c["id"]],
        }
    return rows


def freeze():
    frozen_path = OUT / "frozen_protocol.json"
    if frozen_path.exists():
        raise FileExistsError(f"Frozen protocol already exists; refusing to overwrite: {frozen_path}")
    cases, labels, eligible, folds, manifest = load()
    files = [DATA / n for n in ["combined_cases.json", "combined_labels.json", "eligibility.json", "development_folds.json", "manifest.json"]]
    model_files = [
        DEMO / "models/agentjev-public/verified_manifest.json",
        DEMO / "models/agentjev-public/model.safetensors",
        DEMO / "models/bert-base-chinese-local/local_manifest.json",
        DEMO / "models/bert-base-chinese-local/model.safetensors",
        DEMO / "models/qwen25-05b-instruct/verified_manifest.json",
        DEMO / "models/qwen25-05b-instruct/model.safetensors",
    ]
    model_files += [p for directory in [DEMO / "models/agentjev-public", DEMO / "models/bert-base-chinese-local",
                                       DEMO / "models/qwen25-05b-instruct"]
                    for p in directory.iterdir() if p.suffix in (".json", ".txt") and p not in model_files]
    code_files = [Path(__file__).resolve(), DEMO / "real_model.py", DEMO / "slow_model.py",
                  DEMO / "shadow_engine.py", DEMO / "engine.py", DEMO / "vendor/agentjev/model.py",
                  DEMO / "vendor/agentjev/contract.py"]
    freeze_record = {
        "protocol": "PM19-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "project-authored synthetic development diagnostic only; not bank validation",
        "holdout_policy": "review_holdout_v1 is not read; its previously exposed labels remain development-only",
        "dataset": {"cases": len(cases), "lineage_groups": len({x["lineage_group"] for x in labels.values()}),
                    "semantic_eligible": sum(eligible.values()), "rule_handled": sum(not v for v in eligible.values()),
                    "expert_labels": False},
        "comparison": {
            "shared": "same materials, input_guard, task questions, answer options, evidence text, and route mapping",
            "folds": "leave one lineage group out within each task; no case from validation lineage enters training",
            "systems": [
                "input_guard_only; semantic cases abstain to human",
                "AgentJev public coding checkpoint frozen zero-shot",
                "AgentJev public checkpoint with frozen backbone and candidate-head adaptation inside each training fold",
                "bert-base-chinese frozen CLS encoder with logistic head fitted inside each training fold",
                "character 2-4gram TF-IDF + logistic regression fitted inside each training fold",
                "Qwen2.5-0.5B-Instruct same-task constrained JSON generation, local substitute only"
            ],
            "no_auto_completion": True,
            "training_selection": "fixed hyperparameters; validation lineage is never used to select epochs or settings",
            "hyperparameters": {"seed": 19062026, "threads": 4, "jev_head_epochs": 40,
                "jev_head_lr": 0.0001, "jev_head_weight_decay": 0.01, "bert_logistic_C": 1.0,
                "tfidf_ngram": [2, 4], "tfidf_logistic_C": 1.0, "class_weight": "balanced",
                "qwen_max_new_tokens": 180, "qwen_max_time_seconds": 45, "qwen_do_sample": False},
            "limitations": ["synthetic labels are author-created and not independently reviewed",
                            "12 lineage groups are too few for a credible production/generalization claim",
                            "different model sizes and pretraining are not parameter-matched",
                            "latency is local CPU engineering measurement, not bank SLA or cost"]
        },
        "source_sha256": {str(p.relative_to(Path(__file__).resolve().parents[2])): sha(p) for p in files + model_files + code_files},
        "runtime": {"python": platform.python_version(), "platform": platform.platform()},
        "status": "frozen_before_new_model_runs"
    }
    save(frozen_path, freeze_record)
    print(json.dumps(freeze_record, ensure_ascii=False, indent=2))


def require_frozen():
    path = OUT / "frozen_protocol.json"
    if not path.exists():
        raise RuntimeError("Freeze the protocol before running models")
    frozen = json.loads(path.read_text(encoding="utf-8"))
    if frozen.get("protocol") != "PM19-v1" or frozen.get("status") != "frozen_before_new_model_runs":
        raise RuntimeError("Unexpected or incomplete frozen protocol")
    loaded = load()
    for rel, digest in frozen["source_sha256"].items():
        source = Path(__file__).resolve().parents[2] / rel
        if not source.exists() or sha(source) != digest:
            raise RuntimeError(f"Frozen source changed: {rel}")
    return (*loaded, frozen)


def encode_features():
    import torch
    from transformers import AutoModel, AutoTokenizer
    from real_model import PublicDecisionModel

    cases, labels, eligible, folds, manifest, frozen = require_frozen()
    rows = base_rows(cases, labels, eligible)
    prior = OUT / "progress.json"
    done = {}
    if prior.exists():
        previous = json.loads(prior.read_text(encoding="utf-8"))
        if previous.get("frozen_protocol_sha256") != sha(OUT / "frozen_protocol.json"):
            raise RuntimeError("Feature progress does not match frozen protocol")
        done = previous.get("feature_rows", {})
    for cid, row in rows.items():
        if not eligible[cid]:
            done[cid] = row
    torch.set_num_threads(4)
    fast = PublicDecisionModel(threads=4)
    for c in cases:
        cid = c["id"]
        if not eligible[cid] or cid in done and "jev_vectors" in done[cid]:
            continue
        tid = c["task_id"]
        docs = task_documents(c, tid)
        state = model_state(docs)
        prepared = {"state": state, "questions": [{"id": "decision", "type": "choice",
                      "question": QUESTIONS[tid], "options": ANSWERS[tid]}]}
        from vendor.agentjev.contract import prepare, encode_paths
        t0 = time.perf_counter()
        paths, _, _ = encode_paths(prepare(prepared), fast.tokenizer, fast.max_tokens)
        lens = torch.tensor([len(x) for x in paths], dtype=torch.long)
        width = int(lens.max().item())
        pad = fast.tokenizer.pad_token_id
        if pad is None: pad = fast.tokenizer.eos_token_id or 0
        ids = torch.full((len(paths), width), pad, dtype=torch.long)
        mask = torch.zeros_like(ids)
        for i, path in enumerate(paths):
            ids[i, :len(path)] = torch.tensor(path, dtype=torch.long)
            mask[i, :len(path)] = 1
        with torch.inference_mode():
            out = fast.model.path_encoder.backbone(input_ids=ids, attention_mask=mask, use_cache=False)
            vec = out.last_hidden_state[torch.arange(len(paths)), lens - 1].detach().cpu().numpy()
        with torch.inference_mode():
            zero_logits = fast.model._score(torch.from_numpy(vec).unsqueeze(0), torch.ones((1, len(vec)), dtype=torch.bool)).cpu().numpy()[0]
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        done[cid] = {**rows[cid], "jev_vectors": vec.tolist(),
                     "jev_zero_shot_logits": zero_logits.tolist(),
                     "jev_input_path_tokens": int(lens.sum()), "jev_feature_wall_ms": elapsed}
        save(prior, {"stage": "jev_features", "frozen_protocol_sha256": sha(OUT / "frozen_protocol.json"),
                     "completed": len(done), "feature_rows": done})
        print("JEV_FEATURE", cid, elapsed, flush=True)
    info = fast.info()
    del fast
    gc.collect()
    save(OUT / "agentjev_checkpoint.json", info)

    # Load the Chinese encoder only after the Jev process and its tensors are released.
    tokenizer = AutoTokenizer.from_pretrained(DEMO / "models/bert-base-chinese-local", local_files_only=True, trust_remote_code=False)
    bert = AutoModel.from_pretrained(DEMO / "models/bert-base-chinese-local", local_files_only=True,
                                     trust_remote_code=False, add_pooling_layer=False)
    bert.eval()
    for p in bert.parameters(): p.requires_grad_(False)
    for c in cases:
        cid = c["id"]
        if not eligible[cid]:
            continue
        if "bert_cls" in done[cid]:
            continue
        tid = c["task_id"]
        text = "\n".join(f"主体:{d['subject']} 期间:{d['period']}\n" + "\n".join(p["text"] for p in d["paragraphs"])
                          for d in task_documents(c, tid))
        t0 = time.perf_counter()
        inputs = tokenizer(QUESTIONS[tid], text, return_tensors="pt", truncation=False)
        n_tokens = int(inputs["input_ids"].shape[1])
        if n_tokens > 512:
            raise RuntimeError(f"BERT input exceeds 512 tokens for {cid}; no truncation allowed")
        with torch.inference_mode():
            vec = bert(**inputs).last_hidden_state[:, 0, :].cpu().numpy()[0]
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        done[cid]["bert_cls"] = vec.tolist()
        done[cid]["bert_tokens"] = n_tokens
        done[cid]["bert_feature_wall_ms"] = elapsed
        save(prior, {"stage": "bert_features", "frozen_protocol_sha256": sha(OUT / "frozen_protocol.json"),
                     "completed": len(done), "feature_rows": done})
        print("BERT_FEATURE", cid, elapsed, flush=True)
    save(OUT / "progress.json", {"stage": "features_complete",
                                  "frozen_protocol_sha256": sha(OUT / "frozen_protocol.json"),
                                  "completed": len(done), "feature_rows": done})
    print("FEATURES_COMPLETE", len(done), flush=True)


def run_oof():
    import torch
    from torch import nn
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline

    cases, labels, eligible, folds, manifest, frozen = require_frozen()
    report_path = OUT / "grouped_oof_comparison.json"
    if report_path.exists():
        raise FileExistsError(f"OOF report exists; refusing to overwrite: {report_path}")
    progress = json.loads((OUT / "progress.json").read_text(encoding="utf-8"))
    if progress.get("frozen_protocol_sha256") != sha(OUT / "frozen_protocol.json"):
        raise RuntimeError("Feature cache does not match frozen protocol")
    feats = progress["feature_rows"]
    if sum(eligible.values()) != sum("bert_cls" in feats.get(cid, {}) and "jev_vectors" in feats.get(cid, {}) for cid in eligible):
        raise RuntimeError("Missing paired Jev/BERT features; do not compare incomplete model pools")
    torch.manual_seed(19062026)
    torch.set_num_threads(4)

    class Head(nn.Module):
        def __init__(self, public_model):
            super().__init__()
            self.proj_in = copy.deepcopy(public_model.proj_in)
            self.set_encoder = copy.deepcopy(public_model.set_encoder)
            self.proj_out = copy.deepcopy(public_model.proj_out)
            self.scorer = copy.deepcopy(public_model.scorer)
        def forward(self, x):
            mask = torch.ones((x.shape[0], x.shape[1]), dtype=torch.bool)
            z = self.proj_in(x)
            z = self.set_encoder(z, mask)
            return self.scorer(x + self.proj_out(z))

    # Re-load pinned Jev checkpoint for the reference decision head. Feature extraction is complete.
    from real_model import PublicDecisionModel
    fast = PublicDecisionModel(threads=4)
    answer_index = {tid: {a: i for i, a in enumerate(answers)} for tid, answers in ANSWERS.items()}
    by_id = {c["id"]: c for c in cases}
    predictions = {name: {} for name in ["rule", "jev_frozen", "jev_head_adapted", "bert_frozen_linear", "tfidf"]}
    candidate_logits = {}
    fold_records = []
    for c in cases:
        if not eligible[c["id"]]:
            answer = feats[c["id"]]["rule_answer"]
            for name in predictions: predictions[name][c["id"]] = answer
        else:
            predictions["rule"][c["id"]] = None
    for fold_idx, fold in enumerate(folds):
        task = fold["task_id"]
        train_ids = [x for x in fold["train_ids"] if eligible[x] and labels[x]["task_id"] == task]
        val_ids = [x for x in fold["validation_ids"] if eligible[x] and labels[x]["task_id"] == task]
        if not val_ids: continue
        y = torch.tensor([answer_index[task][labels[x]["answer"]] for x in train_ids], dtype=torch.long)
        x_train = torch.tensor(np.asarray([feats[x]["jev_vectors"] for x in train_ids]), dtype=torch.float32)
        head = Head(fast.model)
        head.train()
        opt = torch.optim.AdamW(head.parameters(), lr=1e-4, weight_decay=0.01)
        start_train = time.perf_counter()
        for _ in range(40):
            opt.zero_grad(set_to_none=True)
            logits = head(x_train)
            loss = nn.functional.cross_entropy(logits, y)
            loss.backward()
            opt.step()
        train_ms = round((time.perf_counter() - start_train) * 1000, 2)
        head.eval()
        for cid in val_ids:
            vec = torch.tensor(np.asarray(feats[cid]["jev_vectors"]), dtype=torch.float32).unsqueeze(0)
            with torch.inference_mode():
                adapted_logits = head(vec)[0].numpy()
                frozen_logits = np.asarray(feats[cid]["jev_zero_shot_logits"], dtype=np.float64)
            predictions["jev_head_adapted"][cid] = ANSWERS[task][int(np.argmax(adapted_logits))]
            predictions["jev_frozen"][cid] = ANSWERS[task][int(np.argmax(frozen_logits))]
            candidate_logits[cid] = {"jev_head_adapted": adapted_logits.tolist(), "jev_frozen": frozen_logits.tolist()}
        head_path = ART / f"head_fold_{fold_idx + 1:02d}.pt"
        torch.save({"state_dict": head.state_dict(), "task_id": task, "train_ids": train_ids,
                    "validation_ids": val_ids, "frozen_protocol_sha256": sha(OUT / "frozen_protocol.json")}, head_path)
        # A frozen Chinese encoder representation with a task-specific logistic head.
        x_bert = np.asarray([feats[x]["bert_cls"] for x in train_ids], dtype=np.float32)
        y_text = [labels[x]["answer"] for x in train_ids]
        bert_head = make_pipeline(__import__("sklearn").preprocessing.StandardScaler(),
            LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000, random_state=19062026))
        bert_head.fit(x_bert, y_text)
        bert_x_val = np.asarray([feats[x]["bert_cls"] for x in val_ids], dtype=np.float32)
        for cid, answer in zip(val_ids, bert_head.predict(bert_x_val)):
            predictions["bert_frozen_linear"][cid] = str(answer)
        # Character n-gram classifier, fitted only on this fold's training lineages.
        tfidf = make_pipeline(TfidfVectorizer(analyzer="char", ngram_range=(2, 4), sublinear_tf=True),
            LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000, random_state=19062026))
        tfidf.fit([feature_text(by_id[x]) for x in train_ids], y_text)
        for cid, answer in zip(val_ids, tfidf.predict([feature_text(by_id[x]) for x in val_ids])):
            predictions["tfidf"][cid] = str(answer)
        fold_records.append({"task_id": task, "validation_lineage_group": fold["validation_lineage_group"],
            "train_ids": train_ids, "validation_ids": val_ids, "train_semantic_n": len(train_ids),
            "validation_semantic_n": len(val_ids), "jev_head_epochs": 40, "jev_head_lr": 1e-4,
            "jev_head_optimizer": "AdamW(weight_decay=0.01)", "jev_head_training_ms": train_ms,
            "bert_head": "StandardScaler + balanced logistic regression C=1",
            "tfidf": "char 2-4gram + balanced logistic regression C=1",
            "head_artifact": str(head_path), "head_sha256": sha(head_path)})
        save(OUT / "oof_progress.json", {"completed_folds": len(fold_records), "folds": fold_records,
              "predictions": predictions, "candidate_logits": candidate_logits,
              "frozen_protocol_sha256": sha(OUT / "frozen_protocol.json")})
        print("FOLD", fold_idx + 1, task, fold["validation_lineage_group"], len(train_ids), len(val_ids), flush=True)
    del fast
    if any(set(predictions[name]) != {c["id"] for c in cases} for name in predictions):
        missing = {name: sorted({c["id"] for c in cases} - set(ids)) for name, ids in predictions.items()}
        raise RuntimeError("Incomplete OOF predictions: " + json.dumps(missing, ensure_ascii=False))

    def summarize(name, pred):
        output = {}
        for task in [*ANSWERS, "all"]:
            selected = [c for c in cases if task == "all" or c["task_id"] == task]
            errors = [c["id"] for c in selected if pred[c["id"]] != labels[c["id"]]["answer"]]
            conflict = [c for c in selected if labels[c["id"]]["answer"] in ("存在明确矛盾", "发现明确矛盾")]
            misses = [c["id"] for c in conflict if pred[c["id"]] not in ("存在明确矛盾", "发现明确矛盾")]
            answered = [c for c in selected if pred[c["id"]] is not None]
            output[task] = {"n": len(selected), "answered": len(answered),
                "coverage": round(len(answered) / len(selected), 4),
                "correct": sum(pred[c["id"]] == labels[c["id"]]["answer"] for c in answered),
                "agreement_rate": round((len(selected) - len(errors)) / len(selected), 4),
                "semantic_n": sum(eligible[c["id"]] for c in selected),
                "semantic_correct": sum(eligible[c["id"]] and pred[c["id"]] == labels[c["id"]]["answer"] for c in selected),
                "conflict_n": len(conflict), "conflict_misses": misses,
                "wrong_ids": errors,
                "confusion": dict(Counter(f"{labels[c['id']]['answer']} -> {pred[c['id']]}" for c in selected))}
        return output

    full_rows = []
    for c in cases:
        cid = c["id"]
        full_rows.append({**{k: feats[cid].get(k) for k in ["case_id", "task_id", "lineage_group", "expected", "rule_answer", "semantic_eligible"]},
            "predictions": {name: p[cid] for name, p in predictions.items()},
            "candidate_logits": candidate_logits.get(cid),
            "jev_feature_wall_ms": feats[cid].get("jev_feature_wall_ms"),
            "bert_feature_wall_ms": feats[cid].get("bert_feature_wall_ms"),
            "jev_input_path_tokens": feats[cid].get("jev_input_path_tokens"),
            "bert_tokens": feats[cid].get("bert_tokens")} )
    report = {"created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "all predictions are leave-lineage-group-out development diagnostics on project-authored synthetic cases",
        "data": {"n": len(cases), "semantic_n": sum(eligible.values()), "rule_n": len(cases)-sum(eligible.values()),
                 "lineage_groups": len({x["lineage_group"] for x in labels.values()}), "expert_labels": False},
        "systems": {name: {"summary": summarize(name, pred), "rows": full_rows}
                    for name, pred in predictions.items()},
        "folds": fold_records,
        "models": {"jev": json.loads((OUT/"agentjev_checkpoint.json").read_text(encoding="utf-8")),
                   "bert": {"name": "bert-base-chinese", "method": "frozen encoder CLS + linear head", "domain_finetuning": "head only"}},
        "latency_scope": "feature extraction wall time only; excludes model cold load and fold-training time; local CPU, not bank SLA",
        "note": "The adapted Jev result is a project-trained candidate-head experiment on a public coding checkpoint, not official Jev or bank-trained model."}
    save(report_path, report)
    print(json.dumps({n: v["summary"]["all"] for n, v in report["systems"].items()}, ensure_ascii=False, indent=2))


def slow_compare():
    from slow_model import LocalSlowModel, SlowAnalysisError
    cases, labels, eligible, folds, manifest, frozen = require_frozen()
    report_path = OUT / "qwen_same_task_comparison.json"
    if report_path.exists():
        raise FileExistsError(f"Qwen report exists; refusing to overwrite: {report_path}")
    model = LocalSlowModel(threads=4, max_new_tokens=180, max_time=45)
    progress_path = OUT / "qwen_same_task_progress.json"
    previous = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {}
    if previous and previous.get("frozen_protocol_sha256") != sha(OUT / "frozen_protocol.json"):
        raise RuntimeError("Qwen progress does not match frozen protocol")
    rows_by_id = {r["case_id"]: r for r in previous.get("rows", [])}
    for c in cases:
        if c["id"] in rows_by_id:
            continue
        tid = c["task_id"]
        guard = input_guard(task_documents(c, tid), tid)
        if guard:
            record = {"answer": guard[0], "source": "input_rule", "latency_ms": 0,
                      "prompt_tokens": 0, "completion_tokens": 0, "error": None}
        else:
            t0 = time.perf_counter()
            try:
                result = model.analyze(tid, task_documents(c, tid))
                usage = result["usage"]
                record = {"answer": result["answer"], "source": "qwen_local_valid_json",
                          "latency_ms": round((time.perf_counter()-t0)*1000, 2),
                          "prompt_tokens": usage.get("prompt_tokens"),
                          "completion_tokens": usage.get("completion_tokens"), "error": None,
                          "reason": result["reason"], "evidence_refs": [e["document_id"]+":"+e["paragraph_id"] for e in result["evidence"]]}
            except Exception as exc:
                attempt = getattr(exc, "attempt", {})
                usage = attempt.get("usage", {})
                record = {"answer": None, "source": "qwen_invalid_or_failed",
                          "latency_ms": round((time.perf_counter()-t0)*1000, 2),
                          "prompt_tokens": usage.get("prompt_tokens"),
                          "completion_tokens": usage.get("completion_tokens"), "error": type(exc).__name__,
                          "raw_output": attempt.get("raw_output")}
        rows_by_id[c["id"]] = {"case_id": c["id"], "task_id": tid,
                                "expected": labels[c["id"]]["answer"], **record}
        rows = [rows_by_id[x["id"]] for x in cases if x["id"] in rows_by_id]
        save(progress_path, {"completed": len(rows), "total": len(cases), "rows": rows,
             "frozen_protocol_sha256": sha(OUT / "frozen_protocol.json"),
             "model": model.info(), "scope": "local substitute; synthetic development only"})
        print("QWEN", c["id"], record["source"], record["latency_ms"], flush=True)
    rows = [rows_by_id[x["id"]] for x in cases]
    def sum_rows(selected):
        answered = [r for r in selected if r["answer"] is not None]
        return {"n": len(selected), "answered": len(answered), "valid_response_rate": round(len(answered)/len(selected),4),
                "correct": sum(r["answer"] == r["expected"] for r in answered),
                "all_case_correct": sum(r["answer"] == r["expected"] for r in selected),
                "median_wall_ms_answered": float(np.median([r["latency_ms"] for r in answered])) if answered else None,
                "median_prompt_tokens_answered": float(np.median([r["prompt_tokens"] for r in answered])) if answered else None,
                "median_completion_tokens_answered": float(np.median([r["completion_tokens"] for r in answered])) if answered else None,
                "errors": [r["case_id"] for r in selected if r["answer"] is None],
                "conflict_misses": [r["case_id"] for r in selected if r["expected"] in ("存在明确矛盾","发现明确矛盾") and r["answer"] not in ("存在明确矛盾","发现明确矛盾")]}
    report = {"model": model.info(), "scope": "same task and materials; labels are author-created synthetic development labels",
        "summary": {task: sum_rows([r for r in rows if task == "all" or r["task_id"] == task])
                    for task in [*ANSWERS,"all"]}, "rows": rows,
        "latency_scope": "local CPU inference plus evidence validation; cold model load excluded"}
    save(report_path, report)
    print(json.dumps(report["summary"]["all"], ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=["freeze", "features", "oof", "qwen"])
    args = p.parse_args()
    if args.stage == "freeze": freeze()
    elif args.stage == "features": encode_features()
    elif args.stage == "oof": run_oof()
    else: slow_compare()


if __name__ == "__main__":
    main()
