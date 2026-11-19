#!/bin/zsh
# 체크포인트 선택 (009c): 각 체크포인트를 (1) 합성 val 앞 100 TEDS, (2) 라벨 없는 실제 표 17개(test-real 제외)의
# 반복·잘림 비율로 평가. 정답이 필요 없는 (2) 덕분에 test-real을 보지 않고도 반복 붕괴를 걸러낼 수 있다.
#   ./scripts/select_ckpt.sh lora_html_mix_r16 [1500 2000 2500 3000]
set -e
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:$PATH"
NAME=$1; shift; STEPS=(${@:-1500 2000 2500 3000})
SMALL=${MODEL:-models/Qwen3.5-2B-bf16}
KEY="$(cat ~/.config/llm-serving/api_key)"
ready() { for i in {1..120}; do curl -s -m 2 -H "Authorization: Bearer $KEY" http://127.0.0.1:8081/health | grep -q healthy && return 0; sleep 2; done; return 1; }
for st in $STEPS; do
  d=adapters/${NAME}_it$st
  if [[ ! -s $d/adapters.safetensors ]]; then
    mkdir -p $d; cp adapters/$NAME/adapter_config.json $d/
    cp adapters/$NAME/$(printf %07d $st)_adapters.safetensors $d/adapters.safetensors
  fi
  tmux kill-session -t tvlm 2>/dev/null || true
  tmux new -d -s tvlm "ADAPTER=$d MODEL=$SMALL ./scripts/serve_model.sh > runs/serve_tvlm.log 2>&1"; sleep 3; ready
  uv run python -m ko_table_vlm.predict --data data/generated/val/manifest.jsonl --run runs/sel_${NAME}_it${st}__val --base-url http://127.0.0.1:8081/v1 --model $SMALL --workers 2 --limit 100 > /dev/null
  uv run python -m ko_table_vlm.evaluate --data data/generated/val/manifest.jsonl --run runs/sel_${NAME}_it${st}__val --limit 100 > /dev/null
  uv run python -m ko_table_vlm.predict --data data/real/dev_unlabeled/manifest.jsonl --run runs/sel_${NAME}_it${st}__dev --base-url http://127.0.0.1:8081/v1 --model $SMALL --workers 2 > /dev/null
  uv run python - <<PY
import json
v=json.load(open('runs/sel_${NAME}_it${st}__val/summary.json'))['overall']
P=[json.loads(l) for l in open('runs/sel_${NAME}_it${st}__dev/predictions.jsonl')]
t=sum(p['finish_reason']=='length' for p in P)
print(f"${NAME} it${st}: val TEDS {v['teds']:.3f}  dev 잘림 {t}/{len(P)}  dev p50 {sorted(p['latency_s'] for p in P)[len(P)//2]:.1f}s")
PY
done
tmux kill-session -t tvlm 2>/dev/null || true
echo DONE select $NAME
