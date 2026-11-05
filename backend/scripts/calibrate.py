"""拒答阈值校准脚本：30 条问句，输出可复现的校准数据。

分类：
- positive：知识库里有明确答案，期望通过检索闸门；
- negative：与注塑完全无关，期望被检索闸门挡住；
- gray：属于注塑领域但知识库没有答案，应通过检索闸门、由生成层拒答。

运行：
    backend/.venv/Scripts/python.exe backend/scripts/calibrate.py
输出：
    docs/calibration-data.json（完整明细）
"""
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import config  # noqa: E402
from app.services import kb  # noqa: E402

QUERIES = [
    ("positive", "注塑机开机前需要检查什么"),
    ("positive", "注塑机正常停机步骤"),
    ("positive", "料筒温度异常怎么排查"),
    ("positive", "顶针不复位怎么处理"),
    ("positive", "液压系统压力低是什么原因"),
    ("positive", "模具保护报警 A-402 怎么排查"),
    ("positive", "产品飞边怎么调整工艺"),
    ("positive", "产品缩水怎么解决"),
    ("positive", "注塑机日常点检有哪些项目"),
    ("positive", "注塑机月保养做什么"),
    ("positive", "PP 料筒温度设定多少"),
    ("positive", "注塑机锁模区域安全要求"),
    ("positive", "注塑车间触电怎么应急处理"),
    ("positive", "加热圈正常电阻是多少"),
    ("positive", "保压压力和时间怎么设定"),
    ("negative", "如何做红烧肉"),
    ("negative", "今天上海天气怎么样"),
    ("negative", "帮我写一首关于春天的诗"),
    ("negative", "2026 年世界杯冠军是谁"),
    ("negative", "Python 怎么读取 Excel 文件"),
    ("negative", "推荐一部好看的科幻电影"),
    ("negative", "我的手机屏幕碎了怎么办"),
    ("negative", "股票行情怎么分析"),
    ("gray", "注塑机多少钱一台"),
    ("gray", "注塑机螺杆磨损到什么程度必须更换"),
    ("gray", "海天和震雄注塑机哪个好"),
    ("gray", "注塑机品牌排行榜"),
    ("gray", "注塑车间如何降低能耗"),
    ("gray", "注塑机出口到欧洲需要什么认证"),
    ("gray", "注塑机操作工月薪多少"),
]


def main() -> None:
    rows = []
    for label, query in QUERIES:
        result = kb.search(query, top_k=4)
        top = result["hits"][0] if result["hits"] else None
        rows.append(
            {
                "label": label,
                "query": query,
                "max_score": result["max_score"],
                "has_relevant_at_current": result["has_relevant"],
                "top1_doc": top["doc_no"] if top else "",
                "top1_heading": top["heading_path"] if top else "",
                "scores": [h["score"] for h in result["hits"]],
            }
        )

    def scores(kind: str) -> list[float]:
        return [r["max_score"] for r in rows if r["label"] == kind]

    pos, neg, gray = scores("positive"), scores("negative"), scores("gray")

    candidates = []
    for i in range(300, 701):
        t = i / 1000
        tp = sum(s >= t for s in pos)
        fp = sum(s >= t for s in neg)
        accuracy = (tp + (len(neg) - fp)) / (len(pos) + len(neg))
        candidates.append(
            {
                "threshold": t,
                "positive_pass": tp,
                "negative_pass": fp,
                "accuracy": round(accuracy, 4),
            }
        )
    best = max(candidates, key=lambda c: (c["accuracy"], c["positive_pass"], -c["negative_pass"]))
    # 若正负样本之间存在安全间隔，取间隔中点，避免贴着某一条样本过拟合；
    # 没有间隔时退回"准确率最高且召回优先"的阈值。
    min_pos, max_neg = min(pos), max(neg)
    if min_pos > max_neg:
        recommended = round((min_pos + max_neg) / 2, 3)
        safe_band = [max_neg, min_pos]
        positive_pass = sum(s >= recommended for s in pos)
        negative_pass = sum(s >= recommended for s in neg)
    else:
        recommended = best["threshold"]
        safe_band = None
        positive_pass = best["positive_pass"]
        negative_pass = best["negative_pass"]

    report = {
        "generated_by": "backend/scripts/calibrate.py",
        "current_threshold": config.RETRIEVAL_MIN_SIM,
        "top_k": config.RETRIEVAL_TOP_K,
        "summary": {
            "positive": {
                "count": len(pos),
                "min": min(pos),
                "avg": round(sum(pos) / len(pos), 4),
                "max": max(pos),
            },
            "negative": {
                "count": len(neg),
                "min": min(neg),
                "avg": round(sum(neg) / len(neg), 4),
                "max": max(neg),
            },
            "gray": {
                "count": len(gray),
                "min": min(gray),
                "avg": round(sum(gray) / len(gray), 4),
                "max": max(gray),
            },
            "recommended_threshold": recommended,
            "safe_band": safe_band,
            "recommended_positive_pass": positive_pass,
            "recommended_negative_pass": negative_pass,
            "best_accuracy_threshold": best["threshold"],
            "best_accuracy": best["accuracy"],
        },
        "queries": rows,
    }

    out = Path(__file__).resolve().parents[2] / "docs" / "calibration-data.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"current threshold: {config.RETRIEVAL_MIN_SIM}")
    print(f"positive: n={len(pos)} min={min(pos)} avg={report['summary']['positive']['avg']}")
    print(f"negative: n={len(neg)} max={max(neg)} avg={report['summary']['negative']['avg']}")
    print(f"gray:     n={len(gray)} min={min(gray)} max={max(gray)}")
    print(
        f"recommended threshold={recommended} (safe band {safe_band}) "
        f"positive_pass={positive_pass}/{len(pos)} "
        f"negative_pass={negative_pass}/{len(neg)}"
    )
    print(f"best accuracy threshold={best['threshold']} accuracy={best['accuracy']}")
    print(f"written: {out}")


if __name__ == "__main__":
    main()
