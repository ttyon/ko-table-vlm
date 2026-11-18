import random

from ko_table_vlm.generate import make_structure, to_table
from ko_table_vlm.metrics import cell_cer, merged_cell_recall, score_prediction, teds
from ko_table_vlm.otsl import html_table_to_otsl, otsl_to_table
from ko_table_vlm.table import extract_table_html, normalize_html, parse_table, to_grid

GT = ('<table><tr><td rowspan="2">구분</td><td colspan="2">2025년</td></tr>'
      '<tr><td>상반기</td><td>하반기</td></tr><tr><td>예산(억원)</td><td>1,250</td><td>1,410</td></tr></table>')


def test_normalize_strips_tags_and_attrs():
    raw = ('```html\n<table border=1><thead><tr><th rowspan="2" style="x">구분</th><th colspan="2">2025년</th></tr>'
           '<tr><th>상반기</th><th>하반기</th></tr></thead><tbody><tr><td>예산<br>(억원)</td><td>1,250</td>'
           '<td colspan="1">1,410</td></tr></tbody></table>\n```')
    assert normalize_html(extract_table_html(raw)) == GT.replace("예산(억원)", "예산 (억원)")


def test_extract_handles_truncated_and_think():
    assert extract_table_html("<think>음...</think>결과: <table><tr><td>a</td></tr></table> 끝") == \
        "<table><tr><td>a</td></tr></table>"
    assert extract_table_html("<table><tr><td>a</td>").endswith("</table>")
    assert extract_table_html("표가 없습니다") is None


def test_grid():
    cells, r, c, ok = to_grid(parse_table(GT))
    assert (r, c, ok) == (3, 3, True)
    assert [(x.r, x.c) for x in cells] == [(0, 0), (0, 1), (1, 1), (1, 2), (2, 0), (2, 1), (2, 2)]


def test_teds_identity_and_degradation():
    gt = parse_table(GT)
    assert teds(gt, gt) == 1.0
    wrong_text = parse_table(GT.replace("1,410", "1,41O"))
    assert 0.9 < teds(wrong_text, gt) < 1.0
    assert teds(wrong_text, gt, structure_only=True) == 1.0
    no_merge = parse_table("<table><tr><td>구분</td><td>2025년</td><td></td></tr><tr><td></td><td>상반기</td>"
                           "<td>하반기</td></tr><tr><td>예산(억원)</td><td>1,250</td><td>1,410</td></tr></table>")
    assert teds(no_merge, gt, structure_only=True) < 1.0
    assert merged_cell_recall(no_merge, gt) == 0.0
    assert teds(None, gt) == 0.0


def test_cer():
    gt = parse_table(GT)
    assert cell_cer(gt, gt) == 0.0
    assert cell_cer(None, gt) == 1.0


def test_score_prediction_invalid():
    s = score_prediction("모르겠습니다", GT)
    assert not s.valid and s.teds == 0.0


def test_otsl_roundtrip_fixed():
    gt = parse_table(GT)
    otsl = html_table_to_otsl(gt)
    assert otsl == "<fcel>구분<fcel>2025년<lcel><nl><ucel><fcel>상반기<fcel>하반기<nl><fcel>예산(억원)<fcel>1,250<fcel>1,410<nl>"
    assert otsl_to_table(otsl).to_html() == gt.to_html()


def test_generated_tables_are_consistent_and_roundtrip():
    rng = random.Random(0)
    for _ in range(300):
        placed, h, s = make_structure(rng)
        t = to_table(placed)
        assert to_grid(t)[3], "격자 불일치"
        html = t.to_html()
        assert normalize_html(html) == html          # 정규화는 멱등
        back = otsl_to_table(html_table_to_otsl(parse_table(html)))
        assert teds(back, parse_table(html), structure_only=True) == 1.0


def test_nfkc_visual_equivalence():
    a = parse_table("<table><tr><td>－</td><td>…</td><td>１２３</td></tr></table>")
    b = parse_table("<table><tr><td>-</td><td>...</td><td>123</td></tr></table>")
    assert teds(a, b) == 1.0
