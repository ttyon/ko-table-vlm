"""실패 분석: 구조 오류 유형 분포 + 자주 틀리는 셀 텍스트 쌍.

  uv run python -m ko_table_vlm.analyze --data data/generated/test/manifest.jsonl --run runs/docling__test

구조 오류 유형 (샘플당 하나, 위에서부터 먼저 해당하는 것):
  invalid      : 표를 못 꺼냄 (출력 없음/형식 오류)
  truncated    : max_tokens에 걸려 잘림 (반복 생성 포함)
  row_count    : 행 수가 다름
  col_count    : 열 수가 다름
  span         : 행·열 수는 같지만 병합(rowspan/colspan) 배치가 다름
  text_only    : 구조는 완전히 같고 셀 텍스트만 다름
  exact        : 완전 일치
"""
from __future__ import annotations

import argparse
import collections

from .data import load_jsonl, load_manifest
from .otsl import otsl_to_table
from .table import extract_table_html, parse_table, to_grid


def classify(pred, gold, finish_reason):
    if pred is None:
        return "invalid"
    if finish_reason == "length":
        return "truncated"
    gc, gr, gcols, _ = to_grid(gold)
    pc, pr, pcols, _ = to_grid(pred)
    if pr != gr:
        return "row_count"
    if pcols != gcols:
        return "col_count"
    if {(c.r, c.c, c.rowspan, c.colspan) for c in pc} != {(c.r, c.c, c.rowspan, c.colspan) for c in gc}:
        return "span"
    if [c.text for c in pc] != [c.text for c in gc]:
        return "text_only"
    return "exact"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    gold = {r["id"]: r for r in load_manifest(args.data)}
    types, pairs = collections.Counter(), collections.Counter()
    by_tag = collections.defaultdict(collections.Counter)
    preds = load_jsonl(f"{args.run}/predictions.jsonl")
    for p in preds:
        g = parse_table(gold[p["id"]]["html"])
        t = otsl_to_table(p["output"]) if p.get("format") == "otsl" else parse_table(extract_table_html(p["output"]) or "")
        kind = classify(t, g, p.get("finish_reason"))
        types[kind] += 1
        for tag in gold[p["id"]]["meta"].get("tags", []):
            by_tag[tag][kind] += 1
        if t is not None:
            pm = {(c.r, c.c): c.text for c in to_grid(t)[0]}
            for c in to_grid(g)[0]:
                pv = pm.get((c.r, c.c), "∅")
                if pv != c.text and len(c.text) <= 14:
                    pairs[(c.text, pv)] += 1

    n = len(preds)
    order = ["exact", "text_only", "span", "col_count", "row_count", "truncated", "invalid"]
    print(f"## 구조 오류 유형 (n={n})\n")
    print("| 유형 | 전체 | " + " | ".join(sorted(by_tag)) + " |")
    print("|---|---|" + "---|" * len(by_tag))
    for k in order:
        print(f"| {k} | {types[k]} ({types[k] / n:.0%}) | " +
              " | ".join(str(by_tag[t][k]) for t in sorted(by_tag)) + " |")
    print(f"\n## 자주 틀린 셀 텍스트 (정답 → 예측, 상위 {args.top})\n")
    for (a, b), c in pairs.most_common(args.top):
        print(f"- {c}× `{a}` → `{b}`")


if __name__ == "__main__":
    main()
