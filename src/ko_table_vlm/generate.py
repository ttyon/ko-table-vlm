"""합성 한국어 표 데이터 생성기: 무작위 구조·내용·스타일 → HTML 렌더링 → PNG + 정답 HTML.

    uv run python -m ko_table_vlm.generate --split train --n 3000 --seed 1
    uv run python -m ko_table_vlm.generate --split ood --n 300 --seed 9   # 학습에 없는 스타일

출력: data/generated/<split>/manifest.jsonl, data/generated/<split>/images/*.png
manifest 한 줄: {"id", "image"(manifest 기준 상대경로), "html"(정규화 정답), "meta"{...}}
"""
from __future__ import annotations

import argparse
import html as html_lib
import io
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter

from . import content as C
from .styles import Style, css, sample_style
from .table import Cell, Table, to_grid

ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = ROOT / "fonts"
KINDS = ["int", "int", "money", "pct", "delta", "date", "text"]


@dataclass
class Placed:
    r: int
    c: int
    rs: int
    cs: int
    text: str
    role: str   # header | stub | data | total
    kind: str = "text"


def make_structure(rng: random.Random, max_rows: int = 16, max_cols: int = 9, template_p: float = 0.0):
    """격자 위에 셀을 배치한다. 반환: (Placed 목록, 헤더 행 수, stub 열 수).
    모든 행에 그 행에서 시작하는 셀이 최소 1개 있어야 HTML로 표현 가능 → 아니면 다시 생성."""
    while True:
        if template_p and rng.random() < template_p:
            placed, h, s = _template_structure(rng, max_rows)
        else:
            placed, h, s = _make_structure(rng, max_rows, max_cols)
        n_rows = max(p.r + p.rs for p in placed)
        if {p.r for p in placed} == set(range(n_rows)):
            return placed, h, s


def _make_structure(rng: random.Random, max_rows: int, max_cols: int):
    h = rng.choices([1, 2, 3], weights=[0.45, 0.4, 0.15])[0]
    s = rng.choices([1, 2], weights=[0.75, 0.25])[0]
    n_data = rng.randint(2, max_cols - s)
    C_ = s + n_data
    placed: list[Placed] = []
    col_kind: dict[int, str] = {}

    # --- 헤더 ---
    stub_names = rng.sample(C.STUB_HEADERS, s)
    for j in range(s):
        placed.append(Placed(0, j, h, 1, stub_names[j], "header"))

    def part(level: int, c0: int, c1: int):
        if level == h - 1:
            for c in range(c0, c1):
                k = rng.choice(KINDS)
                col_kind[c] = k
                placed.append(Placed(level, c, 1, 1, C.leaf_header(rng, k), "header"))
            return
        c = c0
        while c < c1:
            size = min(c1 - c, rng.choices([1, 2, 3, 4], weights=[0.3, 0.4, 0.2, 0.1])[0])
            if size == 1:
                k = rng.choice(KINDS)
                col_kind[c] = k
                placed.append(Placed(level, c, h - level, 1, C.leaf_header(rng, k), "header"))
            else:
                placed.append(Placed(level, c, 1, size, C.group_header(rng, level), "header"))
                part(level + 1, c, c + size)
            c += size

    part(0, s, C_)

    # --- 본문 ---
    n_body = rng.randint(2, max_rows - h)
    has_total = rng.random() < 0.4
    total_at_top = has_total and rng.random() < 0.3
    body_start = h + (1 if total_at_top else 0)
    body_end = body_start + n_body  # exclusive
    occ: set[tuple[int, int]] = set()
    for p in placed:
        for dr in range(p.rs):
            for dc in range(p.cs):
                occ.add((p.r + dr, p.c + dc))

    def put(p: Placed):
        placed.append(p)
        for dr in range(p.rs):
            for dc in range(p.cs):
                occ.add((p.r + dr, p.c + dc))

    if has_total:
        tr = h if total_at_top else body_end
        put(Placed(tr, 0, 1, s, rng.choice(["합계", "총계", "계", "소계"]), "total"))

    # stub 열: 첫 열은 그룹(rowspan) 가능
    stub_kind = rng.choice(["region", "dept", "project", "item", "year"])
    grouped = s == 2 or rng.random() < 0.35
    r = body_start
    groups = rng.choice(C.STUB_GROUPS)
    gi = 0
    while r < body_end:
        if grouped:
            size = min(body_end - r, rng.randint(1, 4))
            label = groups[gi % len(groups)] if s == 2 or rng.random() < 0.5 else C.stub_text(rng, stub_kind)
            gi += 1
            put(Placed(r, 0, size, 1, label, "stub"))
            if s == 2:
                for rr in range(r, r + size):
                    put(Placed(rr, 1, 1, 1, C.stub_text(rng, stub_kind), "stub"))
            r += size
        else:
            put(Placed(r, 0, 1, 1, C.stub_text(rng, stub_kind), "stub"))
            r += 1

    # 데이터 셀: 가끔 병합(같은 값·'해당 없음' 등)
    merge_on = rng.random() < 0.35
    data_rows = list(range(body_start, body_end)) + ([h if total_at_top else body_end] if has_total else [])
    for rr in data_rows:
        for c in range(s, C_):
            if (rr, c) in occ:
                continue
            kind = col_kind.get(c, "int")
            rs = cs = 1
            if merge_on and rr < body_end and rng.random() < 0.08:
                cs = rng.choice([1, 2, 2, 3])
                rs = rng.choice([1, 1, 2])
                while cs > 1 and any((rr, c + k) in occ or c + k >= C_ for k in range(cs)):
                    cs -= 1
                while rs > 1 and any((rr + k, cc) in occ or rr + k >= body_end
                                     for k in range(rs) for cc in range(c, c + cs)):
                    rs -= 1
            text = C.value(rng, kind)
            if (rs > 1 or cs > 1) and rng.random() < 0.5:
                text = rng.choice(["해당 없음", "-", "미집계", "공통", "전체 적용"])
            put(Placed(rr, c, rs, cs, text, "total" if rr not in range(body_start, body_end) else "data", kind))

    return placed, h, s


