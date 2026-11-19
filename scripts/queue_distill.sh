#!/bin/zsh
# 015 증류: 27B(입력 1280)로 증류 풀 라벨링 → 필터 → data/sft/distill
set -e
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:$PATH"
uv run python -m ko_table_vlm.predict --data data/res/distill_1280/manifest.jsonl --run runs/teacher27b__distill_1280 \
    --model models/Qwen3.8-27B-4bit --workers 2
uv run python -m ko_table_vlm.distill filter --root data/distill --run runs/teacher27b__distill_1280 \
    --out data/sft/distill --min-text-agree 0.95 --repeat 2
echo DONE distill
