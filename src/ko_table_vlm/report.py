"""여러 실행 결과(summary.json)를 하나의 비교표로.

  uv run python -m ko_table_vlm.report runs/docling__test runs/zs_qwen2b__test > runs/report.md
  uv run python -m ko_table_vlm.report runs/docling__test/summary_first100.json runs/zs_qwen2b__test   # 같은 부분집합 비교
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

COLS = [("teds", "TEDS"), ("teds_s", "TEDS-S"), ("cer", "CER↓"), ("merged_recall", "병합셀"),
        ("valid_rate", "유효"), ("latency_p50", "p50 s"), ("out_tokens_mean", "출력 토큰")]


def fmt(v):
    if v is None:
        return "-"
    return f"{v:.3f}" if isinstance(v, float) and v < 10 else str(v)


def main():
    # 인자: runs/<이름> 디렉터리(summary.json 사용) 또는 summary*.json 파일 경로
    paths = [Path(p) if p.endswith(".json") else Path(p) / "summary.json" for p in sys.argv[1:]]
    sums = [json.loads(p.read_text()) for p in paths if p.exists()]
    if not sums:
        raise SystemExit("summary.json 이 있는 runs/<이름> 디렉터리를 인자로 주세요")
    print("## 전체\n")
    print("| 실행 | 모델 | n | " + " | ".join(c[1] for c in COLS) + " |")
    print("|---|---|---|" + "---|" * len(COLS))
    for s in sums:
        o = s["overall"]
        print(f"| {s['run']} | {s['info'].get('model', '-')} | {o['n']} | " + " | ".join(fmt(o.get(k)) for k, _ in COLS) + " |")
    tags = sorted({t for s in sums for t in s["by_tag"]})
    print("\n## 태그별 TEDS\n")
    print("| 실행 | " + " | ".join(tags) + " |")
    print("|---|" + "---|" * len(tags))
    for s in sums:
        print(f"| {s['run']} | " + " | ".join(fmt(s["by_tag"].get(t, {}).get("teds")) for t in tags) + " |")


if __name__ == "__main__":
    main()
