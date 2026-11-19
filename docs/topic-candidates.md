# 1개월 문서 처리 VLM 프로젝트 후보 (2026-11)

선정 기준: Mac Studio(M5 Max 64GB, MLX)에서 4주 안에 **데이터 → 학습 → 평가 → 공개**까지 완주 가능, 라벨 비용이 낮음, 문서 처리 경험을 살릴 수 있음.

| # | 주제 | 데이터 | 평가 | docling-ko(친구)와 겹침 | 결정 |
|---|---|---|---|---|---|
| A | **한국어 복잡한 표 인식 (표 이미지 → HTML)** | HTML 표 렌더링 자동 라벨 + 실제 공공 문서 표 | TEDS, TEDS-S, 셀 CER | 낮음 | ✅ 선택 |
| B | 한국어 서식 문서 KIE + 근거 bbox (신청서·계약서·공문) | 합성 서식 렌더링 | 필드 F1, IoU | 낮음 | 후보 |
| C | 페이지 → Markdown 소형 모델 (27B/Docling 출력으로 증류) | Docling·27B 출력 | 편집 거리, 속도 | 높음 | 제외 |
| D | 시각 문서 검색 (페이지 이미지 임베딩 RAG) | 공개 문서 + 생성 질문 | Recall@k, nDCG | 낮음 | A의 후속 확장 |

## docling-ko와의 차이
- docling-ko: PDF → Docling DocTags 라벨 → Qwen-VL LoRA SFT, **페이지 전체 구조 파싱**.
- 이 프로젝트: **표 하나를 깊게** — 병합 셀·다단 헤더 중심의 합성 생성기, 실제 공공 문서 표 테스트셋, Docling(TableFormer)·큰 VLM과 TEDS로 직접 비교, 출력 형식(HTML vs OTSL) 실험.
