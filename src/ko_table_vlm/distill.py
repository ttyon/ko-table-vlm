"""27B → 2B 증류 데이터 만들기 (015 사전 등록 방법).

  # 1) 라벨 없는 manifest + 페이지 단위 dev 분리
  uv run python -m ko_table_vlm.distill manifest --root data/distill --dev-frac 0.15 --seed 0
  # 2) 교사(27B)로 라벨링: 긴 변 1280 사본에 predict (queue_distill.sh)
  # 3) 필터 → SFT 데이터
  uv run python -m ko_table_vlm.distill filter --root data/distill --run runs/teacher27b__distill_1280 \
      --out data/sft/distill --min-text-agree 0.95

필터 (정답이 없으므로 신뢰도로 거른다):
  1. 출력이 정상 종료(잘림 아님), 표 추출 가능, 격자 일관
  2. 2행 이상, 2열 이상
  3. PDF 텍스트 레이어 대조: 셀을 공백으로 나눈 단어(2자 이상) 중 같은 페이지 원문에 (공백 무시, NFKC) 포함되는 비율 ≥ 기준
     (처음엔 셀 단위였으나 여러 줄 셀이 PDF 읽기 순서에서 쪼개져 맞는 라벨까지 버려져 단어 단위로 바꿈 — 016)
"""
from __future__ import annotations

import argparse
import json
import random
import re
import unicodedata
from pathlib import Path

from PIL import Image

from .data import load_jsonl
from .prompts import PROMPTS
from .table import clean_text, extract_table_html, normalize_html, parse_table, to_grid

ID_RE = re.compile(r"^(?P<doc>.+)_p(?P<page>\d{3})_t\d+$")
_SP = re.compile(r"\s+")
_LS = re.compile(r"(\S )+\S")


def _norm(s: str) -> str:
    return _SP.sub("", unicodedata.normalize("NFKC", s))


def cmd_manifest(root: Path, dev_frac: float, seed: int):
    imgs = sorted((root / "images").glob("*.png"))
    pages = sorted({(ID_RE.match(p.stem)["doc"], ID_RE.match(p.stem)["page"]) for p in imgs})
    rng = random.Random(seed)
    dev_pages = set(rng.sample(pages, max(1, round(len(pages) * dev_frac))))
    n = {"train": 0, "dev": 0}
    with open(root / "pool.jsonl", "w") as ft, open(root / "dev_unlabeled.jsonl", "w") as fd:
        for p in imgs:
            m = ID_RE.match(p.stem)
            w, h = Image.open(p).size
            split = "dev" if (m["doc"], m["page"]) in dev_pages else "train"
            rec = {"id": p.stem, "image": f"images/{p.name}", "html": "<table><tr><td></td></tr></table>",
                   "meta": {"doc": m["doc"], "page": int(m["page"]), "split": split, "width": w, "height": h,
                            "tags": ["distill_" + split]}}
            (fd if split == "dev" else ft).write(json.dumps(rec, ensure_ascii=False) + "\n")
            n[split] += 1
    print(f"pool(train 후보) {n['train']} / dev(라벨 없음, 페이지 단위 분리) {n['dev']} — 페이지 {len(pages)}쪽 중 dev {len(dev_pages)}쪽")


def _page_text(root: Path, doc: str, page: int, cache: dict) -> str:
    key = (doc, page)
    if key not in cache:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(str(root / "pdfs" / f"{doc}.pdf"))
        cache[key] = _norm(pdf[page - 1].get_textpage().get_text_range())
    return cache[key]


def cmd_filter(root: Path, run: Path, out: Path, min_agree: float, repeat: int, unit: str = "token"):
    pool = {json.loads(l)["id"]: json.loads(l) for l in open(root / "pool.jsonl")}
    preds = {p["id"]: p for p in load_jsonl(run / "predictions.jsonl")}
    cache: dict = {}
    kept, stats = [], {"total": 0, "truncated": 0, "invalid": 0, "grid": 0, "small": 0, "text": 0, "kept": 0}
    for sid, r in pool.items():
        if sid not in preds:
            continue
        stats["total"] += 1
        p = preds[sid]
        if p.get("finish_reason") == "length":
            stats["truncated"] += 1; continue
        html = normalize_html(extract_table_html(p["output"]) or "")
        t = parse_table(html or "")
        if t is None:
            stats["invalid"] += 1; continue
        cells, n_rows, n_cols, ok = to_grid(t)
        if not ok:
            stats["grid"] += 1; continue
        if n_rows < 2 or n_cols < 2:
            stats["small"] += 1; continue
        page_text = _page_text(root, r["meta"]["doc"], r["meta"]["page"], cache)
        if unit == "cell":
            texts = [_norm(c.text) for c in cells if clean_text(c.text)]
        else:  # 단어 단위: PDF 읽기 순서에서 여러 줄 셀은 옆 셀 글자와 섞이므로, 셀을 공백으로 나눈 단어(2자 이상)마다 확인
            texts = [_norm(w) for c in cells for w in clean_text(c.text).split(" ") if len(_norm(w)) >= 2]
        agree = sum(x in page_text for x in texts) / max(1, len(texts))
        if agree < min_agree:
            stats["text"] += 1; continue
        stats["kept"] += 1
        # 라벨 규칙(003·015): 한 글자씩 띄운 자간 라벨(구 분, 합 계)은 붙여 쓴다 — 교사(27B)는 보이는 대로 띄어 씀
        for row in t.rows:
            for c in row:
                if _LS.fullmatch(c.text):
                    c.text = c.text.replace(" ", "")
        html = t.to_html()
        kept.append({"images": [str((root / r["image"]).resolve())], "messages": [
            {"role": "user", "content": PROMPTS["html"]}, {"role": "assistant", "content": html}],
            "_meta": {"id": sid, "agree": round(agree, 3), "rows": n_rows, "cols": n_cols}})
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "train.jsonl", "w") as f:
        for _ in range(repeat):
            for k in kept:
                f.write(json.dumps({x: k[x] for x in ("images", "messages")}, ensure_ascii=False) + "\n")
    with open(out / "kept_meta.jsonl", "w") as f:
        for k in kept:
            f.write(json.dumps(k["_meta"], ensure_ascii=False) + "\n")
    (out / "filter_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2))
    print(json.dumps(stats, ensure_ascii=False), f"→ {out/'train.jsonl'} ({len(kept)}×{repeat})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("manifest"); p.add_argument("--root", default="data/distill")
    p.add_argument("--dev-frac", type=float, default=0.15); p.add_argument("--seed", type=int, default=0)
    p = sub.add_parser("filter"); p.add_argument("--root", default="data/distill"); p.add_argument("--run", required=True)
    p.add_argument("--out", default="data/sft/distill"); p.add_argument("--min-text-agree", type=float, default=0.95)
    p.add_argument("--repeat", type=int, default=2)
    p.add_argument("--unit", choices=["cell", "token"], default="token", help="텍스트 대조 단위 (016: cell→token으로 변경)")
    a = ap.parse_args()
    if a.cmd == "manifest":
        cmd_manifest(Path(a.root), a.dev_frac, a.seed)
    else:
        cmd_filter(Path(a.root), Path(a.run), Path(a.out), a.min_text_agree, a.repeat, a.unit)


if __name__ == "__main__":
    main()
