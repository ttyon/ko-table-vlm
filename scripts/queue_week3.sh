#!/bin/zsh
# 3주차 실험 단계 실행기 (단계별로 따로 실행 → 끝날 때마다 문서화)
#   ./scripts/queue_week3.sh aug        # 009 데이터 보강: 학습 + 평가
#   ./scripts/queue_week3.sh mix        # 009b 원본+보강 혼합 학습 + 평가
#   ./scripts/queue_week3.sh rank       # 011 rank 8/16/32 @1500 iter (보강 데이터): 학습(8, 32) + 평가(3개)
#   ./scripts/queue_week3.sh size4b     # 011 4B QLoRA: 다운로드 + zero-shot(real) + 학습 + 평가
#   ./scripts/queue_week3.sh res        # 010 해상도 640/960/1280/1600: 추론 전용
# 평가 세트: val(앞 100, 선택용) · test(앞 100) · ood(앞 100) · real(50). 동시 2요청.
set -e
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:$PATH"
py() { local m=$1; shift; uv run python -m ko_table_vlm.$m "$@"; }
G=data/generated; R=data/real/manifest.jsonl
KEY="$(cat ~/.config/llm-serving/api_key)"
ready() { for i in {1..180}; do curl -s -m 2 -H "Authorization: Bearer $KEY" "http://127.0.0.1:$1/health" | grep -q healthy && return 0; sleep 2; done; return 1; }
serve() {  # $1=model $2=adapter(optional)
  tmux kill-session -t tvlm 2>/dev/null || true
  tmux new -d -s tvlm "ADAPTER=$2 MODEL=$1 ./scripts/serve_model.sh > runs/serve_tvlm.log 2>&1"
  sleep 3; ready 8081
}
unserve() { tmux kill-session -t tvlm 2>/dev/null || true; }
ev() {  # $1=run-name $2=model $3=fmt $4...=splits(val test ood real)
  local name=$1 model=$2 fmt=$3; shift 3
  for s in "$@"; do
    local data lim=()
    if [[ $s == real ]]; then data=$R; else data=$G/$s/manifest.jsonl; lim=(--limit 100); fi
    py predict --data $data --run runs/${name}__$s --base-url http://127.0.0.1:8081/v1 --model $model --workers 2 --format $fmt $lim
    py evaluate --data $data --run runs/${name}__$s $lim > /dev/null
    echo "$name $s: $(sed -n '8p' runs/${name}__$s/summary.md)"
  done
}
SMALL=models/Qwen3.5-2B-bf16
mkdir -p runs

case "$1" in
  aug)
    [[ -s data/sft/html_aug/train.jsonl ]] || py to_sft --train $G/train_aug/manifest.jsonl --valid $G/val/manifest.jsonl --out data/sft/html_aug --format html
    MODEL=$SMALL DATA=data/sft/html_aug NAME=lora_html_aug_r16 RANK=16 ITERS=3000 ./scripts/train.sh > /dev/null
    serve $SMALL adapters/lora_html_aug_r16
    ev lora_html_aug_r16 $SMALL html val test ood real
    unserve
    # 비교 기준(E2)도 val 100 채점
    serve $SMALL adapters/lora_html_r16; ev lora_html_r16 $SMALL html val; unserve ;;
  mix)   # 009b: 원본 3,000 + 보강 3,000 섞기, 같은 연산량(3,000 iter)
    if [[ ! -s data/sft/html_mix/train.jsonl ]]; then
      mkdir -p data/sft/html_mix
      cat data/sft/html/train.jsonl data/sft/html_aug/train.jsonl | uv run python -c "import sys,random; l=sys.stdin.readlines(); random.Random(0).shuffle(l); sys.stdout.writelines(l)" > data/sft/html_mix/train.jsonl
      cp data/sft/html/valid.jsonl data/sft/html_mix/valid.jsonl
    fi
    MODEL=$SMALL DATA=data/sft/html_mix NAME=lora_html_mix_r16 RANK=16 ITERS=3000 ./scripts/train.sh > /dev/null
    serve $SMALL adapters/lora_html_mix_r16; ev lora_html_mix_r16 $SMALL html val test ood real; unserve ;;
  rank)  # 011: 보강 데이터(html_aug)에서 rank 8/16/32 @1500 iter. r16은 aug 학습의 1500 체크포인트 사용
    D=${RANK_DATA:-html_aug}; BASE=${RANK_BASE:-lora_html_aug_r16}
    for r in 8 32; do
      [[ -s adapters/${D}_r${r}_it1500/adapters.safetensors ]] || \
        MODEL=$SMALL DATA=data/sft/$D NAME=${D}_r${r}_it1500 RANK=$r ITERS=1500 ./scripts/train.sh > /dev/null
    done
    mkdir -p adapters/${D}_r16_it1500
    cp adapters/$BASE/adapter_config.json adapters/${D}_r16_it1500/
    cp adapters/$BASE/0001500_adapters.safetensors adapters/${D}_r16_it1500/adapters.safetensors
    for r in 8 16 32; do
      serve $SMALL adapters/${D}_r${r}_it1500; ev ${D}_r${r}_it1500 $SMALL html val test ood real; unserve
    done ;;
  size4b)
    M4=models/Qwen3.5-4B-MLX-4bit
    [[ -s $M4/config.json ]] || ./scripts/download_model.sh mlx-community/Qwen3.5-4B-MLX-4bit
    serve $M4 ""; ev zs_qwen4b $M4 html test real; unserve
    MODEL=$M4 DATA=data/sft/${SIZE_DATA:-html_mix} NAME=lora_4b_html_r16 RANK=16 ITERS=${SIZE_ITERS:-1500} ./scripts/train.sh > /dev/null
    serve $M4 adapters/lora_4b_html_r16; ev lora_4b_html_r16 $M4 html val test ood real; unserve ;;
  res)
    BEST=${BEST:-lora_html_r16}
    for L in 640 960 1280 1600; do
      [[ -s data/res/test_$L/manifest.jsonl ]] || uv run python scripts/make_resized.py $G/test/manifest.jsonl data/res/test --sizes $L --limit 50
      [[ -s data/res/real_$L/manifest.jsonl ]] || uv run python scripts/make_resized.py $R data/res/real --sizes $L
    done
    serve $SMALL adapters/$BEST
    for L in 640 960 1280 1600; do
      for s in test real; do
        py predict --data data/res/${s}_$L/manifest.jsonl --run runs/res_${BEST}__${s}_$L --base-url http://127.0.0.1:8081/v1 --model $SMALL --workers 2
        py evaluate --data data/res/${s}_$L/manifest.jsonl --run runs/res_${BEST}__${s}_$L > /dev/null
        echo "res $L $s: $(sed -n '8p' runs/res_${BEST}__${s}_$L/summary.md)"
      done
    done
    unserve ;;
  *) sed -n '2,7p' "$0"; exit 1 ;;
esac
echo DONE $1
