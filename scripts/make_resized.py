"""해상도 실험(010)용: manifest의 이미지를 긴 변 L 픽셀로 리사이즈한 사본 manifest를 만든다 (정답 HTML 동일).

  uv run python scripts/make_resized.py data/generated/test/manifest.jsonl data/res/test --sizes 640 960 1280 1600 --limit 50
  → data/res/test_640/manifest.jsonl ...

긴 변을 정확히 L로 맞춘다(축소·확대 모두). 확대는 정보가 늘지 않지만, VLM 입장에서는 글자당 패치 수가 늘어
작은 글자 인식이 좋아질 수 있으므로 같이 본다.
"""
import argparse
import json
from pathlib import Path

from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("manifest")
ap.add_argument("out_prefix")
ap.add_argument("--sizes", type=int, nargs="+", required=True)
ap.add_argument("--limit", type=int, default=0)
a = ap.parse_args()

src = Path(a.manifest)
rows = [json.loads(x) for x in src.read_text().splitlines() if x.strip()]
if a.limit:
    rows = rows[: a.limit]
for L in a.sizes:
    out = Path(f"{a.out_prefix}_{L}")
    (out / "images").mkdir(parents=True, exist_ok=True)
    with open(out / "manifest.jsonl", "w") as f:
        for r in rows:
            im = Image.open(src.parent / r["image"]).convert("RGB")
            w, h = im.size
            k = L / max(w, h)
            im = im.resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS if k < 1 else Image.BICUBIC)
            name = Path(r["image"]).name
            im.save(out / "images" / name)
            rr = dict(r, image=f"images/{name}")
            rr.setdefault("meta", {})
            rr["meta"] = dict(rr["meta"], width=im.size[0], height=im.size[1], resized_to=L)
            f.write(json.dumps(rr, ensure_ascii=False) + "\n")
    print(f"{out}: {len(rows)}")
