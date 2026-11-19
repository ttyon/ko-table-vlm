"""생성기 v3 (015 사전 등록 축): 기존 생성기(원본·보강)에 '구조·스타일 축'을 넓힌 표를 추가한다.

축 (015에서 고정):
  1. 표 길이 최대 40행          2. 세로선 없는 스타일(스타일 쪽, styles.py)
  3. 빈 왼쪽 위 칸               4. L자형 헤더 (라벨 규칙: 상위 rowspan 2 + 하위 열 위 빈칸 colspan + 하위 항목)
  5. 구역 제목 행 (값이 빈 행 / 전체 colspan 행)
  6. 목록·문장형 표 (긴 문장, 코드 ID, 글머리표 여러 줄)
  7. 자간 라벨 — 렌더링은 CSS letter-spacing, 정답은 붙여 씀 (role="ls")
  8. 분류 열 들여쓰기 — 같은 열 안의 하위 항목 (role="indent")
특정 기관 문서의 셀 값·제목은 쓰지 않는다 (일반 어휘만).
"""
from __future__ import annotations

import random

from . import content as C
from .generate import Placed

GROUPS_L = [("만족", ["매우", "약간"], "보통", "불만족", ["약간", "매우"]),
            ("증가", ["크게", "약간"], "동일", "감소", ["약간", "크게"]),
            ("찬성", ["적극", "다소"], "중립", "반대", ["다소", "적극"]),
            ("있음", ["자주", "가끔"], "모름", "없음", ["거의", "전혀"]),
            ("좋아짐", ["많이", "약간"], "변화없음", "나빠짐", ["약간", "많이"])]
CHOICE_HEADERS = ["경제적 부담", "시간 부족", "정보 부족", "건강 문제", "교통 불편", "시설 부족", "비용 부담", "관심 없음",
                  "절차 복잡", "거리가 멂", "필요 없음", "기타", "모르겠다", "직장 문제", "가족 돌봄", "서비스 부족"]
SEGMENTS = [
    ("지역", ["도시(동부)", "농어촌(읍면부)"]),
    ("성별", ["남자", "여자"]),
    ("연령", ["13~19세", "20~29세", "30~39세", "40~49세", "50~59세", "60세이상", "65세이상"]),
    ("학력", ["초졸이하", "중졸", "고졸", "대졸이상"]),
    ("직업", ["전문관리", "사무", "서비스판매", "농어업", "기능노무"]),
    ("소득", ["100만원 미만", "100~200만원 미만", "200~300만원 미만", "300~400만원 미만", "400~500만원 미만",
              "500~600만원 미만", "600만원 이상"]),
    ("가구", ["1인 가구", "2인 가구", "3인 가구", "4인 이상"]),
]
SECTION_TITLES = ["가구의 월평균소득", "가구주 특성", "지역별", "규모별", "업종별", "연령별 현황", "주요 지표"]
LIST_HEADERS = [("구분", "항목명", "코드", "비고"), ("분류", "세부 내용"), ("번호", "과제명", "주관 부서", "추진 일정"),
                ("목록명", "통계표명", "통계표ID", "비고"), ("영역", "주요 내용", "기대 효과")]
SENT_A = ["지역별", "성별", "연령별", "업종별", "규모별", "시도별", "유형별", "기관별"]
SENT_B = ["이용 실태", "근무 인력 현황", "평균 임금", "이직률", "참여 현황", "만족도 조사", "시설 현황", "지원 실적", "운영 성과"]
BULLETS = ["·", "-", "■", "○", "•"]
LIST_ITEMS = ["예산 편성 현황", "집행 실적 점검", "사업 성과 평가", "현장 의견 수렴", "제도 개선 과제", "관계기관 협의",
              "데이터 공개 확대", "모니터링 체계 구축", "교육 프로그램 운영", "안전 점검 강화", "정보 시스템 고도화"]


def _pct(rng):
    return f"{rng.uniform(0, 100):.1f}" if rng.random() > 0.03 else "-"


def _footnote(rng, s):
    return f"{s} {rng.randint(1, 3)})" if rng.random() < 0.08 else s


