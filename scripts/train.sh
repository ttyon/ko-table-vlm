#!/bin/zsh
# LoRA SFT (mlx_vlm.train)
#   ./scripts/train.sh                    # 기본값
#   NAME=r16_html RANK=16 ITERS=3000 ./scripts/train.sh
#   MODEL=models/Qwen3.5-4B-MLX-4bit DATA=data/sft/otsl NAME=4b_otsl ./scripts/train.sh
# 결과: adapters/<NAME>/ , 로그 runs/train_<NAME>.log
set -e
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:$PATH"

MODEL="${MODEL:-models/Qwen3.5-2B-bf16}"
DATA="${DATA:-data/sft/html}"
NAME="${NAME:-r16_html}"
RANK="${RANK:-16}"
ALPHA="${ALPHA:-$((RANK * 2))}"
LR="${LR:-1e-4}"
ITERS="${ITERS:-3000}"          # train 3000줄 × batch 1 → 약 1 epoch
BATCH="${BATCH:-1}"

mkdir -p runs adapters
echo "model=$MODEL data=$DATA rank=$RANK alpha=$ALPHA lr=$LR iters=$ITERS" | tee "runs/train_${NAME}.log"
# --train-on-completions : 질문(이미지+프롬프트) 부분은 loss에서 빼고 정답 HTML만 학습
# --grad-checkpoint      : 긴 출력(표 HTML) 때문에 메모리 절약
uv run python -m mlx_vlm.train \
  --model "$MODEL" --data "$DATA" \
  --train-type lora --lora-rank "$RANK" --lora-alpha "$ALPHA" --lora-dropout 0.05 \
  --learning-rate "$LR" --optimizer adamw \
  --batch-size "$BATCH" --iters "$ITERS" \
  --train-on-completions --grad-checkpoint \
  --steps-per-report 20 --steps-per-eval 250 --val-batches 25 --steps-per-save 500 \
  --output-path "adapters/$NAME" \
  2>&1 | tee -a "runs/train_${NAME}.log"
