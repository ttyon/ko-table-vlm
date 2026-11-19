"""스캔 문서 모사(014): 실제 표 이미지에 '인쇄 → 스캔' 열화를 고정 seed로 적용한 사본 manifest를 만든다.

  uv run python scripts/make_scanlike.py data/real/manifest.jsonl data/scan/real
  → data/scan/real/manifest.jsonl (+ images/)

실제 스캔본이 아니라 **모사**다. 라이선스가 명확한 스캔 문서를 구하지 못해, 같은 표에 열화만 더해
"깨끗한 PDF 렌더 → 스캔 품질"로 바뀔 때 시스템별로 얼마나 무너지는지를 본다.
적용: 흑백 + 대비 저하 + 종이 배경색, 축소-확대(해상도 손실), ±1.2° 회전, 가우시안 흐림, 점 잡음, JPEG(품질 35~55)
"""
import argparse
import io
import json
import random
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

ap = argparse.ArgumentParser()
ap.add_argument("manifest")
ap.add_argument("out_dir")
ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args()

src = Path(a.manifest)
out = Path(a.out_dir)
(out / "images").mkdir(parents=True, exist_ok=True)
rng = random.Random(a.seed)
rows = [json.loads(x) for x in src.read_text().splitlines() if x.strip()]
with open(out / "manifest.jsonl", "w") as f:
    for r in rows:
        im = Image.open(src.parent / r["image"]).convert("L")
        im = ImageEnhance.Contrast(im).enhance(rng.uniform(0.65, 0.85))
        im = Image.eval(im, lambda v: int(25 + v * 0.85))  # 흰색이 아닌 종이 배경
        w, h = im.size
        k = rng.uniform(0.55, 0.75)
        im = im.resize((int(w * k), int(h * k)), Image.BILINEAR).resize((w, h), Image.BILINEAR)
        im = im.rotate(rng.uniform(-1.2, 1.2), resample=Image.BICUBIC, expand=True, fillcolor=235)
        im = im.filter(ImageFilter.GaussianBlur(rng.uniform(0.5, 0.9)))
        px = im.load()
        for _ in range(int(im.width * im.height * 0.002)):  # 점 잡음
            x, y = rng.randrange(im.width), rng.randrange(im.height)
            px[x, y] = rng.choice([30, 60, 200])
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "JPEG", quality=rng.randint(35, 55))
        name = Path(r["image"]).stem + ".jpg"
        (out / "images" / name).write_bytes(buf.getvalue())
        rr = dict(r, image=f"images/{name}")
        rr["meta"] = dict(r.get("meta", {}), scanlike=True, width=im.width, height=im.height,
                          tags=list(r.get("meta", {}).get("tags", [])) + ["scanlike"])
        f.write(json.dumps(rr, ensure_ascii=False) + "\n")
print(f"{out}: {len(rows)}")
