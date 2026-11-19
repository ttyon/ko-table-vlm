# 013 데이터셋·학습 방법 정리 (Data & Training Card)

> 001~012에 흩어져 있던 **"무엇으로, 어떻게 학습하고, 무엇으로 평가했는가"** 를 한 문서에 모은 참조용 카드.
> 재현 명령은 각 항목에, 실험별 판단 근거는 해당 번호 문서에 있다.

---

## 1. 과제 정의
| 항목 | 내용 |
|---|---|
| 입력 | 표 하나가 담긴 이미지 (PNG/JPEG, 긴 변 ≤1280px, 최종 추론 시 긴 변 1280으로 리사이즈) |
| 출력 | 표 구조 HTML — `<table>/<tr>/<td>`와 `rowspan`/`colspan`만 사용 (정규화 규칙: `table.py`, 004) |
| 프롬프트 | `prompts.py` v1 (학습·추론 동일): "이 이미지의 표를 HTML로 변환하라. <table>, <tr>, <td> 태그와 rowspan, colspan 속성만 사용하고, 병합된 셀은 반드시 rowspan/colspan으로 표현하라. 셀 안의 줄바꿈은 공백 하나로 바꾸고, 설명 없이 HTML만 출력하라." |
| 언어·도메인 | 한국어 행정·예산·통계 문서의 표 |

---

## 2. 데이터셋 구성

### 2-1. 한눈에 보기
| 이름 | 개수 | 출처 | 용도 | 정답 | git 공개 |
|---|---|---|---|---|---|
| `train` | 3,000 | 합성 (seed 1) | 학습 | 생성 시 자동 | 생성기 코드만 |
| `train_aug` | 3,000 | 합성 + 실제 문서 패턴 템플릿 (seed 11, `--aug`) | 학습 | 자동 | 생성기 코드만 |
| `val` | 300 | 합성 (seed 2) | 체크포인트·설정 **선택** (앞 100개 사용) | 자동 | 생성기 코드만 |
| `test` | 300 | 합성 (seed 3) | 평가 — 학습과 같은 분포 | 자동 | 생성기 코드만 |
| `ood` | 300 | 합성, **학습에 없는 스타일** (seed 4) | 평가 — 스타일 일반화 | 자동 | 생성기 코드만 |
| `dev_unlabeled` | 17 | 실제 (국회예산정책처 PDF, test-real과 다른 표) | 선택 — 반복·잘림 검사만 (정답 불필요) | 없음 | ✗ |
| **`test-real`** | **50** | 실제 — 국회예산정책처 문서 2종 | **평가 — 핵심** | 사람 검수 | ✗ (출처만) |
| **`test-real-2`** | **15** | 실제 — 통계청·보건복지부·행정안전부 | 평가 — **다른 기관 일반화** (014) | 사람 검수 | ✗ (출처만) |
| `scan` 변형 | 50 + 15 | test-real·test-real-2에 스캔 열화 모사 | 평가 — 스캔 품질 강건성 (014) | 원본과 동일 | ✗ |
| `res` 변형 | 50 / 50 / 15 | 긴 변 640~1600 리사이즈 | 평가 — 해상도 (010) | 원본과 동일 | ✗ |

합성 데이터는 `make data`(약 6분) + `generate --split train_aug --n 3000 --seed 11 --aug`로 **완전히 재현** 가능하므로 이미지는 올리지 않는다.
실제 문서 이미지·정답은 로컬에만 보관한다 (`.gitignore`). 출처는 `data/real/SOURCES.md`, `data/real2/SOURCES.md`.

### 2-2. 합성 데이터 (002, 009)
**생성 방식**: 무작위 표 구조·내용·스타일 → HTML → Playwright(Chromium)로 렌더링 → 표 영역 캡처 → 열화 → PNG + 정답 HTML.

