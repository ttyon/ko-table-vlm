# Korean Table VLM

**학습 영역** · Document AI + VLM Fine-tuning + Synthetic Data · **기간** 4주

한국어 문서의 **복잡한 표 이미지**(병합 셀, 다단 헤더, 셀 내 줄바꿈, 테두리 없는 표)를 **HTML 표 구조**로 복원하는 소형 VLM을 학습합니다.
정답이 자동으로 붙는 **합성 표 생성기**로 학습 데이터를 만들고, 실제 공공 문서 표로 평가해
**Docling(TableFormer) · 큰 VLM zero-shot · LoRA 학습 소형 VLM**을 같은 지표(TEDS)로 비교합니다.

**현재 상태** · 1~3주차 완료 (2026-11-19). 문서는 [`docs/`](docs/README.md)를 번호 순서대로, 결론은 [`docs/012_summary.md`](docs/012_summary.md).

| 시스템 | 합성 test | **실제 문서 (50)** | 표당 지연 |
|---|---|---|---|
| Docling (TableFormer) | 0.854 | 0.773 | **0.8초** |
| Qwen3.5-2B zero-shot | 0.936 | 0.896 | 5초 |
| **Qwen3.5-2B + LoRA (보강·혼합 데이터) + 입력 1280** | 0.982 | **0.956** | 8초 |
| Qwen3.8-27B zero-shot + 입력 1280 | — | **0.985** | 24초 |

TEDS 기준. 합성 데이터만으로 학습한 2B가 실제 공문서 표에서 Docling을 크게 앞섰고, 실패 분석 → 데이터 보강 → 체크포인트 선택 → 해상도 조정으로 0.896 → 0.956까지 올렸다. 27B와의 격차는 남아 있다.

**일반화 확인 (014)**: 다른 기관 문서 15개에서는 최종 2B가 0.805로 학습 전(0.900)보다 낮았다 — 합성 데이터에 긴 표(30행+)·목록형 표가 없어 반복 붕괴. 반면 스캔 품질 모사에서는 Docling이 0.087로 무너지고 VLM은 유지(2B 0.941, 27B 0.983). 학습 데이터·평가 세트 구성과 학습 설정은 [`docs/013`](docs/013_data-and-training-card.md).

```
표 이미지                                         출력 (HTML)
┌──────────┬─────────────────────┐        <table>
│          │      2025년          │          <tr><td rowspan="2">구분</td><td colspan="2">2025년</td></tr>
│   구분   ├──────────┬──────────┤   ──▶    <tr><td>상반기</td><td>하반기</td></tr>
│          │  상반기   │  하반기   │          <tr><td>예산(억원)</td><td>1,250</td><td>△1,410</td></tr>
├──────────┼──────────┼──────────┤        </table>
│ 예산(억원) │  1,250   │  △1,410  │
└──────────┴──────────┴──────────┘
```

## 빠른 시작
```bash
cd ~/ttyon/study/ko-table-vlm
make setup          # 의존성(+docling), Chromium, 한글 폰트 8종
make test           # 단위 테스트
make data-small     # 소량 데이터로 흐름 확인 (1분)
make preview        # data/generated/train/preview.html 에서 이미지·정답 나란히 확인
make help           # 전체 명령
```
SSH 원격에서 preview 보기: 프로젝트 루트에서 `uv run python -m http.server 8090 --bind 127.0.0.1` → 맥북에서 `ssh -L 8090:127.0.0.1:8090 studio` → `http://127.0.0.1:8090/data/generated/train/preview.html`

## 구성
| 파일 | 역할 |
|---|---|
| `src/ko_table_vlm/generate.py` | 합성 표 생성기 (구조·내용·스타일 무작위 → Playwright 렌더링 → 열화 → PNG + 정답 HTML) |
| `src/ko_table_vlm/content.py` / `styles.py` | 한국어 행정·통계 어휘, 숫자 표기(`△` 음수 등) / 렌더링 스타일(train·ood 분리) |
| `src/ko_table_vlm/table.py` | 정답 HTML 정규화 규칙, 모델 출력에서 표 추출, 격자 변환 |
| `src/ko_table_vlm/otsl.py` | HTML ↔ OTSL 변환 (출력 형식 실험) |
| `src/ko_table_vlm/metrics.py` | TEDS, TEDS-S, 셀 CER, 병합 셀 재현율 |
| `src/ko_table_vlm/prompts.py` | 학습·추론 공용 프롬프트 (버전 관리) |
| `src/ko_table_vlm/to_sft.py` | manifest → `mlx_vlm.train` 데이터 |
| `src/ko_table_vlm/predict.py` | 예측 실행 (OpenAI 호환 API / Docling), 이어서 실행 가능 |
| `src/ko_table_vlm/evaluate.py` / `report.py` | 채점·태그별 요약 / 여러 실행 비교표 |
| `src/ko_table_vlm/preview.py` | 이미지·정답·예측 나란히 보기 (TEDS 낮은 순) |
| `src/ko_table_vlm/real.py` | 실제 문서 표 테스트셋 만들기 (PDF → 표 검출·crop → 초안 → 검수 → manifest) |
| `scripts/train.sh` / `serve_model.sh` / `download_model.sh` / `download_fonts.sh` | 학습 / 어댑터 서빙 / 모델·폰트 받기 |
| `docs/concepts.md` | TSR, TEDS, OTSL, 합성→실제 격차 개념 정리 |

