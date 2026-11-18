#!/bin/zsh
# 소형 모델(+LoRA 어댑터)을 OpenAI 호환 API로 띄운다. 기존 llm-serving(8080)과 같은 API 키 사용.
#   ./scripts/serve_model.sh                                   # 학습 전 소형 모델 (zero-shot)
#   ADAPTER=adapters/r16_html ./scripts/serve_model.sh         # LoRA 적용
#   tmux new -d -s table-vlm './scripts/serve_model.sh'        # 백그라운드
set -e
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:$PATH"
MODEL="${MODEL:-models/Qwen3.5-2B-bf16}"
PORT="${PORT:-8081}"
KEY_FILE="$HOME/.config/llm-serving/api_key"
ARGS=(--model "$MODEL" --host 127.0.0.1 --port "$PORT" --api-key "$(cat "$KEY_FILE")")
[[ -n "$ADAPTER" ]] && ARGS+=(--adapter-path "$ADAPTER")
echo "Serving $MODEL ${ADAPTER:+(adapter $ADAPTER)} on http://127.0.0.1:$PORT/v1"
uv run python -m mlx_vlm.server "${ARGS[@]}"