| 요소 | 원본 생성기 (`train`·`val`·`test`) | 보강 (`train_aug`, 50%가 템플릿) |
|---|---|---|
| 헤더 | 1~3단(0.45/0.4/0.15), 재귀 colspan 분할, 하위 없으면 rowspan | + 실제 문서 템플릿 3종: 연도별 `예산\|수납`, `결산·예산(A)·예산(B)·증감(B-A, (B-A)/A)`, `국회 심의결과 > 상임위 예비심사·본회의 수정 > 증액·감액·증감` |
| 2줄 헤더 | 거의 없음 | `2023\n결산`, `2026\n확정예산` 등 |
| stub(분류) 열 | 1~2개, 세로 병합 1~4행 | 40% 확률로 본문 전체를 덮는 긴 병합 |
| 본문 병합 | 35% 표에서 셀별 8% | 동일 |
| 합계 행 | 40% | 40% |
| 내용 | 지역·부서·사업명, 숫자(쉼표, `△` 음수, `%`), 날짜 5형식, 빈칸 기호, 셀 내 줄바꿈 | + 회계·기금명, `기본경비`·`(R&D)`·`(보조)`, 감액 사유 문장, 열 의미 일관(금액·증감·비율) |
| 스타일 | 폰트 6종, 테두리 4종, 헤더 배경 5종, 패딩·정렬·줄무늬, 렌더 배율 1~2 | + 진한 청록/파랑 헤더+흰 글씨, 점선 행 구분, 단어 중간 줄바꿈 |
| 열화 (44%) | 축소-확대, ±0.8° 회전, 흐림, 흑백, JPEG | 동일 |
| ood 전용 (평가만) | 폰트 3종(Gowun·코딩체), 점선·이중선 테두리, 주황·남색 헤더 | 보강에도 넣지 않음 |

통계 (002): 평균 10.2행×6.3열, 병합 셀 평균 4.4개, 이미지 평균 794×531, 정답 HTML 평균 991자. 쉬운 표(simple)는 6%뿐.

### 2-3. 실제 문서 테스트셋 (003, 014)
| | test-real | test-real-2 |
|---|---|---|
| 기관 | 국회예산정책처 | 통계청, 보건복지부, 행정안전부 |
| 문서 | 「2025 대한민국 재정」, 「2026년도 예산안 심의결과」 | 「2023년 사회조사 결과」 보도자료, 보건의료인력 실태조사 KOSIS 게시 보도참고자료, 지자체 재정공시 보도자료 |
| 라이선스 | 공공누리 제1유형 | 정책브리핑 게시 "텍스트에 한하여 공공누리 제1유형" |
| 페이지 선택 | `(단위` 포함 페이지 중 문서별 25쪽 (seed 0) | 통계청 20쪽 (seed 0), 짧은 두 문서는 전체 |
| 표 검출 | Docling 레이아웃 (PDF 2배 렌더) | 동일 |
| 정답 | Docling PDF 텍스트 레이어 초안 → 이미지와 대조해 사람이 구조 수정 | 동일 |
| 개수 | 50 (67개 검출 중) | 15 (37개 검출 중) |
| 특징 | 다단 헤더·긴 세로 병합, 병합 셀 포함 82% | 긴 표(평균 22행), 테두리 적음, 자간 라벨, L자형 헤더, 병합 포함 40% |

**제외 기준**: 이미지만으로 정답을 정할 수 없는 표(잘려서 헤더 글자가 안 보임, 본문 중간 구역 제목 행), 개인정보(담당자 이름·전화번호)가 있는 표, 2×3 수준의 사소한 표.

**라벨링 규칙** (003, 014): 표 밖 캡션 제외 / 셀 내 줄바꿈 → 공백 / 각주 표시(`1)`) 유지 / 자간 라벨(`남   자`, `구 분`)은 붙여 씀 / 가운뎃점 변형은 채점 시 통일 / L자형 헤더는 "상위 항목 rowspan 2 + 하위 열 위 빈칸(colspan) + 하위 항목" 으로 통일 (014).