## 데이터 분할
| 분할 | 개수 | 용도 |
|---|---|---|
| train | 3,000 | 학습 |
| val | 300 | 체크포인트·하이퍼파라미터 선택 |
| test | 300 | 합성 테스트 (학습과 같은 스타일 분포) |
| **ood** | 300 | **학습에 없는 폰트·테두리·색**으로만 만든 일반화 테스트 |
| **test-real** | 50~100 | **실제 공공 문서 표** — 가장 중요한 숫자 |

## 측정 지표
TEDS(구조+내용), TEDS-S(구조만), 셀 CER, 병합 셀 재현율, HTML 유효율, 잘림 비율, p50/p95 지연, 출력 토큰 수.
태그별(`multi_header`, `merged_body`, `borderless`, `simple`, `real`)로 나눠 보고합니다. 개념은 `docs/concepts.md`.

## 4주 체크리스트

### 1주차 — 데이터와 기준선
- [x] `make setup && make test`
- [x] `make data` (약 6분) → `make preview`로 30장 눈으로 확인, 이상한 패턴은 `content.py`/`styles.py` 수정
- [x] 실제 표 PDF 수집 → `data/real/pdfs/`, 출처는 `data/real/SOURCES.md`
- [x] `uv run --extra docling python -m ko_table_vlm.real detect` → `data/real/images/`
- [x] 정답 초안 (실제로는 27B 대신 Docling PDF 텍스트 레이어로 — 글자가 원문 그대로라 검수가 쉬움, `docs/003`) → `data/real/labels/*.html` 직접 수정 → 첫 줄 `<!-- DRAFT -->` 삭제
      (검수 도우미: `uv run python -m ko_table_vlm.preview --data data/real/labels`)
- [x] `uv run python -m ko_table_vlm.real build` → `data/real/manifest.jsonl` (50개 목표)
- [x] 기준선: Docling 300개, 2B 100개, 27B 50개 (27B는 표당 ~35초라 50개로 축소, `docs/005`)
- [x] test-real에도 같은 명령 (`--data data/real/manifest.jsonl --run runs/<이름>_real`)
- [x] `make report` → 비교표를 `docs/005_baselines.md` 에 정리

### 2주차 — 소형 모델 LoRA
- [x] `./scripts/download_model.sh` (Qwen3.5-2B-bf16)
- [x] 학습 전 성능: `tmux new -d -s tvlm './scripts/serve_model.sh'` → `make baseline-2b` → 서버 종료
- [x] `make sft` → `NAME=r16_html ./scripts/train.sh` (로그: `runs/train_r16_html.log`)
- [x] `ADAPTER=adapters/r16_html ./scripts/serve_model.sh` → test / ood / test-real 예측·채점
- [x] `uv run python -m ko_table_vlm.preview --data <manifest> --run runs/<이름> --worst` 로 실패 사례 분류
      (병합 셀 누락 / 행·열 밀림 / 셀 OCR 오류 / HTML 깨짐 / 잘림·반복)

### 3주차 — 개선 실험 (하나 이상, 매번 val로 고르고 test·ood·real로 보고)
- [x] **출력 형식**: `DATA=data/sft/otsl NAME=r16_otsl ./scripts/train.sh` → 예측 시 `--format otsl` → 토큰 수·속도·TEDS 비교
- [x] **데이터**: 실패 유형 맞춤 보강 (생성기 확률 조정, 열화 강화) → 재학습
- [x] **해상도**: `--max-side 960/1280/1600`으로 생성해 TEDS vs 지연 (`VLM/005` 노트)
- [x] **모델 크기**: `MODEL=models/Qwen3.5-4B-MLX-4bit` (QLoRA)
- [x] **rank**: 8 / 16 / 32

### 4주차 — 정리와 공개
- [ ] `make report` → README 상단에 최종 결과표 (시스템 × test/ood/real), 성공·실패 예시 이미지
- [ ] 데모: PDF → `real detect`로 표 crop → 어댑터 서버로 HTML → Markdown 변환 CLI (선택)
- [ ] (선택) Hugging Face에 생성기 코드·합성 데이터셋·LoRA 어댑터 공개 (데이터 카드에 생성 방식·한계 명시)
- [ ] 회고: 합성→실제 격차, 가장 효과 컸던 개선, Docling 대비 장단점

## 소요 시간 감 (M5 Max 64GB 실측/추정)
| 작업 | 시간 |
|---|---|
| 합성 표 생성 | ~11장/초 (3,900장 ≈ 6분) |
| 27B zero-shot 예측 | 표당 ~25~50초 (출력 700~1,500 토큰) |
| Docling 예측 | 표당 ~1초 (워밍업 후) |
| 2B LoRA 학습 (rank 16) | ~2초/스텝, 피크 메모리 ~12GB → 3,000스텝 ≈ 100분 (스모크 20스텝 실측) |
| 2B 예측 (+어댑터) | 표당 ~7~10초 (정상 종료 시), 반복 출력 시 max_tokens까지 ~55초 |

## 주의
- 실제 문서는 이용 조건이 명확한 공개 문서만, 출처 기록. 개인정보가 담긴 표 제외.
- test·ood·test-real은 학습·하이퍼파라미터 선택에 쓰지 않음 (선택은 val로).
- 프롬프트를 바꾸면 `prompts.py`의 `PROMPT_VERSION`을 올리고 학습·평가를 다시.
- TEDS 구현은 thead/tbody를 구분하지 않으므로 논문 수치와 직접 비교하지 않음.
- 결과표에는 표본 수와 실행 조건(`runs/*/run.json`)을 함께 적음 (`PORTFOLIO_GUIDE.md`).
