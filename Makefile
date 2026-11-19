# 자주 쓰는 명령 모음.  make help
.PHONY: help setup test data data-small sft preview baseline-27b baseline-2b baseline-docling eval-all report

PY := uv run python -m ko_table_vlm
TEST := data/generated/test/manifest.jsonl
OOD := data/generated/ood/manifest.jsonl
LIMIT ?= 100

help:
	@grep -E '^[a-z0-9-]+:.*## ' Makefile | sed 's/:.*## /\t/' | column -t -s "$$(printf '\t')"

setup: ## 의존성 + Chromium + 한글 폰트
	uv sync --extra docling
	uv run playwright install chromium
	./scripts/download_fonts.sh

test: ## 단위 테스트
	uv run pytest -q

data: ## 합성 데이터 전체 (train 3000 / val 300 / test 300 / ood 300, 약 6분)
	$(PY).generate --split train --n 3000 --seed 1
	$(PY).generate --split val --n 300 --seed 2
	$(PY).generate --split test --n 300 --seed 3
	$(PY).generate --split ood --n 300 --seed 4

data-small: ## 빠른 확인용 소량 데이터
	$(PY).generate --split train --n 100 --seed 1
	$(PY).generate --split val --n 20 --seed 2
	$(PY).generate --split test --n 20 --seed 3
	$(PY).generate --split ood --n 20 --seed 4

sft: ## 학습 데이터 변환 (html, otsl 둘 다)
	$(PY).to_sft --train data/generated/train/manifest.jsonl --valid data/generated/val/manifest.jsonl --out data/sft/html --format html
	$(PY).to_sft --train data/generated/train/manifest.jsonl --valid data/generated/val/manifest.jsonl --out data/sft/otsl --format otsl

preview: ## 생성 데이터 미리보기 HTML
	$(PY).preview --data data/generated/train/manifest.jsonl --n 30

baseline-27b: ## 큰 모델 zero-shot (8080, LIMIT개)
	$(PY).predict --data $(TEST) --run runs/qwen27b_zeroshot --limit $(LIMIT)
	$(PY).evaluate --data $(TEST) --run runs/qwen27b_zeroshot

baseline-2b: ## 소형 모델 zero-shot (8081에 serve_model.sh 필요)
	$(PY).predict --data $(TEST) --run runs/qwen2b_zeroshot --base-url http://127.0.0.1:8081/v1 --model models/Qwen3.5-2B-bf16 --workers 2
	$(PY).evaluate --data $(TEST) --run runs/qwen2b_zeroshot

baseline-docling: ## Docling(TableFormer) 기준선
	uv run --extra docling python -m ko_table_vlm.predict --data $(TEST) --run runs/docling --backend docling
	$(PY).evaluate --data $(TEST) --run runs/docling

report: ## runs/* 비교표 → runs/report.md (문서용 표는 docs/0xx에 정리)
	$(PY).report $$(ls -d runs/*/ | sed 's#/$$##') > runs/report.md && cat runs/report.md
