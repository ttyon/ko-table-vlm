"""실제 문서 표 테스트셋(test-real) 만들기 도구.

순서:
  1) PDF를 data/real/pdfs/ 에 넣고 출처를 data/real/SOURCES.md 에 기록 (공공누리 등 이용조건 확인)
  1-1) (큰 PDF) 표가 있는 페이지만 고정 seed로 샘플링:  uv run python -m ko_table_vlm.real subset --n-pages 25
  2) 표 자동 검출·잘라내기 (Docling 레이아웃):
       uv run --extra docling python -m ko_table_vlm.real detect
     또는 수동: 페이지 이미지 → bbox 지정
       uv run python -m ko_table_vlm.real pages             # data/real/pages/*.png
       (crops.json 작성: [{"id": "doc1_p3_t1", "page": "doc1_p003.png", "bbox": [x0, y0, x1, y1]}])
       uv run python -m ko_table_vlm.real crop data/real/crops.json
  3) 정답 초안 생성 (큰 모델로):  uv run python -m ko_table_vlm.real draft
       → data/real/labels/<id>.html (첫 줄 '<!-- DRAFT -->')
  4) 초안을 직접 고친다. 다 고친 파일은 첫 줄 '<!-- DRAFT -->' 를 지운다.
       검수 도우미: uv run python -m ko_table_vlm.preview --data data/real/labels  (이미지 옆에 초안 렌더링)
  5) 검수 끝난 것만 manifest 로:  uv run python -m ko_table_vlm.real build
       → data/real/manifest.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from .table import normalize_html, parse_table, to_grid

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "data" / "real"
DRAFT_MARK = "<!-- DRAFT -->"


def cmd_pages(scale: float):
    import pypdfium2 as pdfium
    (REAL / "pages").mkdir(parents=True, exist_ok=True)
    for pdf in sorted((REAL / "pdfs").glob("*.pdf")):
        doc = pdfium.PdfDocument(str(pdf))
        for i in range(len(doc)):
            out = REAL / "pages" / f"{pdf.stem}_p{i + 1:03d}.png"
            if not out.exists():
                doc[i].render(scale=scale).to_pil().save(out)
        print(f"{pdf.name}: {len(doc)} pages")


def cmd_subset(n_pages: int, seed: int, pattern: str):
    """큰 PDF에서 표가 있을 법한 페이지(텍스트에 pattern 포함)를 seed로 고정 샘플링해 작은 PDF로 만든다.
    원본은 data/real/pdfs/_full/ 로 옮기고, 샘플 PDF를 data/real/pdfs/ 에 둔다 (detect 대상)."""
    import random
    import pypdfium2 as pdfium
    full = REAL / "pdfs" / "_full"
    full.mkdir(parents=True, exist_ok=True)
    for pdf in sorted((REAL / "pdfs").glob("*.pdf")):
        src = full / pdf.name
        pdf.rename(src)
        doc = pdfium.PdfDocument(str(src))
        cands = [i for i in range(len(doc)) if pattern in doc[i].get_textpage().get_text_range()]
        picked = sorted(random.Random(seed).sample(cands, min(n_pages, len(cands))))
        out = pdfium.PdfDocument.new()
        out.import_pages(doc, picked)
        out.save(str(REAL / "pdfs" / pdf.name))
        (REAL / "pdfs" / f"{pdf.stem}.pages.txt").write_text(",".join(str(i + 1) for i in picked) + "\n")
        print(f"{pdf.name}: {len(cands)}/{len(doc)} 후보 페이지 중 {len(picked)}쪽 샘플 → 원본 쪽번호 {pdf.stem}.pages.txt")


def cmd_crop(spec: str, pad: int):
    (REAL / "images").mkdir(parents=True, exist_ok=True)
    for c in json.loads(Path(spec).read_text()):
        img = Image.open(REAL / "pages" / c["page"]).convert("RGB")
        x0, y0, x1, y1 = c["bbox"]
        img.crop((max(0, x0 - pad), max(0, y0 - pad), min(img.width, x1 + pad), min(img.height, y1 + pad))) \
           .save(REAL / "images" / f"{c['id']}.png")
        print("crop", c["id"])


def cmd_detect(scale: float, pad: int):
    """Docling으로 PDF의 표 위치를 찾아 잘라낸다. 정답 HTML은 만들지 않는다(그건 draft)."""
    import pypdfium2 as pdfium
    from docling.document_converter import DocumentConverter
    (REAL / "images").mkdir(parents=True, exist_ok=True)
    conv = DocumentConverter()
    for pdf in sorted((REAL / "pdfs").glob("*.pdf")):
        doc = conv.convert(str(pdf)).document
        pdf_doc = pdfium.PdfDocument(str(pdf))
        for ti, table in enumerate(doc.tables):
            if not table.prov:
                continue
            prov = table.prov[0]
            page = doc.pages[prov.page_no]
            bbox = prov.bbox.to_top_left_origin(page_height=page.size.height)
            img = pdf_doc[prov.page_no - 1].render(scale=scale).to_pil().convert("RGB")
            box = [int(v * scale) for v in (bbox.l, bbox.t, bbox.r, bbox.b)]
            crop = img.crop((max(0, box[0] - pad), max(0, box[1] - pad),
                             min(img.width, box[2] + pad), min(img.height, box[3] + pad)))
            sid = f"{pdf.stem}_p{prov.page_no:03d}_t{ti + 1}"
            crop.save(REAL / "images" / f"{sid}.png")
            # 정답 초안: PDF 텍스트 레이어 기반 Docling 결과 (글자는 원문 그대로, 구조는 검수 필요)
            lab = REAL / "labels" / f"{sid}.html"
            lab.parent.mkdir(parents=True, exist_ok=True)
            if not lab.exists():
                norm = normalize_html(table.export_to_html(doc=doc)) or "<table><tr><td></td></tr></table>"
                lab.write_text(f"{DRAFT_MARK}\n<!-- source: docling-pdf-textlayer -->\n"
                               + norm.replace("<tr>", "\n<tr>").replace("</table>", "\n</table>") + "\n")
            print("table", sid, crop.size)


def cmd_draft(base_url: str, model: str, overwrite: bool):
    from .predict import ApiBackend
    (REAL / "labels").mkdir(parents=True, exist_ok=True)
    be = ApiBackend(base_url, model, "html", 4096, 900)
    from .table import extract_table_html
    for img in sorted((REAL / "images").glob("*.png")):
        out = REAL / "labels" / f"{img.stem}.html"
        if out.exists() and not overwrite:
            continue
        res = be(str(img))
        norm = normalize_html(extract_table_html(res["output"]) or "") or "<table><tr><td></td></tr></table>"
        pretty = norm.replace("<tr>", "\n<tr>").replace("</table>", "\n</table>")
        out.write_text(f"{DRAFT_MARK}\n{pretty}\n")
        print("draft", out.name)


def cmd_build():
    rows, skipped = [], []
    for lab in sorted((REAL / "labels").glob("*.html")):
        text = lab.read_text()
        if text.lstrip().startswith(DRAFT_MARK):
            skipped.append(lab.stem)
            continue
        norm = normalize_html(text)
        t = parse_table(norm or "")
        if not t or not to_grid(t)[3]:
            print(f"경고: {lab.name} 격자 불일치(행·열 수가 안 맞음) → 제외, 수정 필요")
            continue
        cells, n_rows, n_cols, _ = to_grid(t)
        img = REAL / "images" / f"{lab.stem}.png"
        w, h = Image.open(img).size
        rows.append({"id": lab.stem, "image": f"images/{img.name}", "html": norm,
                     "meta": {"rows": n_rows, "cols": n_cols, "n_spans": sum(c.rowspan > 1 or c.colspan > 1 for c in cells),
                              "tags": ["real"] + (["merged"] if any(c.rowspan > 1 or c.colspan > 1 for c in cells) else []),
                              "width": w, "height": h}})
    with open(REAL / "manifest.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"manifest: {len(rows)}개 (아직 DRAFT {len(skipped)}개)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("subset"); p.add_argument("--n-pages", type=int, default=25); p.add_argument("--seed", type=int, default=0)
    p.add_argument("--pattern", default="(단위")
    p = sub.add_parser("pages"); p.add_argument("--scale", type=float, default=2.0)
    p = sub.add_parser("crop"); p.add_argument("spec"); p.add_argument("--pad", type=int, default=8)
    p = sub.add_parser("detect"); p.add_argument("--scale", type=float, default=2.0); p.add_argument("--pad", type=int, default=8)
    p = sub.add_parser("draft")
    p.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    p.add_argument("--model", default="models/Qwen3.8-27B-4bit")
    p.add_argument("--overwrite", action="store_true")
    sub.add_parser("build")
    a = ap.parse_args()
    if a.cmd == "subset":
        cmd_subset(a.n_pages, a.seed, a.pattern)
    elif a.cmd == "pages":
        cmd_pages(a.scale)
    elif a.cmd == "crop":
        cmd_crop(a.spec, a.pad)
    elif a.cmd == "detect":
        cmd_detect(a.scale, a.pad)
    elif a.cmd == "draft":
        cmd_draft(a.base_url, a.model, a.overwrite)
    else:
        cmd_build()


if __name__ == "__main__":
    main()