def long_stat(rng: random.Random, max_rows: int = 40):
    """통계 조사표형: 행 라벨(세그먼트) 20~40행, 백분율, L자형/평평한 헤더, 구역 제목 행, 자간 라벨."""
    placed: list[Placed] = []
    empty_corner = rng.random() < 0.6
    use_l = rng.random() < 0.5
    has_total_col = rng.random() < 0.7
    c = 1
    if use_l:
        g1, s1, mid, g2, s2 = rng.choice(GROUPS_L)
        h = 2
        placed.append(Placed(0, 0, 2, 1, "" if empty_corner else rng.choice(["구분", "특성별"]), "header"))
        if has_total_col:
            placed.append(Placed(0, c, 2, 1, _footnote(rng, "계"), "header")); c += 1
        placed.append(Placed(0, c, 2, 1, g1, "header")); placed.append(Placed(0, c + 1, 1, 2, "", "header"))
        placed.append(Placed(1, c + 1, 1, 1, s1[0], "header")); placed.append(Placed(1, c + 2, 1, 1, s1[1], "header")); c += 3
        placed.append(Placed(0, c, 2, 1, mid, "header")); c += 1
        placed.append(Placed(0, c, 2, 1, g2, "header")); placed.append(Placed(0, c + 1, 1, 2, "", "header"))
        placed.append(Placed(1, c + 1, 1, 1, s2[0], "header")); placed.append(Placed(1, c + 2, 1, 1, s2[1], "header")); c += 3
        if rng.random() < 0.4:
            placed.append(Placed(0, c, 2, 1, "모르겠다", "header")); c += 1
    else:
        h = 1
        placed.append(Placed(0, 0, 1, 1, "" if empty_corner else "구분", "header"))
        if has_total_col:
            placed.append(Placed(0, c, 1, 1, _footnote(rng, "계"), "header")); c += 1
        for t in rng.sample(CHOICE_HEADERS, rng.randint(4, 10)):
            placed.append(Placed(0, c, 1, 1, t, "header")); c += 1
    n_cols = c
    # 행: 연도 + 세그먼트 블록들 + (선택) 구역 제목 행
    r = h
    target = rng.randint(18, max_rows)
    def add_row(label, role="stub", empty=False):
        nonlocal r
        placed.append(Placed(r, 0, 1, 1, label, role))
        for cc in range(1, n_cols):
            placed.append(Placed(r, cc, 1, 1, "" if empty else ("100.0" if has_total_col and cc == 1 else _pct(rng)), "data", "int"))
        r += 1
    y = rng.randint(2015, 2024)
    year_fmt = rng.choice(["{}년", "<{}>", "{}"])
    for k in range(rng.choice([1, 2, 2, 3])):
        add_row(_footnote(rng, year_fmt.format(y + 2 * k)))
    segs = rng.sample(SEGMENTS, len(SEGMENTS))
    for name, labels in segs:
        if r - h >= target:
            break
        if rng.random() < 0.25:
            if rng.random() < 0.5:
                add_row(rng.choice(SECTION_TITLES), role="stub", empty=True)          # 값이 빈 구역 제목 행
            else:                                                                     # 전체 열을 덮는 구역 제목 행
                placed.append(Placed(r, 0, 1, n_cols, f"< {rng.choice(SECTION_TITLES)} >", "total")); r += 1
        for lab in labels:
            if r - h >= target:
                break
            role = "ls" if len(lab) <= 4 and rng.random() < 0.5 else ("indent" if rng.random() < 0.15 else "stub")
            add_row(lab, role=role)
    return placed, h, 1


def list_table(rng: random.Random, max_rows: int = 40):
    """목록·문장형: 열 2~4개, 긴 문장/코드/글머리표 여러 줄, 분류는 첫 행에만 쓰고 아래는 빈칸(또는 rowspan)."""
    heads = rng.choice(LIST_HEADERS)
    placed: list[Placed] = [Placed(0, j, 1, 1, t, "header") for j, t in enumerate(heads)]
    n_cols = len(heads)
    r = 1
    n = rng.randint(4, min(max_rows, 30))
    prefix = rng.choice(["DT_", "TB_", "ID-", "K"])
    code_base = rng.randint(100, 900)
    use_rowspan = rng.random() < 0.4
    groups = rng.sample(["의사", "간호사", "약사", "치과의사", "기술직", "행정직", "연구직", "운영지원"], 4)
    gi = 0
    while r - 1 < n:
        size = min(n - (r - 1), rng.randint(2, 8))
        for k in range(size):
            row = r + k
            if heads[0] in ("번호",):
                first = str(row)
            elif use_rowspan:
                if k == 0:
                    placed.append(Placed(row, 0, size, 1, groups[gi % 4], "stub"))
                first = None
            else:
                first = groups[gi % 4] if k == 0 else ""
            if first is not None:
                placed.append(Placed(row, 0, 1, 1, first, "stub"))
            for j in range(1, n_cols):
                h_ = heads[j]
                if "ID" in h_ or "코드" in h_:
                    v = f"{prefix}{code_base}_{chr(65 + gi % 26)}{row:03d}"
                elif h_ in ("비고",):
                    v = rng.choice(["신규", "변경", "", "유지"])
                elif h_ in ("추진 일정",):
                    v = rng.choice(["'25.상반기", "'25.하반기", "연중", "'26.3월"])
                elif h_ in ("세부 내용", "주요 내용", "기대 효과"):
                    b = rng.choice(BULLETS)
                    items = rng.sample(LIST_ITEMS, rng.randint(1, 4))
                    v = "\n".join(f"{b}{it}" for it in items)
                else:
                    v = f"{rng.choice(SENT_A)}, {rng.choice(SENT_A)} {rng.choice(SENT_B)}"
                    if rng.random() < 0.3:
                        v += f"({rng.choice(['일반', '전문', '공공', '민간'])})"
                placed.append(Placed(row, j, 1, 1, v, "data", "text"))
        r += size
        gi += 1
    if rng.random() < 0.3:
        placed.append(Placed(r, 0, 1, 1, "", "stub"))
        placed.append(Placed(r, 1, 1, n_cols - 1, f"합계 {rng.randint(50, 400)}건", "data", "text"))
    return placed, 1, 1


def v3_structure(rng: random.Random, max_rows: int = 40):
    return long_stat(rng, max_rows) if rng.random() < 0.6 else list_table(rng, max_rows)
