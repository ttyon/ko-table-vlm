#!/bin/zsh
# 학습할 소형 VLM 내려받기 → models/<이름>  (재실행하면 이어받기)
#   ./scripts/download_model.sh                                  # 기본: Qwen3.5-2B-bf16
#   ./scripts/download_model.sh mlx-community/Qwen3.5-4B-MLX-4bit
set -e
cd "$(dirname "$0")/.."
REPO="${1:-mlx-community/Qwen3.5-2B-bf16}"
DEST="models/${REPO##*/}"
mkdir -p models
export HF_HUB_DISABLE_XET=1   # Xet 전송이 멈추는 문제 회피 (llm-serving에서 겪음)
uv run hf download "$REPO" --local-dir "$DEST"
du -sh "$DEST"
