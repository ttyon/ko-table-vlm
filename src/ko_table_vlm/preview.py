"""이미지와 정답(·예측) 표를 나란히 보는 HTML 페이지 생성.

  # 생성 데이터 눈으로 검증
  uv run python -m ko_table_vlm.preview --data data/generated/train/manifest.jsonl --n 30
  # 예측과 비교 (TEDS 낮은 순)
  uv run python -m ko_table_vlm.preview --data data/generated/test/manifest.jsonl --run runs/qwen2b_lora_r16 --worst
  # 실제 표 정답 초안 검수
  uv run python -m ko_table_vlm.preview --data data/real/labels

보기: 생성된 preview.html 을 브라우저로. SSH 원격이면
  uv run python -m http.server 8090 --bind 127.0.0.1   (프로젝트 루트에서)
  맥북: ssh -L 8090:127.0.0.1:8090 studio  →  http://127.0.0.1:8090/<경로>/preview.html
"""
from __future__ import annotations

import argparse
import html as H
import json
import os
from pathlib import Path

from .data import load_jsonl, load_manifest
from .otsl import otsl_to_table
from .table import extract_table_html, normalize_html

CSS = """body{font-family:-apple-system,sans-serif;margin:16px;background:#fafafa}
.item{background:#fff;border:1px solid #ddd;margin:12px 0;padding:10px}
.row{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start}
.row>div{flex:1;min-width:320px;overflow:auto}
img{max-width:100%;border:1px solid #eee}
table{border-collapse:collapse;font-size:12px}td{border:1px solid #888;padding:2px 6px}
h4{margin:4px 0}.bad{color:#c00}"""


def _render(table_html: str | None) -> str:
    return table_html or "<p class='bad'>(표 없음/파싱 실패)</p>"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="manifest.jsonl 또는 data/real/labels 디렉터리")
    ap.add_argument("--run", help="runs/<이름> (predictions/scores 함께 표시)")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--worst", action="store_true", help="TEDS 낮은 순으로")
    ap.add_argument("--out", help="출력 HTML 경로 (기본: run 또는 data 옆 preview.html)")
    args = ap.parse_args()

    data = Path(args.data)
    if data.is_dir():  # 실제 표 라벨 검수 모드
        items = [{"id": p.stem, "image_path": str((data.parent / "images" / f"{p.stem}.png").resolve()),
                  "html": normalize_html(p.read_text()), "draft": "DRAFT" in p.read_text()[:30]}
                 for p in sorted(data.glob("*.html"))]
        out = Path(args.out or data.parent / "preview.html")
    else:
        items = load_manifest(data)
        out = Path(args.out or (Path(args.run) if args.run else data.parent) / "preview.html")

    preds, scores = {}, {}
    if args.run:
        preds = {p["id"]: p for p in load_jsonl(Path(args.run) / "predictions.jsonl")}
        scores = {s["id"]: s for s in load_jsonl(Path(args.run) / "scores.jsonl")}
        items = [i for i in items if i["id"] in preds]
        if args.worst:
            items.sort(key=lambda i: scores.get(i["id"], {}).get("teds", 0))
    items = items[: args.n]

    parts = [f"<!doctype html><meta charset='utf-8'><title>preview</title><style>{CSS}</style>",
             f"<h2>{H.escape(str(data))} {('· ' + H.escape(args.run)) if args.run else ''} ({len(items)})</h2>"]
    for it in items:
        rel = os.path.relpath(it["image_path"], out.parent)
        head = H.escape(it["id"]) + (" <span class='bad'>[DRAFT]</span>" if it.get("draft") else "")
        if it["id"] in scores:
            s = scores[it["id"]]
            head += f" — TEDS {s['teds']:.3f} / TEDS-S {s['teds_s']:.3f} / CER {s['cer']:.3f}"
        if "meta" in it:
            head += f" <small>{H.escape(json.dumps(it['meta'].get('tags', []), ensure_ascii=False))}</small>"
        cols = [f"<div><h4>이미지</h4><img src='{H.escape(rel)}'></div>",
                f"<div><h4>정답</h4>{_render(it['html'])}</div>"]
        if it["id"] in preds:
            p = preds[it["id"]]
            if p.get("format") == "otsl":
                t = otsl_to_table(p["output"])
                ph = t.to_html() if t else None
            else:
                ph = normalize_html(extract_table_html(p["output"]) or "")
            cols.append(f"<div><h4>예측 ({p.get('latency_s')}s, {H.escape(str(p.get('finish_reason')))})</h4>{_render(ph)}</div>")
        parts.append(f"<div class='item'><b>{head}</b><div class='row'>{''.join(cols)}</div></div>")
    out.write_text("\n".join(parts))
    print(f"→ {out}")


if __name__ == "__main__":
    main()
