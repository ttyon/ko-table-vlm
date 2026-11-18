"""예측 채점 → 샘플별 점수 + 요약 (전체 / 태그별).

  uv run python -m ko_table_vlm.evaluate --data data/generated/test/manifest.jsonl --run runs/qwen27b_zeroshot

출력: runs/<name>/scores.jsonl, summary.json, summary.md
"""
from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import asdict
from pathlib import Path

from .data import load_jsonl, load_manifest
from .metrics import score_prediction
from .otsl import otsl_to_table


def pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q / 100 * (len(xs) - 1))))]


def aggregate(scores: list[dict]) -> dict:
    n = len(scores)
    if n == 0:
        return {"n": 0}
    mean = lambda k: round(statistics.fmean(s[k] for s in scores), 4)  # noqa: E731
    merged = [s["merged_recall"] for s in scores if s["merged_recall"] is not None]
    lat = [s["latency_s"] for s in scores if s.get("latency_s") is not None]
    toks = [s["completion_tokens"] for s in scores if s.get("completion_tokens")]
    return {
        "n": n,
        "teds": mean("teds"), "teds_s": mean("teds_s"), "cer": mean("cer"),
        "valid_rate": mean("valid"), "grid_ok_rate": mean("grid_ok"),
        "merged_recall": round(statistics.fmean(merged), 4) if merged else None, "n_merged": len(merged),
        "truncated_rate": round(sum(s.get("finish_reason") == "length" for s in scores) / n, 4),
        "error_rate": round(sum(str(s.get("finish_reason", "")).startswith("error") for s in scores) / n, 4),
        "latency_p50": pct(lat, 50), "latency_p95": pct(lat, 95),
        "out_tokens_mean": round(statistics.fmean(toks), 1) if toks else None,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--limit", type=int, default=0, help="manifest 앞 N개만 채점 (predict --limit 과 같은 부분집합으로 공정 비교)")
    ap.add_argument("--ignore-space", action="store_true", help="셀 텍스트 공백 무시 (민감도 분석)")
    ap.add_argument("--out-suffix", default="", help="결과 파일 이름 뒤에 붙일 접미사 (예: _first100)")
    args = ap.parse_args()

    run = Path(args.run)
    gold_rows = load_manifest(args.data)
    if args.limit:
        gold_rows = gold_rows[: args.limit]
    gold = {r["id"]: r for r in gold_rows}
    preds = {p["id"]: p for p in load_jsonl(run / "predictions.jsonl")}
    missing = [i for i in gold if i not in preds]
    if missing:
        print(f"주의: 예측 없는 샘플 {len(missing)}개는 제외 (예: {missing[:3]})")

    scores = []
    for sid, p in preds.items():
        if sid not in gold:
            continue
        g = gold[sid]
        table = otsl_to_table(p["output"]) if p.get("format") == "otsl" else None
        sc = score_prediction(None if table else p["output"], g["html"], pred_table=table, ignore_space=args.ignore_space)
        usage = p.get("usage") or {}
        scores.append({"id": sid, **asdict(sc), "tags": g.get("meta", {}).get("tags", []),
                       "latency_s": p.get("latency_s"), "finish_reason": p.get("finish_reason"),
                       "completion_tokens": usage.get("completion_tokens")})

    sfx = args.out_suffix
    with open(run / f"scores{sfx}.jsonl", "w") as f:
        for s in scores:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    by_tag = {}
    for tag in sorted({t for s in scores for t in s["tags"]}):
        by_tag[tag] = aggregate([s for s in scores if tag in s["tags"]])
    run_info = json.loads((run / "run.json").read_text()) if (run / "run.json").exists() else {}
    summary = {"run": run.name + sfx, "info": run_info, "overall": aggregate(scores), "by_tag": by_tag}
    (run / f"summary{sfx}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))

    o = summary["overall"]
    lines = [f"# {run.name}{sfx}", "", f"- 데이터: `{args.data}` (n={o['n']})",
             f"- 모델: `{run_info.get('model')}` / 형식 {run_info.get('format')} / 프롬프트 {run_info.get('prompt_version')}",
             "", "| 구분 | n | TEDS | TEDS-S | CER↓ | 병합셀 | 유효 | 잘림 | p50 s | p95 s |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for name, a in [("전체", o)] + list(by_tag.items()):
        lines.append(f"| {name} | {a['n']} | {a['teds']:.3f} | {a['teds_s']:.3f} | {a['cer']:.3f} | "
                     f"{'-' if a['merged_recall'] is None else f'{a['merged_recall']:.3f}'} | {a['valid_rate']:.2f} | "
                     f"{a['truncated_rate']:.2f} | {a['latency_p50'] or '-'} | {a['latency_p95'] or '-'} |")
    (run / f"summary{sfx}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
