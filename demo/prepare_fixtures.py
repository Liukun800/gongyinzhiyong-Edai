"""Create deliberately synthetic workflow fixtures, never training/test claims."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def fingerprint(documents):
    return hashlib.sha256(json.dumps(documents, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def document(key, title, kind, text, period="2026-08"):
    return {"id": key, "title": title, "kind": kind, "subject": "仿真主体A", "period": period,
            "paragraphs": [{"id": "p1", "text": text}]}


def build():
    purpose = document("application", "申请用途说明", "purpose", "本次申请编号SIM-001，资金拟用于采购生产所需钢材。")
    order = document("order", "采购订单", "purpose", "订单关联申请SIM-001，采购标的为生产用钢材。")
    statement = document("statement", "经营情况说明", "business", "仿真主体A在2026年8月全月正常营业，期间未停业。")
    record = document("record", "经营情况记录", "business", "仿真主体A在2026年8月全月持续营业。")
    normal = [purpose, order, statement, record]
    conflict = document("record", "经营情况记录", "business", "仿真主体A在2026年8月整月停业，期间未开展经营。")
    other_period = document("record", "经营情况记录", "business", "仿真主体A在2026年7月整月停业，期间未开展经营。", "2026-07")
    revised_order = document("order", "原采购订单", "purpose", "订单关联申请SIM-001，原采购标的为生产设备；标的可按双方有效补充协议变更。")
    amendment = document("amendment", "采购补充协议", "purpose", "双方就关联申请SIM-001的订单签订有效补充协议：采购标的由生产设备变更为生产用钢材，其他条款不变。")
    complex_docs = [purpose, revised_order, amendment, statement, record]
    specifications = [
        ("D01", "材料一致", "用途相互支持，经营描述一致。", normal, "normal"),
        ("D02", "经营信息矛盾", "同主体、同月份的营业状态互相冲突。", [purpose, order, statement, conflict], "conflict"),
        ("D03", "证明材料缺失", "用途说明缺少相应采购订单，可补件后重跑。", [purpose, statement, record], "missing"),
        ("D04", "期间不可比", "经营说明属于8月，另一份记录属于7月。", [purpose, order, statement, other_period], "period"),
        ("D05", "多材料复杂分析", "订单存在有效变更，展示模拟升级与证据检查。", complex_docs, "complex"),
        ("D06", "分析服务故障", "与D05相同的材料，注入模拟超时，转人工。", complex_docs, "failure"),
    ]
    cases, labels = [], {}
    for key, title, description, docs, scenario in specifications:
        cases.append({"id": key, "title": title, "description": description, "documents": docs,
                      "supplement": order if key == "D03" else None})
        labels[key] = {"scenario": scenario, "document_sha256": fingerprint(docs),
                      "use_answer": "信息不足" if scenario == "missing" else "一致",
                      "business_answer": {"conflict": "发现明确矛盾", "period": "无法比较"}.get(scenario, "未发现明确矛盾"),
                      "label_origin": "按预设仿真事实通过代码构造，用于流程验收；尚未经银行业务人员核验，不是模型预测或生产样本"}
    labels["D03"]["supplemented_sha256"] = fingerprint([purpose, statement, record, order])
    dest = ROOT / "data"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    (dest / "annotations.json").write_text(json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8")
    return cases, labels


if __name__ == "__main__":
    cases, labels = build()
    print(f"Prepared {len(cases)} synthetic cases; annotations kept separately.")