# ---------------- 데이터 보강(009): 실제 공문서 헤더 템플릿 ----------------
def _template_structure(rng: random.Random, max_rows: int):
    """실제 예산·결산 표에서 반복되는 헤더 패턴 3종 + 긴 세로 병합 + 의미가 일관된 열."""
    kind = rng.choice(["yearly_pair", "settlement", "review"])
    placed: list[Placed] = []
    occ: set[tuple[int, int]] = set()

    def put(p: Placed):
        placed.append(p)
        for dr in range(p.rs):
            for dc in range(p.cs):
                occ.add((p.r + dr, p.c + dc))

    if kind == "yearly_pair":      # 연도별 [예산|수납] 반복
        h, s = 2, rng.choice([1, 2])
        put(Placed(0, 0, 2, s, "구분", "header"))
        years = rng.randint(3, 5)
        y0 = rng.randint(2018, 2022)
        sub = rng.choice([("예산", "수납"), ("계획", "실적"), ("예산", "결산"), ("목표", "실적")])
        c = s
        cols = []
        for i in range(years):
            put(Placed(0, c, 1, 2, str(y0 + i), "header"))
            put(Placed(1, c, 1, 1, sub[0], "header")); put(Placed(1, c + 1, 1, 1, sub[1], "header"))
            cols += ["money", "money"]; c += 2
        for i in range(rng.randint(0, 2)):   # 마지막 연도들은 예산만
            put(Placed(0, c, 1, 1, str(y0 + years + i), "header")); put(Placed(1, c, 1, 1, sub[0], "header"))
            cols.append("money"); c += 1
    elif kind == "settlement":     # 결산 / 예산(A) / 예산(B) / 증감(B-A, (B-A)/A)
        h = 2
        pair = rng.choice(C.STUB_HEADER_PAIRS + [("구분", None)] * 3)
        s = 1 if pair[1] is None else 2
        put(Placed(0, 0, 2, 1, pair[0], "header"))
        if s == 2:
            put(Placed(0, 1, 2, 1, pair[1], "header"))
        y = rng.randint(2021, 2025)
        w = rng.choice(["예산", "계획"])
        labels = [f"{y}\n결산", f"{y + 1}\n{w}(A)", f"{y + 2}\n{w}(B)"]
        for i, t in enumerate(labels):
            put(Placed(0, s + i, 2, 1, t, "header"))
        put(Placed(0, s + 3, 1, 2, rng.choice(["증감", "증 감"]), "header"))
        put(Placed(1, s + 3, 1, 1, "B-A", "header")); put(Placed(1, s + 4, 1, 1, "(B-A)/A", "header"))
        cols = ["money", "money", "money", "delta", "pctd"]
    else:                          # 국회 심의결과 3단 헤더
        h, s = 3, 2
        a, b = rng.choice(C.STUB_HEADER_PAIRS[:4])
        put(Placed(0, 0, 3, 1, a, "header")); put(Placed(0, 1, 3, 1, b, "header"))
        y = rng.randint(2024, 2027)
        put(Placed(0, 2, 3, 1, f"{y}\n예산안", "header"))
        put(Placed(0, 3, 1, 5, "국회 심의결과", "header"))
        put(Placed(1, 3, 1, 2, "상임위 예비심사", "header")); put(Placed(1, 5, 1, 3, "본회의 수정", "header"))
        for i, t in enumerate(["증액", "감액", "증액", "감액", "증감"]):
            put(Placed(2, 3 + i, 1, 1, t, "header"))
        put(Placed(0, 8, 3, 1, f"{y}\n확정예산", "header"))
        cols = ["money", "plus", "minus", "plus", "minus", "delta", "money"]
        if rng.random() < 0.35:
            put(Placed(0, 9, 3, 1, "감액 사유", "header")); cols.append("reason")

    n_cols = s + len(cols)
    n_body = rng.randint(2, max(2, max_rows - h))
    has_total = rng.random() < 0.4
    body_start, body_end = h, h + n_body
    # stub: s==2 이면 첫 열을 긴 그룹(최대 본문 전체)으로
    r = body_start
    while r < body_end:
        if s == 2:
            size = body_end - r if rng.random() < 0.4 else min(body_end - r, rng.randint(1, 6))
            put(Placed(r, 0, size, 1, rng.choice(C.ACCOUNTS), "stub"))
            for rr in range(r, r + size):
                put(Placed(rr, 1, 1, 1, C.budget_item(rng), "stub"))
            r += size
        else:
            put(Placed(r, 0, 1, 1, rng.choice(C.ACCOUNTS + [C.budget_item(rng)]).replace("\n", " "), "stub"))
            r += 1
    if has_total:
        put(Placed(body_end, 0, 1, s, rng.choice(["합계", "합 계", "총계"]), "total"))
    rows = list(range(body_start, body_end)) + ([body_end] if has_total else [])
    for rr in rows:
        for j, kind_ in enumerate(cols):
            c = s + j
            if (rr, c) in occ:
                continue
            put(Placed(rr, c, 1, 1, _typed_value(rng, kind_), "data" if rr < body_end else "total",
                       "text" if kind_ == "reason" else "int"))
    return placed, h, s


