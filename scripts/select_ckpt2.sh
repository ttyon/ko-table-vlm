#!/bin/zsh
# 015 체크포인트 선택 규칙: 각 체크포인트마다
#   ① 합성 val TEDS — 원본 val 앞 100 + v3 val 앞 100 (평균)
#   ② 라벨 없는 실제 dev 59개(기존 17 + 증류 풀 dev 42, 입력 1280)의 잘림 수
# → 잘림 0 중 ① 최고. test 계열은 쓰지 않는다.
#   ./scripts/select_ckpt2.sh <adapter_name> [steps...]      (기본 1000 1500 2000 2500 3000)
set -e
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:$PATH"
NAME=$1; shift; STEPS=(${@:-1000 1500 2000 2500 3000})
SMALL=${MODEL:-models/Qwen3.5-2B-bf16}
KEY="$(cat ~/.config/llm-serving/api_key)"
ready() { for i in {1..120}; do curl -s -m 2 -H "Authorization: Bearer $KEY" http://127.0.0.1:8081/health | grep -q '"model_ready":true' && return 0; sleep 2; done; return 1; }
API=(--base-url http://127.0.0.1:8081/v1 --model $SMALL --workers 2)
for st in $STEPS; do
  d=adapters/${NAME}_it$st
  if [[ ! -s $d/adapters.safetensors ]]; then
    mkdir -p $d; cp adapters/$NAME/adapter_config.json $d/
    cp adapters/$NAME/$(printf %07d $st)_adapters.safetensors $d/adapters.safetensors
  fi
  tmux kill-session -t tvlm 2>/dev/null || true
  tmux new -d -s tvlm "ADAPTER=$d MODEL=$SMALL ./scripts/serve_model.sh > runs/serve_tvlm.log 2>&1"; sleep 3; ready
  for v in val val_v3; do
    uv run python -m ko_table_vlm.predict --data data/generated/$v/manifest.jsonl --run runs/sel2_${NAME}_it${st}__$v $API --limit 100 > /dev/null
    uv run python -m ko_table_vlm.evaluate --data data/generated/$v/manifest.jsonl --run runs/sel2_${NAME}_it${st}__$v --limit 100 > /dev/null
  done
  uv run python -m ko_table_vlm.predict --data data/res/dev_all_1280/manifest.jsonl --run runs/sel2_${NAME}_it${st}__dev $API > /dev/null
  uv run python - <<PY
import json
a=json.load(open('runs/sel2_${NAME}_it${st}__val/summary.json'))['overall']['teds']
b=json.load(open('runs/sel2_${NAME}_it${st}__val_v3/summary.json'))['overall']['teds']
P=[json.loads(l) for l in open('runs/sel2_${NAME}_it${st}__dev/predictions.jsonl')]
t=sum(p['finish_reason']=='length' for p in P)
print(f"SEL ${NAME} it${st}: val {a:.3f} val_v3 {b:.3f} mean {(a+b)/2:.3f}  dev 잘림 {t}/{len(P)}")
PY
done
tmux kill-session -t tvlm 2>/dev/null || true
echo DONE select2 $NAME
