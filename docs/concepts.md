# 핵심 개념 정리

## 1. 표 인식(Table Recognition)의 세부 문제
| 단계 | 하는 일 | 이 프로젝트 |
|---|---|---|
| 표 검출 (Table Detection) | 페이지에서 표 위치(bbox) 찾기 | Docling 레이아웃 모델로 대체 (`real detect`) |
| **표 구조 인식 (TSR)** | 행·열·병합 셀 구조 복원 | **핵심** |
| 셀 내용 인식 | 셀 안 글자 읽기 (OCR) | VLM이 구조와 함께 한 번에 출력 |
| 기능 분석 | 헤더/데이터 구분, 의미 해석 | 범위 밖 (확장 아이디어) |

## 2. 기존 방식 vs VLM 방식
| | 기존 파이프라인 (Docling, PaddleOCR 등) | End-to-end VLM (이 프로젝트) |
|---|---|---|
| 구성 | 레이아웃 검출 → 구조 모델(TableFormer) → OCR → 셀 매칭 | 이미지 → 모델 → HTML/OTSL |
| 장점 | 빠름, 위치 정보 정확, 검증된 도구 | 구조와 글자를 함께 봄, 한 모델, 미세조정 쉬움 |
| 약점 | 단계마다 오류 누적, OCR 언어·셀 매칭 실패 | 느림(토큰 생성), 긴 표에서 잘림·반복, 환각 |

스모크 테스트(3개)에서 본 Docling 실패 예: 다단 헤더 분리, `△`(음수 표기)를 `A`로 인식, 테두리 없는 표의 셀 병합/분리 오류.

## 3. TEDS
- 표를 `table → tr → td` 트리로 보고, 예측 트리를 정답 트리로 바꾸는 최소 편집 비용(삽입·삭제·변경)으로 유사도 계산.
- `TEDS = 1 − 편집거리 / max(두 트리의 노드 수)`, 1이 완벽.
- td 변경 비용: rowspan/colspan이 다르면 1, 같으면 셀 텍스트 편집거리 비율 → 구조와 내용 모두 반영.
- **TEDS-S**: 텍스트를 무시한 구조 점수. TEDS와 TEDS-S의 차이 = OCR로 잃은 점수.
- 주의: 이 저장소 구현은 thead/tbody를 구분하지 않음 → PubTabNet 논문 수치와 직접 비교 금지, 같은 구현으로만 비교.

## 4. OTSL
- 격자 칸마다 토큰 하나로 표를 쓰는 형식: `<fcel>`(내용), `<ecel>`(빈칸), `<lcel>`(왼쪽 병합), `<ucel>`(위쪽 병합), `<xcel>`(양쪽 병합), `<nl>`(행 끝).
- HTML보다 짧고(태그·속성 반복 없음), 문법이 단순해 항상 직사각형 격자가 됨 → 모델이 틀릴 여지가 줄어듦.
- 3주차 실험: 같은 모델·데이터로 HTML vs OTSL 학습 → 출력 토큰 수, 속도, TEDS 비교 (`make sft`가 두 형식 모두 생성).

## 5. 합성 → 실제 격차 (sim-to-real gap)
- 합성 데이터는 라벨이 완벽하지만 실제 문서의 다양성(스캔 품질, 이상한 레이아웃, 각주, 단위 표기)을 다 담지 못함.
- 그래서 **test-real**이 이 프로젝트에서 가장 중요한 숫자. test(합성)에서만 오르고 test-real에서 안 오르면 과적합.
- 격차를 줄이는 방법: 열화(degrade) 강화, 스타일 다양화, 실제 실패 유형을 생성기에 반영(데이터 보강), 공개 실데이터(PubTabNet 등) 혼합.

## 6. 참고 문헌
- Zhong et al., *Image-based table recognition: data, model, and evaluation* (PubTabNet, TEDS), ECCV 2020
- Nassar et al., *TableFormer: Table Structure Understanding with Transformers*, CVPR 2022
- Lysak et al., *Optimized Table Tokenization for Table Structure Recognition* (OTSL), ICDAR 2023
- Docling Technical Report (IBM, 2024)
- `../VLM/` 노트 005(해상도·토큰), 007(학습), 009(평가)
