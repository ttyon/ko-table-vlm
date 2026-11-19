#!/bin/zsh
# 후보 어댑터 평가 (test-real-3 제외): test·ood·test_v3 앞 100, test-real·test-real-2·스캔 모사 (입력 1280), dev 잘림
#   ./scripts/eval_candidate.sh <run_prefix> <adapter_dir>
set -e
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:$PATH"
NAME=$1; AD=$2; SMALL=${MODEL:-models/Qwen3.5-2B-bf16}
KEY="$(cat ~/.config/llm-serving/api_key)"
ready() { for i in {1..120}; do curl -s -m 2 -H "Authorization: Bearer $KEY" http://127.0.0.1:8081/health | grep -q '"model_ready":true' && return 0; sleep 2; done; return 1; }
tmux kill-session -t tvlm 2>/dev/null || true
tmux new -d -s tvlm "ADAPTER=$AD MODEL=$SMALL ./scripts/serve_model.sh > runs/serve_tvlm.log 2>&1"; sleep 3; ready
API=(--base-url http://127.0.0.1:8081/v1 --model $SMALL --workers 2)
for spec in "test:data/generated/test/manifest.jsonl:100" "ood:data/generated/ood/manifest.jsonl:100" "test_v3:data/generated/test_v3/manifest.jsonl:100" \
            "real_1280:data/res/real_1280/manifest.jsonl:0" "real2_1280:data/res/real2_1280/manifest.jsonl:0" \
            "scanreal_1280:data/res/scanreal_1280/manifest.jsonl:0" "scanreal2_1280:data/res/scanreal2_1280/manifest.jsonl:0"; do
  s=${spec%%:*}; rest=${spec#*:}; d=${rest%:*}; lim=${rest##*:}
  L=(); [[ $lim != 0 ]] && L=(--limit $lim)
  uv run python -m ko_table_vlm.predict --data $d --run runs/${NAME}__$s $API $L > /dev/null
  uv run python -m ko_table_vlm.evaluate --data $d --run runs/${NAME}__$s $L > /dev/null
  uv run python -m ko_table_vlm.evaluate --data $d --run runs/${NAME}__$s $L --ignore-space --out-suffix _nospace > /dev/null
  echo "EVAL $NAME $s: $(sed -n '8p' runs/${NAME}__$s/summary.md)"
done
uv run python -m ko_table_vlm.predict --data data/res/dev_all_1280/manifest.jsonl --run runs/${NAME}__dev $API > /dev/null
uv run python -c "import json;P=[json.loads(l) for l in open('runs/${NAME}__dev/predictions.jsonl')];print('EVAL $NAME dev 잘림',sum(p['finish_reason']=='length' for p in P),'/',len(P))"
tmux kill-session -t tvlm 2>/dev/null || true
