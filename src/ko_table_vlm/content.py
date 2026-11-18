"""한국어 행정·통계 문서 스타일의 셀 내용 생성기."""
from __future__ import annotations

import random

YEARS = [f"{y}년" for y in range(2018, 2027)]
QUARTERS = ["1분기", "2분기", "3분기", "4분기"]
HALVES = ["상반기", "하반기"]
GROUP_HEADERS = ["예산", "결산", "인원 현황", "사업비", "집행 실적", "지원 현황", "매출", "전년 대비",
                 "목표", "추진 실적", "국비", "지방비", "신청", "선정", "합계", "운영 현황"]
LEAF_HEADERS = {
    "int": ["인원(명)", "건수", "계획", "실적", "합계", "남", "여", "신규", "누적", "개소", "가구 수"],
    "money": ["금액(백만원)", "예산(억원)", "집행액", "지원액(천원)", "결산액", "편성액", "사업비(억원)"],
    "pct": ["비율(%)", "증감률(%)", "집행률(%)", "비중(%)", "달성률", "점유율(%)"],
    "delta": ["증감", "전년 대비", "증감(B-A)", "차이"],
    "date": ["시행일", "완료일", "기준일", "접수일", "계약일"],
    "text": ["비고", "담당부서", "주요 내용", "사업명", "소관", "추진 방향", "근거 법령"],
}
STUB_HEADERS = ["구분", "항목", "지역", "부서", "사업명", "연도", "기관명", "분야"]
STUB_GROUPS = [["국비", "지방비", "민간"], ["일반회계", "특별회계", "기금"], ["본청", "사업소", "출연기관"],
               ["경제", "복지", "교육", "환경"], ["공공", "민간"], ["수도권", "비수도권"]]
REGIONS = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남",
           "전북", "전남", "경북", "경남", "제주"]
DEPTS = ["기획조정실", "재정경제과", "일자리정책과", "복지정책과", "교육지원과", "디지털혁신팀", "안전총괄과",
         "도시계획과", "환경정책과", "문화관광과", "보건위생과"]
PROJECT_A = ["청년", "노후", "스마트", "취약계층", "탄소중립", "지역", "공공", "디지털", "중소기업", "농어촌"]
PROJECT_B = ["일자리 지원", "인프라 개선", "시티 조성", "돌봄 강화", "실천 확산", "상생 협력", "서비스 혁신",
             "역량 강화", "판로 개척", "주거 안정"]
ITEMS = ["인건비", "운영비", "시설비", "연구개발비", "여비", "업무추진비", "자산취득비", "보조금", "위탁사업비"]
NOTES = ["해당 없음", "추진 중", "완료", "예정", "계속사업", "신규사업", "조정 필요", "협의 중", "-",
         "관계부처 협의 후 확정", "하반기 추가 반영 예정", "전년도 이월분 포함"]
EMPTY_MARKS = ["-", "", "－", "…"]


def stub_text(rng: random.Random, kind: str) -> str:
    if kind == "region":
        return rng.choice(REGIONS)
    if kind == "dept":
        return rng.choice(DEPTS)
    if kind == "item":
        return rng.choice(ITEMS)
    if kind == "year":
        return rng.choice(YEARS)
    p = f"{rng.choice(PROJECT_A)} {rng.choice(PROJECT_B)}"
    if rng.random() < 0.25:
        p += "\n사업"  # 셀 내 줄바꿈
    return p


def _comma(n: int) -> str:
    return f"{n:,}"


