"""Derived reports only: never changes labels, model outputs, or default demo."""
import csv
import hashlib
import html
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
CONFLICT = {"存在明确矛盾", "发现明确矛盾"}
CLEAR = {"一致", "未发现明确矛盾"}
NAMES = {"rule": "输入规则（语义任务弃答）", "jev_frozen": "AgentJev固定公开权重",
         "jev_head_adapted": "AgentJev任务头适配", "bert_frozen_linear": "中文BERT＋分类头",
         "tfidf": "字符TF-IDF＋分类器", "qwen": "Qwen2.5-0.5B JSON生成"}


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def summary(rows, pred):
    answered = [r for r in rows if pred[r["case_id"]] is not None]
    semantic = [r for r in rows if r["semantic_eligible"]]
    conflicts = [r for r in rows if r["expected"] in CONFLICT]
    return {
        "n": len(rows), "answered": len(answered),
        "correct": sum(pred[r["case_id"]] == r["expected"] for r in rows),
        "semantic_n": len(semantic),
        "semantic_correct": sum(pred[r["case_id"]] == r["expected"] for r in semantic),
        "conflict_n": len(conflicts),
        "conflict_nonidentification": [r["case_id"] for r in conflicts if pred[r["case_id"]] not in CONFLICT],
        "conflict_abstained": [r["case_id"] for r in conflicts if pred[r["case_id"]] is None],
        "conflict_clear_answer": [r["case_id"] for r in conflicts if pred[r["case_id"]] in CLEAR],
        "conflict_insufficient_answer": [r["case_id"] for r in conflicts if pred[r["case_id"]] is not None and pred[r["case_id"]] not in CONFLICT | CLEAR],
        "false_conflicts": [r["case_id"] for r in rows if r["expected"] not in CONFLICT and pred[r["case_id"]] in CONFLICT],
        "wrong_ids": [r["case_id"] for r in rows if pred[r["case_id"]] != r["expected"]],
    }