def _typed_value(rng: random.Random, kind: str) -> str:
    if kind == "plus":
        return "-" if rng.random() < 0.55 else f"{rng.randint(1, 99_999):,}"
    if kind == "minus":
        return "-" if rng.random() < 0.55 else f"△{rng.randint(1, 99_999):,}"
    if kind == "pctd":
        v = rng.uniform(-80, 150)
        return "-" if rng.random() < 0.08 else (f"△{abs(v):.1f}" if v < 0 else f"{v:.1f}")
    if kind == "reason":
        return C.reason(rng)
    return C.value(rng, kind)


def to_table(placed: list[Placed]) -> Table:
    rows: dict[int, list[Placed]] = {}
    for p in placed:
        rows.setdefault(p.r, []).append(p)
    t = Table()
    for r in sorted(rows):
        t.rows.append([Cell(p.text, p.rs, p.cs, p.role == "header") for p in sorted(rows[r], key=lambda x: x.c)])
    return t


def render_html(placed: list[Placed]) -> str:
    rows: dict[int, list[Placed]] = {}
    for p in placed:
        rows.setdefault(p.r, []).append(p)
    out = ["<table>"]
    for i, r in enumerate(sorted(rows)):
        cls_tr = ' class="z"' if i % 2 == 0 else ""
        out.append(f"<tr{cls_tr}>")
        for p in sorted(rows[r], key=lambda x: x.c):
            cls = "h" if p.role == "header" else ("t" if p.kind == "text" or p.role in ("stub", "total") else "n")
            if p.role == "total":
                cls += " h"
            attrs = (f' rowspan="{p.rs}"' if p.rs > 1 else "") + (f' colspan="{p.cs}"' if p.cs > 1 else "")
            txt = "<br>".join(html_lib.escape(x) for x in p.text.split("\n"))
            out.append(f'<td class="{cls}"{attrs}>{txt}</td>')
        out.append("</tr>")
    out.append("</table>")
    return "".join(out)


def base_page() -> str:
    faces = "".join(
        f"@font-face {{ font-family:'{f.stem}'; src:url('{f.as_uri()}'); }}\n" for f in sorted(FONT_DIR.glob("*.ttf")))
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{faces} body{{margin:0;background:#fff}}</style>" \
           f"<style id='st'></style></head><body><div id='wrap'></div></body></html>"


def degrade(img: Image.Image, rng: random.Random) -> tuple[Image.Image, list[str]]:
    ops = []
    img = img.convert("RGB")
    if rng.random() < 0.3:
        f = rng.uniform(0.6, 0.9)
        w, h = img.size
        img = img.resize((max(1, int(w * f)), max(1, int(h * f))), Image.BILINEAR).resize((w, h), Image.BILINEAR)
        ops.append("rescale")
    if rng.random() < 0.3:
        img = img.rotate(rng.uniform(-0.8, 0.8), resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))
        ops.append("rotate")
    if rng.random() < 0.3:
        img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 0.8)))
        ops.append("blur")
    if rng.random() < 0.2:
        img = img.convert("L").convert("RGB")
        ops.append("gray")
    if rng.random() < 0.5:
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=rng.randint(40, 90))
        img = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
        ops.append("jpeg")
    return img, ops


