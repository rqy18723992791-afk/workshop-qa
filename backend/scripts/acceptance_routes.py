"""验收留痕：端云路由两条路径 + 故障诊断完整链。

前提：后端已在 127.0.0.1:8000 运行，知识库已导入，Ollama 与 DeepSeek 可用。
运行：backend/.venv/Scripts/python.exe backend/scripts/acceptance_routes.py
输出：docs/evidence/route-*.json、docs/evidence/diagnosis-*.json/md
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "evidence"
OUT.mkdir(parents=True, exist_ok=True)


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def chat_stream(query: str, route_mode: str = "auto") -> dict:
    """消费 SSE 并记录事件序列、首字时间、完整答案。"""
    events: list[dict] = []
    started = time.perf_counter()
    first_delta_ms: int | None = None
    with httpx.Client(timeout=120) as client:
        with client.stream(
            "POST",
            f"{BASE}/api/chat/stream",
            json={"query": query, "route_mode": route_mode},
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                if event.get("type") == "delta" and first_delta_ms is None:
                    first_delta_ms = round((time.perf_counter() - started) * 1000)
                if event.get("type") != "delta":
                    events.append(event)
    done = next(e for e in events if e["type"] == "done")
    meta = next(e for e in events if e["type"] == "meta")
    return {
        "query": query,
        "route_mode": route_mode,
        "tested_at": now(),
        "route": done["route"],
        "route_reason": done["route_reason"],
        "model": done["model"],
        "max_score": round(meta["max_score"], 4),
        "min_sim": meta["min_sim"],
        "refused": done["refused"],
        "grounded": done["grounded"],
        "sources": [
            {
                "doc_no": s["doc_no"],
                "doc_title": s["doc_title"],
                "heading_path": s["heading_path"],
                "score": round(s["score"], 4),
            }
            for s in done["sources"]
        ],
        "answer": done["answer"],
        "first_delta_ms": first_delta_ms,
        "event_types": [
            e["type"] if e["type"] != "route" else f"route->{e['route']}"
            for e in events
        ],
        "switched_to_cloud": any(e["type"] == "route" for e in events),
    }


def diagnose() -> dict:
    """按固定分支走完整条链：SSR 损坏。"""
    steps = [
        ("safety", "done"),
        ("symptom", "single_drop"),
        ("heater_measure", "normal"),
        ("terminal_inspect", "no"),
        ("thermocouple_inspect", "no"),
        ("ssr_test", "fail"),
    ]
    with httpx.Client(timeout=30) as client:
        start = client.post(f"{BASE}/api/diag/sessions", json={"topic_id": "temp-anomaly"})
        start.raise_for_status()
        data = start.json()
        sid = data["session_id"]
        trace = [{"step": 1, "node": data["node"]["id"], "title": data["node"]["title"]}]
        for index, (node_id, option_id) in enumerate(steps, start=1):
            resp = client.post(
                f"{BASE}/api/diag/sessions/{sid}/answer",
                json={"node_id": node_id, "option_id": option_id},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("done"):
                break
            trace.append(
                {"step": index + 1, "node": data["node"]["id"], "title": data["node"]["title"]}
            )
        if not data.get("done"):
            raise RuntimeError("诊断链未在预期步骤内完成")
        report = data["report"]
        md = client.get(f"{BASE}/api/diag/sessions/{sid}/report.md")
        md.raise_for_status()
        (OUT / "diagnosis-report.md").write_text(md.text, encoding="utf-8")
        summary = {
            "tested_at": now(),
            "session_id": sid,
            "steps": trace,
            "report_no": report["report_no"],
            "conclusion": report["conclusion"]["title"],
            "level": report["conclusion"]["level"],
            "references": len(report["references"]),
            "process_rows": len(report["process"]),
        }
        (OUT / "diagnosis-session.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return summary


def main() -> None:
    cases = [
        ("route-local.json", "注塑机开机前需要检查什么？"),
        ("route-cloud.json", "注塑机螺杆磨损到什么程度必须更换？请给出判断标准和检测方法"),
        ("route-refusal.json", "如何做红烧肉？"),
    ]
    for filename, query in cases:
        record = chat_stream(query)
        (OUT / filename).write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"{filename}: route={record['route']} score={record['max_score']} "
              f"refused={record['refused']} first={record['first_delta_ms']}ms")

    diagnosis = diagnose()
    print(f"diagnosis: {diagnosis['report_no']} -> {diagnosis['conclusion']}")


if __name__ == "__main__":
    main()
