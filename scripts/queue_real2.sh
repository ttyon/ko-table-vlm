#!/bin/zsh
# 014: 다른 기관 문서(test-real-2)와 스캔 모사 세트 평가. 이어서 실행 가능.
#   ./scripts/queue_real2.sh
set -e
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:$PATH"
py() { local m=$1; shift; uv run python -m ko_table_vlm.$m "$@"; }
SMALL=models/Qwen3.5-2B-bf16
KEY="$(cat ~/.config/llm-serving/api_key)"
ready() { for i in {1..180}; do curl -s -m 2 -H "Authorization: Bearer $KEY" "http://127.0.0.1:$1/health" | grep -q healthy && return 0; sleep 2; done; return 1; }
serve() { tmux kill-session -t tvlm 2>/dev/null || true; tmux new -d -s tvlm "ADAPTER=$1 MODEL=$SMALL ./scripts/serve_model.sh > runs/serve_tvlm.log 2>&1"; sleep 3; ready 8081; }
run() {  # $1=run name, $2=manifest, $3...=predict args
  local name=$1 data=$2; shift 2
  py predict --data $data --run runs/$name "$@" > /dev/null
  py evaluate --data $data --run runs/$name > /dev/null
  py evaluate --data $data --run runs/$name --ignore-space --out-suffix _nospace > /dev/null
  echo "$name: $(sed -n '8p' runs/$name/summary.md)"
}
R2=data/real2/manifest.jsonl
R2H=data/res/real2_1280/manifest.jsonl
SR=data/scan/real/manifest.jsonl; SR2=data/scan/real2/manifest.jsonl
SRH=data/res/scanreal_1280/manifest.jsonl; SR2H=data/res/scanreal2_1280/manifest.jsonl
RH=data/res/real_1280/manifest.jsonl

# Docling (원래 해상도 — 해상도 무관함을 010에서 확인)
for spec in "docling__real2:$R2" "docling__scanreal:$SR" "docling__scanreal2:$SR2"; do
  uv run --extra docling python -m ko_table_vlm.predict --data ${spec#*:} --run runs/${spec%%:*} --backend docling > /dev/null 2>&1
  py evaluate --data ${spec#*:} --run runs/${spec%%:*} > /dev/null
  py evaluate --data ${spec#*:} --run runs/${spec%%:*} --ignore-space --out-suffix _nospace > /dev/null
  echo "${spec%%:*}: $(sed -n '8p' runs/${spec%%:*}/summary.md)"
done

API=(--base-url http://127.0.0.1:8081/v1 --model $SMALL --workers 2)
serve ""
run zs_qwen2b__real2 $R2 $API
serve adapters/lora_html_mix_r16_it1500
run final2b__real2 $R2 $API
run final2b__real2_1280 $R2H $API
run final2b__scanreal_1280 $SRH $API
run final2b__scanreal2_1280 $SR2H $API
serve adapters/lora_html_r16
run orig2b__real_1280 $RH $API
run orig2b__real2_1280 $R2H $API
run orig2b__scanreal_1280 $SRH $API
run orig2b__scanreal2_1280 $SR2H $API
tmux kill-session -t tvlm 2>/dev/null || true

B27=(--model models/Qwen3.8-27B-4bit --workers 2)
ready 8080
run zs27b__real2 $R2 $B27
run zs27b__real2_1280 $R2H $B27
run zs27b__scanreal_1280 $SRH $B27
run zs27b__scanreal2_1280 $SR2H $B27
echo DONE real2
