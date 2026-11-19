"""표 렌더링 스타일. train 스타일과 ood(일반화 평가 전용) 스타일을 분리한다.

ood 세트는 학습에 쓰지 않은 폰트·테두리·색 조합으로만 만들어, '처음 보는 모양의 표'에 대한 일반화를 측정한다.
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass

FONTS = {
    "train": ["NotoSansKR", "NanumGothic", "NanumMyeongjo", "NotoSerifKR", "IBMPlexSansKR", "Apple SD Gothic Neo"],
    "ood": ["GowunBatang", "GowunDodum", "NanumGothicCoding"],
}
BORDERS = {
    "train": ["full", "full", "horizontal", "outer_header", "none_shaded"],
    "ood": ["dashed", "double_outer"],
}
HEADER_BG = {
    "train": ["none", "#f2f2f2", "#dde6f0", "#e8efe0", "#eeeeee"],
    "ood": ["#fbe4d5", "#3b4a5a"],
}
# 데이터 보강(009): 실제 공문서에서 관찰한 스타일 추가 — 진한 청록/파랑 헤더+흰 글씨, 점선 행 구분.
# ood 전용 스타일(주황, 진한 남색, 점선·이중선 테두리)과는 겹치지 않게 했다.
AUG_EXTRA = {
    "borders": ["dotted_rows", "dotted_rows"],
    "header_bg": ["#4fa59c", "#5b9bd5", "#6aaed6"],
}
DARK_HEADERS = {"#3b4a5a", "#4fa59c", "#5b9bd5", "#6aaed6"}


@dataclass
class Style:
    font: str
    font_size: int
    border: str
    header_bg: str
    header_bold: bool
    padding: int
    num_align: str
    zebra: bool
    text_max_width: int  # 텍스트 열 최대 폭(px) → 자연스러운 줄바꿈 유도, 0이면 제한 없음
    scale: float         # 렌더링 배율 (해상도 다양화)
    break_all: bool = False  # 좁은 텍스트 열에서 단어 중간 줄바꿈 (실제 문서 패턴)
    ls_em: float = 0.0       # v3: 자간 라벨(role ls)의 letter-spacing (em) — 정답은 붙여 씀

    def to_dict(self):
        return asdict(self)


V3_BORDERS = ["no_vertical", "no_vertical", "dotted_v", "horizontal", "full"]


def sample_style(rng: random.Random, split: str, aug: bool = False, v3: bool = False) -> Style:
    key = "ood" if split == "ood" else "train"
    if v3 and key == "train":
        return Style(
            font=rng.choice(FONTS["train"]), font_size=rng.randint(11, 16),
            border=rng.choice(V3_BORDERS), header_bg=rng.choice(HEADER_BG["train"] + AUG_EXTRA["header_bg"] + ["none", "none"]),
            header_bold=rng.random() < 0.4, padding=rng.randint(2, 7),
            num_align=rng.choice(["right", "right", "center"]), zebra=rng.random() < 0.1,
            text_max_width=rng.choice([0, 160, 220, 320]), scale=rng.choice([1.0, 1.25, 1.5]),
            break_all=rng.random() < 0.3, ls_em=rng.uniform(0.3, 1.2))
    if aug and key == "train":
        st = Style(
            font=rng.choice(FONTS["train"]), font_size=rng.randint(12, 17),
            border=rng.choice(BORDERS["train"] + AUG_EXTRA["borders"]),
            header_bg=rng.choice(HEADER_BG["train"] + AUG_EXTRA["header_bg"]),
            header_bold=rng.random() < 0.6, padding=rng.randint(3, 9),
            num_align=rng.choice(["right", "center", "right"]), zebra=rng.random() < 0.15,
            text_max_width=rng.choice([0, 110, 140, 180]), scale=rng.choice([1.0, 1.25, 1.5, 2.0]),
            break_all=rng.random() < 0.4)
        return st
    return Style(
        font=rng.choice(FONTS[key]),
        font_size=rng.randint(12, 17),
        border=rng.choice(BORDERS[key]),
        header_bg=rng.choice(HEADER_BG[key]),
        header_bold=rng.random() < 0.6,
        padding=rng.randint(3, 9),
        num_align=rng.choice(["right", "center", "right"]),
        zebra=rng.random() < 0.15,
        text_max_width=rng.choice([0, 0, 140, 180, 240]),
        scale=rng.choice([1.0, 1.25, 1.5, 2.0]),
    )


def css(st: Style) -> str:
    dark_header = st.header_bg in DARK_HEADERS
    bg = "transparent" if st.header_bg == "none" else st.header_bg
    base = f"""
    #wrap {{ display:inline-block; background:#fff; padding:var(--pad); }}
    table {{ border-collapse:collapse; font-family:'{st.font}', sans-serif; font-size:{st.font_size}px;
             color:#111; line-height:1.35; }}
    td {{ padding:{st.padding}px {st.padding + 3}px; vertical-align:middle; text-align:center; }}
    td.h {{ background:{bg}; {'font-weight:bold;' if st.header_bold else ''} {'color:#fff;' if dark_header else ''} }}
    td.n {{ text-align:{st.num_align}; }}
    td.t {{ text-align:left; {f'max-width:{st.text_max_width}px;' if st.text_max_width else ''} {'word-break:break-all;' if st.break_all else ''} }}
    {'tr.z td:not(.h) { background:#f7f7f7; }' if st.zebra else ''}
    td.ls {{ letter-spacing:{st.ls_em:.2f}em; text-align:center; }}
    td.ind {{ padding-left:{st.padding + 18}px; }}
    sup {{ font-size:0.65em; }}
    """
    b = {
        "full": "td { border:1px solid #444; }",
        "horizontal": "table { border-top:2px solid #222; border-bottom:2px solid #222; }"
                      " td { border-bottom:1px solid #bbb; } td.h { border-bottom:1px solid #222; }",
        "outer_header": "table { border:1.5px solid #222; } td.h { border-bottom:1.5px solid #222; }"
                        " td { border-right:1px solid #ccc; }",
        "none_shaded": "td { border:none; } td.h { border-bottom:1px solid #999; }",
        "dashed": "td { border:1px dashed #666; }",
        "double_outer": "table { border:3px double #222; } td { border:1px solid #888; }",
        "no_vertical": "table { border-top:2px solid #222; border-bottom:2px solid #222; }"
                       " td.h { border-bottom:1px solid #444; } td { border:none; }",
        "dotted_v": "table { border-top:2px solid #222; border-bottom:2px solid #222; }"
                    " td { border-left:1px dotted #999; } td.h { border-bottom:1px solid #444; }",
        "dotted_rows": "table { border-top:2px solid #333; border-bottom:2px solid #333; }"
                       " td { border-bottom:1px dotted #999; border-right:1px solid #ccc; } td.h { border-bottom:1px solid #666; }",
    }[st.border]
    return base + b
