"""Explicit fixture simulator and deterministic routing. No model inference."""
import time
from prepare_fixtures import fingerprint

TASKS = {"USE_MATCH": "资金用途一致性核验", "BIZ_CONFLICT": "经营信息矛盾识别"}
ANSWERS = {"USE_MATCH": ["一致", "存在明确矛盾", "信息不足"],
           "BIZ_CONFLICT": ["发现明确矛盾", "未发现明确矛盾", "无法比较"]}


def evidence(documents, ids):
    return [{"document_id": d["id"], "paragraph_id": p["id"], "quote": p["text"],
             "title": d["title"], "subject": d["subject"], "period": d["period"]}
            for key in ids for d in documents if d["id"] == key for p in d["paragraphs"]]


def evaluate(case, annotation):
    start = time.perf_counter()
    annotation = annotation or {'document_sha256': None, 'scenario': 'custom'}
    docs = case["documents"]
    digest = fingerprint(docs)
    known = digest == annotation["document_sha256"]
    supplemented = case["id"] == "D03" and digest == annotation.get("supplemented_sha256")
    scenario = "normal" if supplemented else annotation["scenario"]
    tasks = []
    for task_id, name in TASKS.items():
        t = {"id": task_id, "name": name, "answer": None, "score": None,
             "calibration": "未校准；当前未运行模型", "status": "待人工核实", "action": "human",
             "reason": "", "evidence": [], "simulated_analysis_requests": 0,
             "analysis": None, "source": "fixture_simulator", "review": None}
        if not (known or supplemented):
            t["reason"] = "材料已改变，未命中预设演示样例。当前没有真实判断模型，保留为待人工核实。"
            t["source"] = "unsupported_input"
            tasks.append(t)
            continue
        t["answer"] = "一致" if task_id == "USE_MATCH" and supplemented else annotation["use_answer" if task_id == "USE_MATCH" else "business_answer"]
        t["evidence"] = evidence(docs, ["application", "order"] if task_id == "USE_MATCH" else ["statement", "record"])
        t["status"], t["action"] = "待复核", "review"
        t["reason"] = "预设仿真结论附原文证据；尚无经过验证的自动接受条件，需人员复核。"
        if task_id == "USE_MATCH" and scenario == "missing":
            t.update(status="待补充", action="supplement", reason="缺少与申请用途对应的采购证明。补充材料后重新核验。")
        elif task_id == "BIZ_CONFLICT" and scenario == "period":
            t.update(status="待补充", action="supplement", reason="两份材料分别属于2026年8月和7月，无法直接比较；需补充同期间记录。")
        elif task_id == "BIZ_CONFLICT" and scenario == "conflict":
            t.update(status="待人工核实", action="human", reason="同主体、同期间的全月正常营业与整月停业陈述冲突，按原型规则提交人工核实。")
        elif task_id == "USE_MATCH" and scenario in ("complex", "failure"):
            t["evidence"] = evidence(docs, ["application", "order", "amendment"])
            t["simulated_analysis_requests"] = 1
            if scenario == "failure":
                t.update(answer=None, status="待人工核实", action="human",
                         reason="已注入模拟分析超时。请求停止，保留三份材料供人工处理。",
                         analysis={"mode": "故障注入", "status": "timeout", "text": "模拟超时；未发生外部模型调用。"})
            else:
                t["reason"] = "预设复杂分析分支已完成；模拟意见经证据引用检查后进入人员复核。"
                t["analysis"] = {"mode": "预设分析意见", "status": "simulated_success",
                                 "text": "补充协议明确将原订单标的由生产设备变更为生产用钢材，与申请用途相符。该意见只解释给定仿真材料关系，不认定协议真实性。"}
        # References must exist verbatim in this material version.
        assert all(any(d["id"] == e["document_id"] and any(p["id"] == e["paragraph_id"] and p["text"] == e["quote"] for p in d["paragraphs"]) for d in docs) for e in t["evidence"])
        tasks.append(t)
    return {"case_id": case["id"], "revision": case["revision"], "mode": "流程模拟",
            "adapter": "fixture_simulator", "model": None, "tasks": tasks,
            "usage": {"actual_model_requests": 0,
                      "simulated_analysis_requests": sum(t["simulated_analysis_requests"] for t in tasks),
                      "workflow_ms": round((time.perf_counter() - start) * 1000, 3)},
            "scope": "仅辅助核验；不作贷款审批、额度、利率或放款决定。"}
