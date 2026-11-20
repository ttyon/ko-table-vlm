#!/bin/zsh
# 015 사전 등록: test-real-3 최종 1회 평가. 대상은 runs/FINAL_SELECTION.txt에 고정한 6개 시스템.
# 이 스크립트 실행 전까지 test-real-3은 어떤 모델로도 채점하지 않았다.
set -e
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:$PATH"
py() { local m=$1; shift; uv run python -m ko_table_vlm.$m "$@"; }
SMALL=models/Qwen3.5-2B-bf16
KEY="$(cat ~/.config/llm-serving/api_key)"
ready() { for i in {1..120}; do curl -s -m 2 -H "Authorization: Bearer $KEY" http://127.0.0.1:8081/health | grep -q '"model_ready":true' && return 0; sleep 2; done; return 1; }
R3=data/real3/manifest.jsonl
[[ -s data/res/real3_1280/manifest.jsonl ]] || uv run python scripts/make_resized.py $R3 data/res/real3 --sizes 1280
R3H=data/res/real3_1280/manifest.jsonl
score() { py evaluate --data $2 --run runs/$1 > /dev/null; py evaluate --data $2 --run runs/$1 --ignore-space --out-suffix _nospace > /dev/null; echo "REAL3 $1: $(sed -n '8p' runs/$1/summary.md)"; }

uv run --extra docling python -m ko_table_vlm.predict --data $R3 --run runs/docling__real3 --backend docling > /dev/null 2>&1
score docling__real3 $R3
for spec in "zs_qwen2b:" "final2b:adapters/lora_html_mix_r16_it1500" "A0:adapters/A0_mix_seq6144" "Cfinal:adapters/C_s1_it3000"; do
  name=${spec%%:*}; ad=${spec#*:}
  tmux kill-session -t tvlm 2>/dev/null || true
  tmux new -d -s tvlm "ADAPTER=$ad MODEL=$SMALL ./scripts/serve_model.sh > runs/serve_tvlm.log 2>&1"; sleep 3; ready
  py predict --data $R3H --run runs/${name}__real3_1280 --base-url http://127.0.0.1:8081/v1 --model $SMALL --workers 2 > /dev/null
  score ${name}__real3_1280 $R3H
done
tmux kill-session -t tvlm 2>/dev/null || true
py predict --data $R3H --run runs/zs27b__real3_1280 --model models/Qwen3.8-27B-4bit --workers 2 > /dev/null
score zs27b__real3_1280 $R3H
echo DONE real3