def stats(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    return {"n": len(values), "min": min(values), "median": statistics.median(values),
            "max": max(values), "sum": sum(values)}


def main():
    oof, qwen = read("grouped_oof_comparison.json"), read("qwen_same_task_comparison.json")
    rows = oof["systems"]["jev_frozen"]["rows"]
    assert len(rows) == 54 and len(qwen["rows"]) == 54
    ids = {r["case_id"] for r in rows}
    assert ids == {r["case_id"] for r in qwen["rows"]}
    predictions = {key: {r["case_id"]: r["predictions"][key] for r in rows} for key in oof["systems"]}
    predictions["qwen"] = {r["case_id"]: r["answer"] for r in qwen["rows"]}
    for r in qwen["rows"]:
        assert r["expected"] == next(x["expected"] for x in rows if x["case_id"] == r["case_id"])
    summaries = {name: summary(rows, pred) for name, pred in predictions.items()}
    tasks = {task: {name: summary([r for r in rows if r["task_id"] == task], pred)
                   for name, pred in predictions.items()} for task in ["USE_MATCH", "BIZ_CONFLICT"]}
    lineage = {group: {name: summary([r for r in rows if r["lineage_group"] == group], pred)
                      for name, pred in predictions.items()} for group in sorted({r["lineage_group"] for r in rows})}
    semantic_ids = {r["case_id"] for r in rows if r["semantic_eligible"]}
    calls = [r for r in qwen["rows"] if r["case_id"] in semantic_ids]
    valid, failed = [r for r in calls if r["answer"] is not None], [r for r in calls if r["answer"] is None]
    raw = [json.loads(line) for line in (OUT / "qwen_raw_outputs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(raw) == 47
    assert {cid for r in raw for cid in r["case_ids"]} == semantic_ids
    timings = {
        "jev_features": stats([r["jev_feature_wall_ms"] for r in rows]),
        "bert_features": stats([r["bert_feature_wall_ms"] for r in rows]),
        "qwen_all_actual_calls": stats([r["latency_ms"] for r in calls]),
        "qwen_valid_calls": stats([r["latency_ms"] for r in valid]),
        "qwen_failed_calls": stats([r["latency_ms"] for r in failed]),
        "qwen_input_tokens_all_calls": stats([r["prompt_tokens"] for r in calls]),
        "qwen_output_tokens_all_calls": stats([r["completion_tokens"] for r in calls]),
        "jev_path_tokens": stats([r["jev_input_path_tokens"] for r in rows]),
        "head_training_ms": stats([r["jev_head_training_ms"] for r in oof["folds"]]),
    }
    frozen, adapted = predictions["jev_frozen"], predictions["jev_head_adapted"]
    changes = {
        "improved": [r["case_id"] for r in rows if frozen[r["case_id"]] != r["expected"] and adapted[r["case_id"]] == r["expected"]],
        "regressed": [r["case_id"] for r in rows if frozen[r["case_id"]] == r["expected"] and adapted[r["case_id"]] != r["expected"]],
        "changed_still_wrong": [r["case_id"] for r in rows if frozen[r["case_id"]] != adapted[r["case_id"]] and frozen[r["case_id"]] != r["expected"] and adapted[r["case_id"]] != r["expected"]],
    }
    protected = read("protected_current.json")
    hashes = {rel: {"expected": v["expected"], "actual": sha(ROOT / rel)} for rel, v in protected["files"].items()}
    passed = all(r["actual"] == r["expected"] for r in hashes.values())
    assert passed, "Existing default/data/documents changed"
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "scope": "54 self-authored synthetic development cases; no independent bank labels",
              "systems": summaries, "tasks": tasks, "lineage": lineage, "timing": timings, "adaptation_changes": changes,
              "qwen_actual_calls": len(calls), "qwen_valid_calls": len(valid), "qwen_failed_calls": len(failed),
              "raw_output_coverage": len(raw), "default_changed": False, "adapted_head_adopted": False,
              "decision": "当前适配头不采用：一致数未增加，参考矛盾未识别增加。其他路线仍需独立数据与强模型对照。",
              "bank_connected": False, "independent_business_reviews": 0, "calibration_performed": False,
              "protected_hashes": hashes, "protected_passed": passed}
    (OUT / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with (OUT / "逐例同任务对照.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["案例", "任务", "案例族", "参考标签（未独立复核）", "语义样本", *NAMES.values()])
        for r in rows:
            writer.writerow([r["case_id"], r["task_id"], r["lineage_group"], r["expected"], r["semantic_eligible"],
                             *[predictions[k][r["case_id"]] or "弃答/失败转人工" for k in NAMES]])
    headings = ["方案", "参考一致/54", "语义一致/47", "矛盾未识别/18", "其中弃答", "矛盾误报/36", "有效回答/54"]
    lines = ["| " + " | ".join(headings) + " |", "|" + "---|" * len(headings)]
    for name, s in summaries.items():
        lines.append(f"| {NAMES[name]} | {s['correct']}/54 | {s['semantic_correct']}/47 | {len(s['conflict_nonidentification'])}/18 | {len(s['conflict_abstained'])} | {len(s['false_conflicts'])}/36 | {s['answered']}/54 |")
    md = """# 领域头部适配与同任务对照结果

作品：工银智涌 e贷——基于Jev式判断与快慢协同的贷前材料核验引擎；数字金融赛道。

## 结论与产品取舍

本轮完成实际特征提取、按12个案例族隔离的开发对照，以及其中10个语义案例族的任务头适配；另外2个仅含输入规则的案例族不训练语义头。六条处理路线均保留逐例结果。当前适配头不替换Demo默认模型：与固定公开权重相比，参考一致数未增加，明确矛盾未识别增加。工程边界保持为材料辅助核验与人员承接，尚不能据此证明自动核验、成本节约或审批提速。

## 同任务结果

""" + "\n".join(lines) + f"""

全部54份由项目编制，其中47份语义资料、7份共享输入规则资料、12个案例族，两项任务各27份。训练采取留一案例族验证，每一资料只取得一次折外输出；验证族不参与对应训练或超参数选择。规则方案只判断输入条件，对语义任务弃答交人工。表中规则的18条矛盾未识别均为弃答，不是自动给出安全结论。所有参考标签均未独立业务复核。

Jev适配改变：改善{len(changes['improved'])}例、退化{len(changes['regressed'])}例、改变后仍不一致{len(changes['changed_still_wrong'])}例。逐例保留原始候选logits与各模型答案，不能将候选分数称为校准置信度或违约概率。

Qwen共真实调用{len(calls)}次，其中有效输出{len(valid)}次、失败{len(failed)}次；7份规则资料不调用生成模型。失败保留在分母中并转人工，未补入预设答案；全部47次成功/失败原始输出另有逐条留档。

## 资源与响应实测

Jev特征提取中位{timings['jev_features']['median']:.2f}毫秒，BERT特征提取中位{timings['bert_features']['median']:.2f}毫秒；Qwen实际调用（含失败）中位{timings['qwen_all_actual_calls']['median']:.2f}毫秒。前两项不含冷加载、训练和后续流程；Qwen含生成与引用校验，输出任务范围不同。均为本机CPU观察，不能换算为银行端到端SLA。当前Jev编码器按候选重复处理前缀，不能套用官方服务时延。

Qwen输入Token合计{timings['qwen_input_tokens_all_calls']['sum']}、输出合计{timings['qwen_output_tokens_all_calls']['sum']}，均含失败调用；Jev候选路径Token合计{timings['jev_path_tokens']['sum']}。Token口径不同，不能据此直接计算API费用。人员工时、内网资源单价、完整成本及整笔审批时间未实测。

## 工程设计与实验边界

领域适配仅训练固定Qwen3公开编码底座之上的候选判断头，不是官方Jev训练，也未进行底座全参微调或概率校准。公开权重原为代码完成判断用途，不能开箱宣称适用于信贷。BERT为固定中文CLS编码加标准化分类头；字符模型为2—4gram加分类器；Qwen为0.5B本地实验替代模型，要求答案、简短理由和原文引用，不代表工银智涌或强大模型能力。

本轮使用固定超参数，没有依分数再调节训练轮数或阈值。各模型预训练、参数量、输出要求不同，实验比较的是具体可选方案，不能归结为Jev普遍优于Transformer或SLM/LLM。当前没有重新跑双系统，也没有证明路由后的质量或经济增量。

旧28份挑战已在历史工作中暴露，本轮未纳入训练或评价。运行期间曾为查阅报告样式读取PM14历史报告，其中包含旧挑战记录；读取发生在本轮协议冻结后，没有据此修改本轮样本、问题、超参数或结果。故仍不能把当前开发诊断称为未见独立测试。

## 银行验证交付

拟议位置是材料归集后、综合审查前，先由银行确认与工小审现有任务的能力重叠。业务交付是两项核验建议、疑点原文位置、缺件事项和人员处理记录。不能将本组件与银行现行“全量大模型处理”的假设当作已核实事实。

已形成银行离线交接说明、六张空白测量/验收表及仿真盲复核输入。现有PM18本地接口与故障回退记录可供技术评估；75项软件测试是历史工程证据，本轮未复跑，不能替代领域质量。银行离线环境、授权数据与业务独立复核仍待银行提供。

下一阶段应使用授权材料和独立参考标签，冻结合理训练的分类器、Jev式判断和能力匹配的短输出生成模型对照；质量达到银行预设条件后，再测人员定位与复核时间、完整费用和全链路时延。当前适配候选保留作为诊断，默认原型及Word均保持。

## 可复核文件

- frozen_protocol.json：运行前协议、数据/代码/模型哈希与固定参数。
- grouped_oof_comparison.json：全部六类答案中的前五类及10个语义案例族的折外训练记录；artifacts内保留每折Jev判断头。2个纯规则案例族不训练语义头。
- qwen_same_task_comparison.json / qwen_raw_outputs.jsonl：生成对照及全部原始输出。
- summary.json / 逐例同任务对照.csv：派生指标、错误分类与配对输出。
- 银行离线验证交接说明.md / 银行离线验证交接包：拟议接入与真实验证所需表单。
"""
    (OUT / "领域适配与对照结论.md").write_text(md, encoding="utf-8")
    # Editable SVG: one denominator, descriptive results, no unsupported bank benefits.
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="620" viewBox="0 0 1200 620">',
           '<rect width="1200" height="620" fill="#ffffff"/>',
           '<g font-family="Microsoft YaHei, sans-serif" fill="#123957">',
           '<text x="45" y="52" font-size="26" font-weight="bold">同任务开发对照：语义参考一致数</text>',
           '<text x="45" y="86" font-size="17">47份自编语义资料 · 留案例族验证 · 参考标签未独立业务复核</text>']
    for index, name in enumerate(NAMES):
        s = summaries[name]
        y = 130 + index * 63
        value = s["semantic_correct"]
        color = ["#bccddd", "#164c8a", "#277dc5", "#4a9ad6", "#79b3df", "#a4c7e6"][index]
        svg += [f'<text x="45" y="{y + 22}" font-size="18">{html.escape(NAMES[name])}</text>',
                f'<rect x="405" y="{y}" width="600" height="30" rx="4" fill="#edf3f9"/>',
                f'<rect x="405" y="{y}" width="{600 * value / 47:.2f}" height="30" rx="4" fill="{color}"/>',
                f'<text x="1025" y="{y + 23}" font-size="19">{value}/47</text>']
    svg += ['<text x="45" y="540" font-size="17">当前头部适配不采用：一致数未增加，矛盾未识别由1例增至2例。</text>',
            '<text x="45" y="575" font-size="16">规则对语义任务弃答；生成失败纳入分母。结果不代表银行准确率或业务收益。</text>',
            '</g></svg>']
    (OUT / "同任务开发对照_蓝色.svg").write_text("\n".join(svg), encoding="utf-8")
    table_rows = ''.join('<tr>' + ''.join(f'<td>{html.escape(v)}</td>' for v in line.split('|')[1:-1]) + '</tr>' for line in lines[2:])
    details = []
    for r in rows:
        cells = ' · '.join(f'{NAMES[k]}：{predictions[k][r["case_id"]] or "弃答/失败"}' for k in NAMES)
        details.append(f'<details><summary>{r["case_id"]} / {r["task_id"]} / {r["lineage_group"]}</summary><p>参考标签（未独立复核）：{r["expected"]}</p><p>{html.escape(cells)}</p></details>')
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>领域适配与对照报告</title><style>body{margin:0;background:#eef4fa;color:#163b5b;font:16px/1.7 "Microsoft YaHei",sans-serif}main{max-width:1120px;margin:auto;padding:28px}header{background:linear-gradient(120deg,#143e6b,#267ec4);color:white;padding:28px;border-radius:14px}section,details{background:white;padding:22px;margin-top:18px;border:1px solid #d6e2ed;border-radius:10px}h1{font-size:27px}h2{font-size:22px}img{max-width:100%;height:auto}.scroll{overflow:auto}table{border-collapse:collapse;min-width:1020px;width:100%;font-size:14px}td,th{padding:10px;border-bottom:1px solid #dce5ee;text-align:left}th{background:#e8f2fc}a{color:#176aba}summary{cursor:pointer}@media(max-width:600px){main{padding:12px}header,section,details{padding:16px}h1{font-size:22px}}</style><main><header><p>工银智涌 e贷 · 数字金融 · PM19</p><h1>领域头部适配与同任务开发对照</h1><p>当前适配头不替换默认模型：参考一致数未增加，矛盾未识别增加。</p></header><section><h2>先比较质量，再讨论收益</h2><p>54份自编仿真资料，47份语义任务，7份共享规则处理，12个案例族；无独立业务标签。训练按案例族隔离，所有错误、弃答和生成失败保留。</p><img src="同任务开发对照_蓝色.svg" alt="47份语义任务参考一致数对照"><div class="scroll"><table><thead><tr>''' + ''.join(f'<th>{x}</th>' for x in headings) + '</tr></thead><tbody>' + table_rows + '''</tbody></table></div><p>规则的矛盾未识别全部为弃答转人工，不能按错误放行解读。参考一致数不等于银行准确率。</p></section><section><h2>接入工小审前需要验证什么</h2><p>位置：材料归集后、综合审查前。交付：用途与经营核验建议、原文位置、待核实事项和处理记录。银行先确认现有能力重叠，随后提供授权环境与材料、独立标签、预先验收条件。质量达标后测人员工作时间和完整成本。</p><p><a href="银行离线验证交接说明.md">银行交接说明</a> · <a href="银行离线验证交接包/使用说明.md">六张验证表使用说明</a> · <a href="领域适配与对照结论.md">完整结果与边界</a> · <a href="逐例同任务对照.csv">逐例CSV</a> · <a href="summary.json">统计JSON</a></p></section><section><h2>54份逐例输出</h2><p>用途与经营任务分开展示；此处不预设复核通过，不以示范答案代替模型结果。</p>''' + ''.join(details) + '</section></main></html>'
    (OUT / "领域适配开发报告.html").write_text(page, encoding="utf-8")
    print(json.dumps({"systems": summaries, "timing": timings, "changes": changes, "protected": passed}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
