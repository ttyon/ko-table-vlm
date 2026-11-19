#!/bin/zsh
# 1주차 마무리: 27B 기준선(test/ood 앞 50, real 50) + real이 50개로 늘어난 뒤 기존 시스템의 추가 19개 예측.
# predict는 이어서 실행되므로 이미 예측한 id는 건너뛴다.
set -e
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:$PATH"
py() { local m=$1; shift; uv run python -m ko_table_vlm.$m "$@"; }
G=data/generated; R=data/real/manifest.jsonl; SMALL=models/Qwen3.5-2B-bf16
KEY="$(cat ~/.config/llm-serving/api_key)"
ready() { for i in {1..120}; do curl -s -m 2 -H "Authorization: Bearer $KEY" "http://127.0.0.1:$1/health" | grep -q healthy && return 0; sleep 2; done; return 1; }

echo "[27B] test/ood 50, real 50"
for s in test ood; do
  py predict --data $G/$s/manifest.jsonl --run runs/zs_qwen27b__$s --model models/Qwen3.8-27B-4bit --workers 2 --limit 50
done
py predict --data $R --run runs/zs_qwen27b__real --model models/Qwen3.8-27B-4bit --workers 2

for spec in "zs_qwen2b::html" "lora_html_r16:adapters/lora_html_r16:html" "lora_otsl_r16:adapters/lora_otsl_r16:otsl"; do
  name=${spec%%:*}; rest=${spec#*:}; ad=${rest%%:*}; fmt=${rest#*:}
  echo "[$name] real 추가 예측"
  tmux kill-session -t tvlm 2>/dev/null || true
  tmux new -d -s tvlm "ADAPTER=$ad MODEL=$SMALL ./scripts/serve_model.sh > runs/serve_tvlm.log 2>&1"
  sleep 3; ready 8081
  py predict --data $R --run runs/${name}__real --base-url http://127.0.0.1:8081/v1 --model $SMALL --workers 2 --format $fmt
  tmux kill-session -t tvlm 2>/dev/null || true
done
echo DONE