### 2-4. 학습 데이터 형식 (`to_sft.py`)
`mlx_vlm.train`이 읽는 JSONL, 한 줄 = 표 하나:
```json
{"images": ["/절대경로/train_000123.png"],
 "messages": [{"role": "user", "content": "<prompts.py v1>"},
              {"role": "assistant", "content": "<table><tr><td rowspan=\"2\">구분</td>…</table>"}]}
```
| SFT 데이터 | 구성 | 행 수 |
|---|---|---|
| `data/sft/html` | `train` → 정규화 HTML | 3,000 |
| `data/sft/otsl` | `train` → OTSL (008) | 3,000 |
| `data/sft/html_aug` | `train_aug` → HTML | 3,000 |
| **`data/sft/html_mix`** | `html` + `html_aug` 섞기 (seed 0) — **최종 모델** | 6,000 |
| valid (공통) | `val` → 각 형식 | 300 |
정답이 6,000자를 넘는 표는 제외하도록 했지만(`--max-chars`), 실제로 걸린 샘플은 없다.

### 2-5. 오염(누수) 방지
- test·ood·test-real·test-real-2는 학습·체크포인트 선택에 쓰지 않는다. 선택은 `val`(합성)과 `dev_unlabeled`(정답 없이 잘림만)으로.
- 합성 split은 seed가 모두 다르다(1/2/3/4/11).
- **알려진 한계**: 보강 데이터(`train_aug`)의 설계와 해상도 비교는 **test-real의 실패를 보고** 정했다(셀 값 복사는 없음). 이 영향이 없는 **test-real-2**가 그래서 필요했다 (014).

---

## 3. 학습 방법

### 3-1. 모델과 방법
| 항목 | 값 |
|---|---|
| 기본 모델 | `mlx-community/Qwen3.5-2B-bf16` (전체 2,213M 파라미터, bf16) |
| 방법 | **LoRA SFT** (지도 미세조정), 비전 인코더는 **고정** |
| LoRA 적용 위치 | 언어 모델 24층 전체(`num_layers -1`), 186개 모듈: MLP(gate/up/down) 24층 · Gated DeltaNet 선형 어텐션(in_proj_qkv/z/a/b, out_proj) 18층 · Full attention(q/k/v/o) 6층 |
| rank / alpha / scale | 16 / 32 / **2.0** (mlx-vlm: scale = alpha/rank) |
| dropout | 0.05 |
| 학습 파라미터 | **16.8M (0.76%)** |
| 손실 | 다음 토큰 cross-entropy, **답변(HTML) 토큰에만** (`--train-on-completions`) |
| 최적화 | AdamW, lr 1e-4 **고정**(스케줄 없음), batch 1, gradient checkpointing |
| 프레임워크 | mlx-vlm 0.8.0 / mlx 0.32.4, Mac Studio M5 Max 64GB |
| 검증·저장 | 250 iter마다 val loss(25 배치), 500 iter마다 체크포인트 |

명령: `MODEL=models/Qwen3.5-2B-bf16 DATA=data/sft/html_mix NAME=... RANK=16 ITERS=3000 ./scripts/train.sh`

### 3-2. 체크포인트 선택 규칙 (009c)
체크포인트(1,500/2,000/2,500/3,000)마다 ① `val` 앞 100 TEDS ② `dev_unlabeled` 17개의 **잘림(반복 붕괴) 수** → **잘림 0 중 val TEDS 최고**.
이유: 마지막 체크포인트가 실제 문서에서 같은 단어를 4,096 토큰까지 반복하는 붕괴를 보였고, 합성 val로는 이를 잡지 못했다.