def fit(img: Image.Image, max_side: int) -> Image.Image:
    w, h = img.size
    if max(w, h) <= max_side:
        return img
    f = max_side / max(w, h)
    return img.resize((int(w * f), int(h * f)), Image.LANCZOS)


def tags_for(t: Table, header_rows: int, st: Style) -> list[str]:
    cells, *_ = to_grid(t)
    tags = []
    if header_rows >= 2:
        tags.append("multi_header")
    if any(c.rowspan > 1 or c.colspan > 1 for c in cells if c.r >= header_rows):
        tags.append("merged_body")
    if st.border in ("horizontal", "none_shaded", "outer_header"):
        tags.append("borderless")
    if not tags:
        tags.append("simple")
    return tags


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", required=True, help="train | val | test | ood (ood만 별도 스타일 사용)")
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", default=str(ROOT / "data" / "generated"))
    ap.add_argument("--max-side", type=int, default=1280, help="이미지 긴 변 최대 픽셀 (VLM 토큰 수 제어)")
    ap.add_argument("--degrade-p", type=float, default=0.5, help="스캔 열화 적용 확률")
    ap.add_argument("--max-rows", type=int, default=16)
    ap.add_argument("--max-cols", type=int, default=9)
    ap.add_argument("--aug", action="store_true", help="데이터 보강(009): 실제 공문서 헤더 템플릿·스타일 추가")
    ap.add_argument("--template-p", type=float, default=0.5, help="--aug 일 때 템플릿 구조 비율")
    args = ap.parse_args()

    if not any(FONT_DIR.glob("*.ttf")):
        raise SystemExit("fonts/ 가 비어 있음 → ./scripts/download_fonts.sh 먼저 실행")
    from playwright.sync_api import sync_playwright

    out = Path(args.out) / args.split
    (out / "images").mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    t0 = time.time()
    with sync_playwright() as pw, open(out / "manifest.jsonl", "w") as mf:
        browser = pw.chromium.launch()
        pages = {}
        for i in range(args.n):
            st = sample_style(rng, args.split, aug=args.aug)
            if st.scale not in pages:
                ctx = browser.new_context(viewport={"width": 2000, "height": 1400}, device_scale_factor=st.scale)
                pg = ctx.new_page()
                base = out / "_base.html"
                base.write_text(base_page())
                pg.goto(base.as_uri())
                pages[st.scale] = pg
            pg = pages[st.scale]
            placed, h, s = make_structure(rng, args.max_rows, args.max_cols, args.template_p if args.aug else 0.0)
            table = to_table(placed)
            pg.evaluate("""([css, html, pad]) => {
                document.getElementById('st').textContent = css;
                const w = document.getElementById('wrap');
                w.style.setProperty('--pad', pad + 'px');
                w.innerHTML = html;
                return document.fonts.ready.then(() => true);
            }""", [css(st), render_html(placed), rng.randint(4, 24)])
            png = pg.locator("#wrap").screenshot()
            img = fit(Image.open(io.BytesIO(png)).convert("RGB"), args.max_side)
            ops = []
            if rng.random() < args.degrade_p:
                img, ops = degrade(img, rng)
            sid = f"{args.split}_{i:06d}"
            img.save(out / "images" / f"{sid}.png")
            cells, n_rows, n_cols, ok = to_grid(table)
            assert ok, f"생성 버그: 격자 불일치 {sid}"
            meta = {"aug": args.aug, "rows": n_rows, "cols": n_cols, "header_rows": h, "stub_cols": s,
                    "n_spans": sum(c.rowspan > 1 or c.colspan > 1 for c in cells),
                    "tags": tags_for(table, h, st), "style": st.to_dict(), "degrade": ops,
                    "width": img.size[0], "height": img.size[1]}
            mf.write(json.dumps({"id": sid, "image": f"images/{sid}.png", "html": table.to_html(),
                                 "meta": meta}, ensure_ascii=False) + "\n")
            if (i + 1) % 100 == 0 or i + 1 == args.n:
                print(f"[{args.split}] {i + 1}/{args.n}  {time.time() - t0:.0f}s", flush=True)
        browser.close()
    (out / "_base.html").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
