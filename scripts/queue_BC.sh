#!/bin/zsh
# 015 실험 B(v3 데이터)·C(v3 + 27B 증류) — 학습 → 체크포인트 선택(select_ckpt2.sh)
#   ./scripts/queue_BC.sh 0      # seed 0: B, C
#   ./scripts/queue_BC.sh 1      # seed 1: B, C
set -e
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:$PATH"
SEED=$1
for exp in B C; do
  NAME=${exp}_s$SEED
  if [[ ! -s adapters/$NAME/0003000_adapters.safetensors ]]; then
    MODEL=models/Qwen3.5-2B-bf16 DATA=data/sft/html_$exp NAME=$NAME RANK=16 ITERS=3000 MAXSEQ=6144 \
      EXTRA="--seed $SEED --lr-schedule cosine_decay --warmup-steps 100 --min-learning-rate 1e-5" \
      ./scripts/train.sh > /dev/null
  fi
  ./scripts/select_ckpt2.sh $NAME 1000 1500 2000 2500 3000 | grep -E "^SEL|DONE"
done
echo DONE BC seed $SEED
