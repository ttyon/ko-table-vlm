"""표 인식 지표.

TEDS (Tree-Edit-Distance-based Similarity, Zhong et al. 2020, PubTabNet):
  TEDS = 1 - TreeEditDistance(pred, gt) / max(노드 수(pred), 노드 수(gt))
  - 노드: table → tr → td
  - td 노드 rename 비용: 태그/rowspan/colspan이 다르면 1, 같으면 셀 텍스트의 정규화 편집거리
  - TEDS-S: 셀 텍스트를 무시하고 구조만 비교
주의: 이 구현은 thead/tbody를 구분하지 않으므로 논문에 보고된 PubTabNet 수치와 직접 비교하지 않는다.
      같은 구현으로 측정한 시스템끼리만 비교한다.
"""
from __future__ import annotations

from dataclasses import dataclass

from apted import APTED, Config
from rapidfuzz.distance import Levenshtein

from .table import Table, extract_table_html, parse_table, to_grid


class _Node:
    __slots__ = ("tag", "rowspan", "colspan", "text", "children")

    def __init__(self, tag, rowspan=1, colspan=1, text="", children=None):
        self.tag, self.rowspan, self.colspan, self.text = tag, rowspan, colspan, text
        self.children = children or []


def _tree(t: Table, structure_only: bool) -> _Node:
    rows = []
    for row in t.rows:
        tds = [_Node("td", c.rowspan, c.colspan, "" if structure_only else c.text) for c in row]
        rows.append(_Node("tr", children=tds))
    return _Node("table", children=rows)


def _count(n: _Node) -> int:
    return 1 + sum(_count(c) for c in n.children)


class _TedsConfig(Config):
    def rename(self, a: _Node, b: _Node) -> float:
        if a.tag != b.tag or a.rowspan != b.rowspan or a.colspan != b.colspan:
            return 1.0
        if a.tag == "td" and (a.text or b.text):
            return Levenshtein.normalized_distance(a.text, b.text)
        return 0.0

    def children(self, node: _Node):
        return node.children


def teds(pred: Table | None, gt: Table, structure_only: bool = False) -> float:
    if pred is None:
        return 0.0
    tp, tg = _tree(pred, structure_only), _tree(gt, structure_only)
    dist = APTED(tp, tg, _TedsConfig()).compute_edit_distance()
    return max(0.0, 1.0 - dist / max(_count(tp), _count(tg)))


def cell_cer(pred: Table | None, gt: Table) -> float:
    """같은 격자 원점 위치의 셀끼리 텍스트 문자 오류율. 예측에 없는 셀은 전부 오류."""
    g_cells, *_ = to_grid(gt)
    total = sum(len(c.text) for c in g_cells)
    if total == 0:
        return 0.0
    p_map = {}
    if pred is not None:
        p_cells, *_ = to_grid(pred)
        p_map = {(c.r, c.c): c.text for c in p_cells}
    err = sum(Levenshtein.distance(p_map.get((c.r, c.c), ""), c.text) for c in g_cells)
    return min(1.0, err / total)


def merged_cell_recall(pred: Table | None, gt: Table) -> float | None:
    """정답의 병합 셀(rowspan/colspan>1) 중 같은 위치·같은 span으로 예측된 비율. 병합 셀이 없으면 None."""
    g_cells, *_ = to_grid(gt)
    spans = [(c.r, c.c, c.rowspan, c.colspan) for c in g_cells if c.rowspan > 1 or c.colspan > 1]
    if not spans:
        return None
    if pred is None:
        return 0.0
    p_cells, *_ = to_grid(pred)
    p_set = {(c.r, c.c, c.rowspan, c.colspan) for c in p_cells}
    return sum(s in p_set for s in spans) / len(spans)


@dataclass
class Score:
    valid: bool          # <table>을 꺼내 파싱할 수 있었나
    grid_ok: bool        # 격자가 일관적인가(겹침·구멍 없음)
    teds: float
    teds_s: float
    cer: float
    merged_recall: float | None


def _strip_spaces(t: Table | None) -> Table | None:
    if t is not None:
        for row in t.rows:
            for c in row:
                c.text = c.text.replace(" ", "")
    return t


def score_prediction(pred_text: str | None, gt_html: str, pred_table: Table | None = None,
                     ignore_space: bool = False) -> Score:
    """pred_text(모델 원문 출력) 또는 이미 파싱된 pred_table 을 정답 HTML과 비교.
    ignore_space: 셀 텍스트의 공백을 모두 무시 (한국어 자간·띄어쓰기 모호성에 대한 민감도 분석용)."""
    gt = parse_table(gt_html)
    assert gt is not None, "정답 HTML 파싱 실패"
    if pred_table is None and pred_text is not None:
        pred_table = parse_table(extract_table_html(pred_text) or "")
    if ignore_space:
        gt, pred_table = _strip_spaces(gt), _strip_spaces(pred_table)
    grid_ok = bool(pred_table) and to_grid(pred_table)[3]
    return Score(
        valid=pred_table is not None,
        grid_ok=grid_ok,
        teds=teds(pred_table, gt),
        teds_s=teds(pred_table, gt, structure_only=True),
        cer=cell_cer(pred_table, gt),
        merged_recall=merged_cell_recall(pred_table, gt),
    )
