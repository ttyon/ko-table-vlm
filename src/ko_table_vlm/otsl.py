"""OTSL(Optimized Table Structure Language) ↔ HTML 변환. 3주차 '출력 형식' 실험용.

OTSL은 표를 격자 칸 단위 토큰으로 표현한다 (Docling/TableFormer 계열에서 사용):
  <fcel>내용  : 내용이 있는 셀의 원점
  <ecel>      : 빈 셀의 원점
  <lcel>      : 왼쪽 셀과 병합(colspan으로 덮인 칸)
  <ucel>      : 위쪽 셀과 병합(rowspan으로 덮인 칸)
  <xcel>      : 왼쪽·위쪽 모두와 병합(rowspan과 colspan이 겹치는 칸)
  <nl>        : 행 끝
HTML보다 토큰이 짧아(태그·속성 반복 없음) 생성 속도가 빠를 수 있다.
"""
from __future__ import annotations

import re

from .table import Cell, Table, to_grid

_TOKEN = re.compile(r"<(fcel|ecel|lcel|ucel|xcel|nl)>")


def html_table_to_otsl(t: Table) -> str:
    cells, n_rows, n_cols, _ = to_grid(t)
    owner: dict[tuple[int, int], int] = {}
    for i, gc in enumerate(cells):
        for dr in range(gc.rowspan):
            for dc in range(gc.colspan):
                owner.setdefault((gc.r + dr, gc.c + dc), i)
    out = []
    for r in range(n_rows):
        for c in range(n_cols):
            i = owner.get((r, c))
            if i is None:
                out.append("<ecel>")
                continue
            gc = cells[i]
            if (gc.r, gc.c) == (r, c):
                out.append(f"<fcel>{gc.text}" if gc.text else "<ecel>")
            elif gc.r == r:
                out.append("<lcel>")
            elif gc.c == c:
                out.append("<ucel>")
            else:
                out.append("<xcel>")
        out.append("<nl>")
    return "".join(out)


def otsl_to_table(s: str) -> Table | None:
    """OTSL 문자열 → Table. 토큰이 하나도 없으면 None."""
    parts = _TOKEN.split(s)
    # split 결과: [앞부분, tok, text, tok, text, ...]
    grid: list[list[tuple[str, str]]] = [[]]
    for i in range(1, len(parts), 2):
        tok, text = parts[i], parts[i + 1] if i + 1 < len(parts) else ""
        if tok == "nl":
            grid.append([])
        else:
            grid[-1].append((tok, text.strip()))
    grid = [row for row in grid if row]
    if not grid:
        return None
    n_rows = len(grid)
    n_cols = max(len(r) for r in grid)
    tok_at = lambda r, c: grid[r][c][0] if c < len(grid[r]) else "ecel"  # noqa: E731
    t = Table()
    for r in range(n_rows):
        row = []
        for c in range(len(grid[r])):
            tok, text = grid[r][c]
            if tok not in ("fcel", "ecel"):
                continue  # 병합으로 덮인 칸
            colspan = 1
            while c + colspan < n_cols and tok_at(r, c + colspan) == "lcel":
                colspan += 1
            rowspan = 1
            while r + rowspan < n_rows and tok_at(r + rowspan, c) == "ucel":
                rowspan += 1
            row.append(Cell(text=text if tok == "fcel" else "", rowspan=rowspan, colspan=colspan))
        t.rows.append(row)
    return t
