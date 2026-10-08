"""Observational raw-output capture; frozen inference code and settings unchanged."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "demo" / "experiments"))
import run_pm19_adaptation as experiment
from slow_model import LocalSlowModel
from shadow_engine import task_documents


def main():
    out = Path(__file__).resolve().parent
    supplement = out / "raw_capture_protocol.json"
    record = {
        "purpose": "Append unchanged full model returns / exception attempts for auditing",
        "changes_to_inference": False,
        "launcher_sha256": experiment.sha(Path(__file__)),
        "frozen_protocol_sha256": experiment.sha(out / "frozen_protocol.json"),
    }
    if supplement.exists():
        prior = json.loads(supplement.read_text(encoding="utf-8"))
        if any(prior[k] != v for k, v in record.items()):
            raise RuntimeError("Observational capture protocol mismatch")
    else:
        record["created_at"] = datetime.now(timezone.utc).isoformat()
        experiment.save(supplement, record)
    cases, *_ = experiment.require_frozen()

    def material_hash(task, docs):
        text = json.dumps({"task": task, "documents": docs}, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    case_ids = {}
    for case in cases:
        key = material_hash(case["task_id"], task_documents(case, case["task_id"]))
        case_ids.setdefault(key, []).append(case["id"])
    original = LocalSlowModel.analyze

    def observed(self, task_id, documents):
        key = material_hash(task_id, documents)
        row = {"case_ids": case_ids.get(key, []), "task_id": task_id,
               "material_sha256": key, "started_at": datetime.now(timezone.utc).isoformat()}
        try:
            result = original(self, task_id, documents)
        except Exception as exc:
            row.update({"error": type(exc).__name__, "attempt": getattr(exc, "attempt", {})})
            with (out / "qwen_raw_outputs.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            raise
        row["result"] = result
        with (out / "qwen_raw_outputs.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        return result

    LocalSlowModel.analyze = observed
    experiment.slow_compare()


if __name__ == "__main__":
    main()
