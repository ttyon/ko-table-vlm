"""manifest → mlx_vlm.train 학습 데이터(jsonl).

  uv run python -m ko_table_vlm.to_sft --train data/generated/train/manifest.jsonl \
      --valid data/generated/val/manifest.jsonl --out data/sft/html --format html

출력: <out>/train.jsonl, <out>/valid.jsonl
한 줄: {"images": ["/abs/path.png"], "messages": [{"role":"user","content": PROMPT},
                                                {"role":"assistant","content": 정답}]}
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .data import load_manifest
from .otsl import html_table_to_otsl
from .prompts import PROMPTS
from .table import parse_table


def convert(manifest: str, out_file: Path, fmt: str, max_chars: int) -> tuple[int, int]:
    kept = skipped = 0
    with open(out_file, "w") as f:
        for r in load_manifest(manifest):
            answer = r["html"] if fmt == "html" else html_table_to_otsl(parse_table(r["html"]))
            if len(answer) > max_chars:  # 너무 긴 표는 학습 시퀀스 길이·메모리 때문에 제외
                skipped += 1
                continue
            f.write(json.dumps({"images": [r["image_path"]], "messages": [
                {"role": "user", "content": PROMPTS[fmt]},
                {"role": "assistant", "content": answer}]}, ensure_ascii=False) + "\n")
            kept += 1
    return kept, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train", required=True)
    ap.add_argument("--valid", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--format", choices=list(PROMPTS), default="html")
    ap.add_argument("--max-chars", type=int, default=6000)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, src in [("train", args.train), ("valid", args.valid)]:
        k, s = convert(src, out / f"{name}.jsonl", args.format, args.max_chars)
        print(f"{name}: {k} rows (skipped {s} too long) → {out / f'{name}.jsonl'}")


if __name__ == "__main__":
    main()
