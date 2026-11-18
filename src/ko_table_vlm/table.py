"""표 구조 표현과 HTML 정규화.

모든 모듈(생성기, 학습 데이터 변환, 평가)이 이 파일의 정규화 규칙을 공유한다.
정규화된 정답 HTML 규칙:
  - 태그는 <table>, <tr>, <td> 만 (th → td, thead/tbody 제거)
  - 속성은 rowspan, colspan 만, 값이 2 이상일 때만 표기
  - 셀 텍스트는 줄바꿈·연속 공백을 공백 하나로, 앞뒤 공백 제거
"""
from __future__ import annotations

import html as html_lib
import re
import unicodedata
from dataclasses import dataclass, field

from lxml import html as lxml_html


@dataclass
class Cell:
    text: str = ""
    rowspan: int = 1
    colspan: int = 1
    header: bool = False  # 렌더링 스타일용 (정규화 HTML에는 반영하지 않음)


@dataclass
class Table:
    rows: list[list[Cell]] = field(default_factory=list)

    def to_html(self) -> str:
        """정규화된 정답 HTML."""
        out = ["<table>"]
        for row in self.rows:
            out.append("<tr>")
            for c in row:
                attrs = ""
                if c.rowspan > 1:
                    attrs += f' rowspan="{c.rowspan}"'
                if c.colspan > 1:
                    attrs += f' colspan="{c.colspan}"'
                out.append(f"<td{attrs}>{html_lib.escape(clean_text(c.text), quote=False)}</td>")
            out.append("</tr>")
        out.append("</table>")
        return "".join(out)


_WS = re.compile(r"\s+")


_SAME_LOOKING = str.maketrans({"・": "·", "‧": "·", "∙": "·", "•": "·", "ㆍ": "·", "ᆞ": "·"})  # 가운뎃점 변형들 (평가 v3)


def clean_text(s: str) -> str:
    # NFKC: 눈으로 구분이 안 되는 문자(전각 '－'↔'-', '…'↔'...', 전각 숫자 등)를 같은 것으로 취급 (평가 v2, 2026-11-18)
    # v3: NFKC가 합치지 않는 가운뎃점 변형(・ U+30FB 등)도 '·'로 통일
    return _WS.sub(" ", unicodedata.normalize("NFKC", s).translate(_SAME_LOOKING)).strip()


_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
_TABLE = re.compile(r"<table\b.*?</table\s*>", re.S | re.I)


def extract_table_html(text: str) -> str | None:
    """모델 출력에서 첫 번째 <table>...</table> 을 꺼낸다 (코드펜스·설명·think 블록 무시).
    닫는 태그가 없으면(토큰 한도로 잘림) 끝까지 잘라 붙여서 최대한 살린다."""
    if not text:
        return None
    text = _THINK.sub("", text)
    m = _TABLE.search(text)
    if m:
        return m.group(0)
    start = text.lower().find("<table")
    if start == -1:
        return None
    return text[start:] + "</table>"


def _span(v) -> int:
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        return 1
    return n if 1 <= n <= 1000 else 1


def parse_table(table_html: str) -> Table | None:
    """HTML 문자열 → Table. 파싱 불가하면 None."""
    if not table_html:
        return None
    try:
        root = lxml_html.fragment_fromstring(table_html, create_parent="div")
    except Exception:
        return None
    tables = root.xpath(".//table")
    if not tables:
        return None
    t = Table()
    for tr in tables[0].xpath(".//tr"):
        # 중첩 표의 tr 은 무시
        if tr.xpath("ancestor::table[1]")[0] is not tables[0]:
            continue
        row = []
        for td in tr.xpath("./td|./th"):
            for br in td.xpath(".//br"):
                br.tail = " " + (br.tail or "")
            row.append(Cell(text=clean_text(td.text_content()),
                            rowspan=_span(td.get("rowspan", 1)),
                            colspan=_span(td.get("colspan", 1)),
                            header=td.tag == "th"))
        if row:
            t.rows.append(row)
    return t if t.rows else None


def normalize_html(table_html: str) -> str | None:
    t = parse_table(table_html)
    return t.to_html() if t else None


@dataclass
class GridCell:
    r: int
    c: int
    rowspan: int
    colspan: int
    text: str


def to_grid(t: Table) -> tuple[list[GridCell], int, int, bool]:
    """셀을 (행, 열) 격자에 배치한다. 반환: (셀 목록(원점 좌표 포함), 행 수, 열 수, 격자 일관성 여부).
    일관성 = 모든 격자 칸이 정확히 한 셀로 덮이고 겹침이 없음."""
    occupied: dict[tuple[int, int], int] = {}
    cells: list[GridCell] = []
    consistent = True
    for r, row in enumerate(t.rows):
        c = 0
        for cell in row:
            while (r, c) in occupied:
                c += 1
            gc = GridCell(r, c, cell.rowspan, cell.colspan, clean_text(cell.text))
            idx = len(cells)
            cells.append(gc)
            for dr in range(cell.rowspan):
                for dc in range(cell.colspan):
                    key = (r + dr, c + dc)
                    if key in occupied:
                        consistent = False
                    occupied[key] = idx
            c += cell.colspan
    if not occupied:
        return cells, 0, 0, False
    n_rows = max(k[0] for k in occupied) + 1
    n_cols = max(k[1] for k in occupied) + 1
    if len(occupied) != n_rows * n_cols:
        consistent = False
    return cells, n_rows, n_cols, consistent