def value(rng: random.Random, kind: str) -> str:
    r = rng.random()
    if r < 0.04:
        return rng.choice(EMPTY_MARKS)
    if kind == "int":
        return _comma(rng.choice([rng.randint(0, 99), rng.randint(100, 9_999), rng.randint(10_000, 999_999)]))
    if kind == "money":
        if rng.random() < 0.3:
            return f"{rng.uniform(0.1, 999):.1f}"
        return _comma(rng.randint(1, 9_999_999))
    if kind == "pct":
        v = f"{rng.uniform(0, 100):.{rng.choice([0, 1, 1, 2])}f}"
        return v + ("%" if rng.random() < 0.3 else "")
    if kind == "delta":
        n = rng.randint(1, 99_999)
        sign = rng.random()
        if sign < 0.35:
            return f"△{_comma(n)}"   # 한국 공문서식 음수 표기
        if sign < 0.5:
            return f"-{_comma(n)}"
        if sign < 0.6:
            return "0"
        return _comma(n) if rng.random() < 0.7 else f"+{_comma(n)}"
    if kind == "date":
        y, m, d = rng.randint(2019, 2026), rng.randint(1, 12), rng.randint(1, 28)
        return rng.choice([f"{y}.{m:02d}.{d:02d}.", f"{y}-{m:02d}-{d:02d}", f"'{y % 100}.{m}.{d}.",
                           f"{y}. {m}. {d}.", f"{m}.{d}.~{min(12, m + 1)}.{d}."])
    if kind == "text":
        t = rng.choice(NOTES)
        if rng.random() < 0.15:
            t = f"{rng.choice(DEPTS)}\n({rng.choice(NOTES)})"
        return t
    raise ValueError(kind)


def leaf_header(rng: random.Random, kind: str) -> str:
    return rng.choice(LEAF_HEADERS[kind])


def group_header(rng: random.Random, level: int) -> str:
    pool = YEARS if level == 0 and rng.random() < 0.5 else (
        QUARTERS + HALVES if rng.random() < 0.3 else GROUP_HEADERS)
    return rng.choice(pool)


# ---- 데이터 보강(009): 예산·결산 공문서에서 반복되는 헤더 패턴과 어휘 (특정 셀 값은 복사하지 않음) ----
ACCOUNTS = ["일반회계", "특별회계", "기금", "환경개선\n특별회계", "교통시설특별회계\n(도로계정)", "지역균형발전\n특별회계",
            "농어촌구조개선\n특별회계", "고용보험\n기금", "국민건강증진\n기금", "에너지및자원사업\n특별회계", "주택도시기금\n(주택계정)"]
STUB_HEADER_PAIRS = [("회계·\n기금명", "세부사업명"), ("회계\n기금", "프로그램별"), ("회계\n기금", "단위사업별"),
                     ("회계·기금명", "세부사업명\n(내역사업명)"), ("구분", "항목"), ("부처명", "세부사업명")]
BUDGET_WORDS_A = ["기관운영", "청사시설", "정보화", "연구개발", "인력양성", "국제협력", "안전관리", "지역혁신", "디지털전환",
                  "산업기반", "환경보전", "복지서비스", "공공데이터", "재난대응", "문화진흥"]
BUDGET_WORDS_B = ["기본경비", "지원", "운영", "구축", "확충", "개선", "활성화", "강화", "육성", "조성"]
BUDGET_SUFFIX = ["", "", "", "(R&D)", "(보조)", "(정보화)", "(포상금)", "(신규)", "(ODA)"]
REASONS = ["사업 준비 부족 등을 고려하여 조정", "집행 실적 부진에 따라 감액", "유사 사업과의 중복성을 고려하여 조정",
           "단가 조정에 따른 감액", "타 사업으로 이관", "실집행 가능액을 고려하여 조정", "사업 추진 일정 지연에 따라 감액"]


def budget_item(rng: random.Random) -> str:
    t = f"{rng.choice(BUDGET_WORDS_A)} {rng.choice(BUDGET_WORDS_B)}{rng.choice(BUDGET_SUFFIX)}"
    if rng.random() < 0.2:
        t = f"({t})"            # 내역사업 표기
    return t


def reason(rng: random.Random) -> str:
    return rng.choice(REASONS) if rng.random() < 0.7 else "-"
