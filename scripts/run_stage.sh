#!/bin/zsh
# 실험 단계 실행기. 단계별로 따로 돌리고 결과는 runs/<이름>/ 에 쌓인다 (이어서 실행 가능).
#   ./scripts/run_stage.sh docling       # Docling 기준선 (test, ood 전체)
#   ./scripts/run_stage.sh zs2b          # 2B zero-shot (test/ood 앞 100개)
#   ./scripts/run_stage.sh zs27b         # 27B zero-shot (8080 서버 사용, test/ood 앞 100개)
#   ./scripts/run_stage.sh train NAME FORMAT [RANK]     # 예: train lora_html_r16 html 16
#   ./scripts/run_stage.sh evalft NAME FORMAT           # 어댑터 서빙 후 test/ood 전체 평가
# API 실행은 모두 --workers 2 (동시 2요청) 조건으로 통일한다.
set -e
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:$PATH"
py() { local m=$1; shift; uv run python -m ko_table_vlm.$m "$@"; }
SMALL="models/Qwen3.5-2B-bf16"
KEY="$(cat ~/.config/llm-serving/api_key)"
G=data/generated
N_SLOW=100
mpath() { [[ $1 == real ]] && echo data/real/manifest.jsonl || echo $G/$1/manifest.jsonl; }

wait_ready() {  # $1=port
  for i in {1..120}; do
    curl -s -m 2 -H "Authorization: Bearer $KEY" "http://127.0.0.1:$1/health" | grep -q '"model_ready":true\|"status":"healthy"' && return 0
    sleep 2
  done
  echo "server on $1 not ready" >&2; return 1
}

start_small() {  # $1=adapter(optional)
  tmux kill-session -t tvlm 2>/dev/null || true
  tmux new -d -s tvlm "ADAPTER=$1 MODEL=$SMALL ./scripts/serve_model.sh > runs/serve_tvlm.log 2>&1"
  sleep 3; wait_ready 8081
}
stop_small() { tmux kill-session -t tvlm 2>/dev/null || true; }

run_eval() {  # $1=run name, $2=split, $3=extra predict args...
  local run=$1 split=$2; shift 2
  py predict --data $(mpath $split) --run runs/${run}__$split "$@"
  py evaluate --data $(mpath $split) --run runs/${run}__$split > /dev/null
  sed -n '8p' runs/${run}__$split/summary.md
}

mkdir -p runs
case "$1" in
  docling)
    for s in test ood; do
      uv run --extra docling python -m ko_table_vlm.predict --data $G/$s/manifest.jsonl --run runs/docling__$s --backend docling
      py evaluate --data $G/$s/manifest.jsonl --run runs/docling__$s > /dev/null; sed -n '8p' runs/docling__$s/summary.md
    done ;;
  zs2b)
    start_small ""
    for s in test ood real; do run_eval zs_qwen2b $s --base-url http://127.0.0.1:8081/v1 --model $SMALL --workers 2 --limit $N_SLOW; done
    stop_small ;;
  zs27b)
    wait_ready 8080
    for s in test ood real; do run_eval zs_qwen27b $s --model models/Qwen3.8-27B-4bit --workers 2 --limit $N_SLOW; done ;;
  train)
    NAME=$2 FMT=$3 RANK=${4:-16}
    [[ -s data/sft/$FMT/train.jsonl ]] || py to_sft --train $G/train/manifest.jsonl --valid $G/val/manifest.jsonl --out data/sft/$FMT --format $FMT
    MODEL=$SMALL DATA=data/sft/$FMT NAME=$NAME RANK=$RANK ITERS=${ITERS:-3000} ./scripts/train.sh ;;
  evalft)
    NAME=$2 FMT=$3
    start_small adapters/$NAME
    for s in test ood real; do run_eval $NAME $s --base-url http://127.0.0.1:8081/v1 --model $SMALL --workers 2 --format $FMT; done
    stop_small ;;
  zs2b-real)   # 2B zero-shot을 real에만 (test/ood는 이미 있을 때)
    start_small ""; run_eval zs_qwen2b real --base-url http://127.0.0.1:8081/v1 --model $SMALL --workers 2; stop_small ;;
  *) sed -n '2,9p' "$0"; exit 1 ;;
esac