### 3-3. 학습한 모델 목록
| 모델 (`adapters/`) | 데이터 | iter | 학습 시간 | 피크 메모리 | 비고 | 문서 |
|---|---|---|---|---|---|---|
| `lora_html_r16` | html (3,000) | 3,000 (1 epoch) | 81분 | 13.1GB | 1차 모델 | 006 |
| `lora_otsl_r16` | otsl | 3,000 | 77분 | 13.1GB | 출력 형식 비교 | 008 |
| `lora_html_aug_r16` (→ `_it2500`) | html_aug | 3,000 | 97분 | 13.2GB | 보강 | 009 |
| `lora_html_mix_r16` | html_mix (6,000) | 3,000 | 91분 | 13.1GB | 3,000 iter는 반복 붕괴 | 009b |
| **`lora_html_mix_r16_it1500`** | html_mix | **1,500** | ~46분 | 13.1GB | **최종 모델** (선택 규칙으로 선정) | 009c |
| `html_mix_r8_it1500` / `html_mix_r32_it1500` | html_mix | 1,500 | 47분 / 46분 | 13.0 / 13.3GB | rank 비교 | 011 |
| `lora_4b_html_r16` | html_mix | 1,500 | 81분 | 11.4GB | `Qwen3.5-4B-MLX-4bit` QLoRA | 011 |

최종 모델은 batch 1 × 1,500 iter라 **6,000장 중 약 1,500장(원본·보강 각 ~750장)만 본 상태**다 — 이 과제에서는 데이터 양보다 데이터 분포(실제 패턴)가 더 중요했다는 증거이기도 하다.

### 3-4. 추론 설정
| 항목 | 값 |
|---|---|
| 서빙 | `mlx_vlm.server` + `--adapter-path` (OpenAI 호환, `scripts/serve_model.sh`, 포트 8081) |
| 디코딩 | temperature 0, max_tokens 4096, thinking 끔, repetition_penalty 없음 |
| 입력 | 긴 변 **1280**으로 리사이즈 (010) |
| 동시성 | 2요청 (continuous batching) — 지연 측정 기준 |
| 후처리 | 출력에서 첫 `<table>…</table>` 추출 → 정규화 (`table.extract_table_html`, `normalize_html`) |

---

## 4. 평가
| 지표 | 정의 (004) |
|---|---|
| TEDS | 표 트리 편집거리 유사도, 셀 텍스트 포함 (1이 완벽). thead/tbody 구분 없음 → 논문 수치와 직접 비교 불가 |
| TEDS-S | 셀 텍스트 무시, 구조만 |
| 셀 CER | 같은 격자 위치 셀끼리 문자 오류율 |
| 병합 셀 재현율 | 정답 병합 셀 중 위치·span까지 맞힌 비율 |
| 유효율 / 잘림 | 표 추출 가능 비율 / max_tokens 도달 비율 |
| 공백 무시 TEDS | 셀 공백 전부 제거 후 TEDS (자간·띄어쓰기 모호성 민감도) |
평가 규칙 v3: 태그·속성 정규화 + NFKC + 가운뎃점 통일. 느린 시스템은 같은 부분집합(앞 50/100개)으로 비교, 작은 차이는 샘플별 승패로 확인.

## 5. 재현 순서 (요약)
```bash
make setup && make test
make data                                                     # 합성 train/val/test/ood
uv run python -m ko_table_vlm.generate --split train_aug --n 3000 --seed 11 --aug
make sft && uv run python -m ko_table_vlm.to_sft --train data/generated/train_aug/manifest.jsonl \
    --valid data/generated/val/manifest.jsonl --out data/sft/html_aug          # + html_mix는 queue_week3.sh mix 참고
./scripts/queue_week3.sh mix                                  # 혼합 데이터 학습 + 평가
./scripts/select_ckpt.sh lora_html_mix_r16 1500 2000 2500 3000  # 체크포인트 선택
BEST=lora_html_mix_r16_it1500 ./scripts/queue_week3.sh res     # 해상도 실험
./scripts/queue_real2.sh                                      # 다른 기관·스캔 모사 평가 (실제 문서는 직접 수집·검수 필요)
```
